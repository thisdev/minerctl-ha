"""Asynchroner Client für Antminer mit Braiins OS: API (Port 4028) zum Lesen, SSH zum Ändern der Config."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from . import tomlmini as T

try:  # von HA über manifest.json installiert; Import hier oben, damit HA ihn nicht im Event-Loop meldet
    import asyncssh
except ImportError:  # pragma: no cover – nur für Tests ohne asyncssh
    asyncssh = None

_LOGGER = logging.getLogger(__name__)

BOS_CONF = "/etc/bosminer.toml"
BOS_ORIG = "/etc/bosminer.toml.minerctl-orig"   # Stand vor der ersten Änderung durch minerctl
BOS_BAK = "/etc/bosminer.toml.bak"              # Stand vor der letzten Änderung
BOS_INIT = "/etc/init.d/bosminer"
RESTART_TIMEOUT = 150

# Ältere Dropbear-Versionen auf dem S9 bieten teils nur ssh-rsa an.
_HOST_KEY_ALGS = ["ssh-ed25519", "ecdsa-sha2-nistp256", "rsa-sha2-512", "rsa-sha2-256", "ssh-rsa"]


class MinerError(Exception):
    """Fehler mit verständlicher Meldung für die Oberfläche."""


def _ths(summary: dict, which: str) -> Optional[float]:
    for unit, div in (("THS", 1), ("GHS", 1e3), ("MHS", 1e6)):
        v = summary.get(f"{unit} {which}")
        if isinstance(v, (int, float)):
            return v / div
    return None


class BosMiner:
    def __init__(self, host: str, username: str = "root", password: str = "",
                 api_port: int = 4028, ssh_port: int = 22) -> None:
        self.host = host
        self.username = username
        self.password = password or ""
        self.api_port = api_port
        self.ssh_port = ssh_port
        self._conn = None
        self._ssh_lock = asyncio.Lock()
        self.change_lock = asyncio.Lock()
        self.restart_timeout = RESTART_TIMEOUT
        self.poll_delay = 3.0

    # ───────────── API ─────────────
    async def api(self, command: str, parameter: Any = None, timeout: float = 5.0) -> dict:
        payload: Dict[str, Any] = {"command": command}
        if parameter is not None:
            payload["parameter"] = parameter
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.api_port), timeout)
        except (OSError, asyncio.TimeoutError) as err:
            raise MinerError(f"API nicht erreichbar ({err.__class__.__name__})") from err
        try:
            writer.write(json.dumps(payload).encode())
            await writer.drain()
            raw = await asyncio.wait_for(reader.read(), timeout)
        except (OSError, asyncio.TimeoutError) as err:
            raise MinerError("API antwortet nicht") from err
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        text = raw.rstrip(b"\x00").decode("utf-8", "replace").replace("}{", "},{")
        if not text.strip():
            raise MinerError("API antwortet nicht (bosminer gestoppt oder startet gerade)")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            raise MinerError("Ungültige API-Antwort") from err
        status = data.get("STATUS") or [{}]
        if isinstance(status, list) and status and status[0].get("STATUS") == "E":
            raise MinerError(status[0].get("Msg", "API-Fehler"))
        return data

    async def api_alive(self) -> bool:
        try:
            await self.api("summary", timeout=3)
            return True
        except MinerError:
            return False

    async def fetch_api(self) -> dict:
        """Laufzeitdaten. online=False, wenn bosminer nicht antwortet."""
        data: Dict[str, Any] = {"online": False}
        try:
            summary = (await self.api("summary")).get("SUMMARY") or [{}]
        except MinerError as err:
            data["api_error"] = str(err)
            return data
        s = summary[0]
        data.update(online=True, hash_5s=_ths(s, "5s"), hash_av=_ths(s, "av"))
        for cmd, key in (("devs", "DEVS"), ("temps", "TEMPS"), ("fans", "FANS"),
                         ("tunerstatus", "TUNERSTATUS"), ("pools", "POOLS")):
            try:
                data[cmd] = (await self.api(cmd)).get(key) or []
            except MinerError:
                data[cmd] = []
        return data

    async def version(self) -> dict:
        try:
            return ((await self.api("version")).get("VERSION") or [{}])[0]
        except MinerError:
            return {}

    # ───────────── SSH ─────────────
    async def _connect(self):
        try:
            return await asyncio.wait_for(asyncssh.connect(
                self.host, port=self.ssh_port, username=self.username, password=self.password,
                known_hosts=None, client_keys=(), server_host_key_algs=_HOST_KEY_ALGS,
                keepalive_interval=15), 15)
        except asyncssh.PermissionDenied as err:
            raise MinerError("SSH-Anmeldung abgelehnt – Benutzer oder Passwort prüfen") from err
        except (OSError, asyncio.TimeoutError, asyncssh.Error) as err:
            raise MinerError(f"SSH nicht erreichbar ({err.__class__.__name__})") from err

    async def ssh(self, command: str, input_text: Optional[str] = None, timeout: float = 90) -> str:
        async with self._ssh_lock:
            for attempt in (1, 2):
                if self._conn is None:
                    self._conn = await self._connect()
                try:
                    result = await asyncio.wait_for(
                        self._conn.run(command, input=input_text, check=False), timeout)
                    break
                except (asyncssh.Error, OSError, BrokenPipeError) as err:
                    self._close()
                    if attempt == 2:
                        raise MinerError(f"SSH-Verbindung abgebrochen ({err.__class__.__name__})") from err
                except asyncio.TimeoutError as err:
                    self._close()
                    raise MinerError("SSH-Befehl hat zu lange gedauert") from err
        if result.exit_status not in (0, None):
            msg = (result.stderr or "").strip().splitlines()
            raise MinerError(msg[-1] if msg else f"SSH-Befehl fehlgeschlagen (Code {result.exit_status})")
        return result.stdout or ""

    def _close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
        self._conn = None

    async def close(self) -> None:
        async with self._ssh_lock:
            self._close()

    # ───────────── Config ─────────────
    async def read_conf(self) -> str:
        text = await self.ssh(f"cat {BOS_CONF}")
        if "[" not in text:
            raise MinerError("bosminer.toml leer oder nicht gefunden – läuft Braiins OS?")
        return text

    async def config_state(self) -> dict:
        text = await self.read_conf()
        secs = T.sections(text)
        key, watts, tuning = T.power_settings(secs)
        fmt = secs.get("format", {})
        return {"power_key": key, "power_limit": watts, "autotuning": tuning,
                "chains": T.chain_settings(secs), "model": T.value(fmt.get("model")),
                "format": T.value(fmt.get("version"))}

    async def _wait_for_api(self) -> bool:
        deadline = time.monotonic() + self.restart_timeout
        await asyncio.sleep(self.poll_delay)
        while time.monotonic() < deadline:
            if await self.api_alive():
                return True
            await asyncio.sleep(self.poll_delay)
        return False

    async def _process_running(self) -> bool:
        try:
            return bool((await self.ssh("pidof bosminer || true")).strip())
        except MinerError:
            return False

    async def apply_conf(self, new_text: str) -> None:
        """Config schreiben, bosminer neu starten, bei Fehlstart automatisch zurückrollen."""
        await self.ssh(f"[ -f {BOS_ORIG} ] || cp {BOS_CONF} {BOS_ORIG}; cp {BOS_CONF} {BOS_BAK}; "
                       f"cat > {BOS_CONF}.tmp && mv {BOS_CONF}.tmp {BOS_CONF}", input_text=new_text)
        await self.ssh(f"{BOS_INIT} restart >/dev/null 2>&1 || true")
        if await self._wait_for_api():
            return
        if await self._process_running():
            _LOGGER.warning("%s: bosminer läuft, API antwortet noch nicht", self.host)
            return
        _LOGGER.warning("%s: bosminer startet mit neuer Config nicht – Rollback", self.host)
        await self.ssh(f"cp {BOS_BAK} {BOS_CONF} && {BOS_INIT} restart >/dev/null 2>&1 || true")
        if await self._wait_for_api():
            raise MinerError("Miner hat die Änderung abgelehnt. Vorherige Config ist wieder aktiv.")
        raise MinerError(f"Miner startet nicht. Bitte in der Weboberfläche prüfen (http://{self.host}).")

    # ───────────── Aktionen ─────────────
    async def set_power(self, watts: int) -> None:
        async with self.change_lock:
            await self.apply_conf(T.with_power(await self.read_conf(), watts))

    async def set_boards(self, changes: Dict[int, bool]) -> None:
        async with self.change_lock:
            text = await self.read_conf()
            state = T.chain_settings(T.sections(text))
            unknown = set(changes) - set(state)
            if unknown:
                raise MinerError(f"Board(s) {sorted(unknown)} gibt es nicht")
            state.update(changes)
            if not any(state.values()):
                raise MinerError("Mindestens ein Board muss an bleiben. Zum Abschalten 'Mining' ausschalten.")
            new = text
            for cid, enabled in changes.items():
                new = T.set_key(new, f"hash_chain.{cid}", "enabled", "true" if enabled else "false")
            if new != text:
                await self.apply_conf(new)

    async def apply_preset(self, preset: dict) -> bool:
        """Boards und Leistung in einem Schritt (ein Neustart). False = war bereits aktiv."""
        if not preset.get("power"):
            raise MinerError("Preset ohne Leistungswert – Autotuning wird nie abgeschaltet")
        async with self.change_lock:
            text = await self.read_conf()
            chains = T.chain_settings(T.sections(text))
            wanted = {int(b) for b in preset["boards"]}
            if not wanted or wanted - set(chains):
                raise MinerError(f"Ungültige Boards im Preset: {sorted(wanted)}")
            new = text
            for cid, enabled in chains.items():
                if enabled != (cid in wanted):
                    new = T.set_key(new, f"hash_chain.{cid}", "enabled", "true" if cid in wanted else "false")
            new = T.with_power(new, preset["power"])
            if new == text:
                return False
            await self.apply_conf(new)
            return True

    async def stop(self) -> None:
        async with self.change_lock:
            await self.ssh(f"{BOS_INIT} stop >/dev/null 2>&1 || true")

    async def start(self) -> bool:
        async with self.change_lock:
            await self.ssh(f"{BOS_INIT} start >/dev/null 2>&1 || true")
            return await self._wait_for_api()

    async def restart(self) -> bool:
        async with self.change_lock:
            await self.ssh(f"{BOS_INIT} restart >/dev/null 2>&1 || true")
            return await self._wait_for_api()

    async def restore(self) -> None:
        async with self.change_lock:
            if (await self.ssh(f"[ -f {BOS_ORIG} ] && echo yes || echo no")).strip() != "yes":
                raise MinerError("Keine Original-Config vorhanden – minerctl hat noch nichts geändert")
            await self.apply_conf(await self.ssh(f"cat {BOS_ORIG}"))
