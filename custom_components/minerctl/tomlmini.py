"""Kleiner, kommentarerhaltender TOML-Leser/-Schreiber für bosminer.toml (aus minerctl übernommen)."""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

S9_CHAINS = [6, 7, 8]

_SECTION_RE = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")
_KEY_RE = re.compile(r"""^\s*([A-Za-z0-9_\-]+|"[^"]*"|'[^']*')\s*=\s*(.*?)\s*$""")


def _strip_comment(raw: str) -> str:
    quote = None
    for i, ch in enumerate(raw):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#":
            return raw[:i].rstrip()
    return raw.strip()


def value(raw: Optional[str]):
    if raw is None:
        return None
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            pass
    return raw


def sections(text: str) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {"": {}}
    current = ""
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _SECTION_RE.match(line)
        if m:
            current = m.group(1)
            result.setdefault(current, {})
            continue
        m = _KEY_RE.match(line)
        if m:
            result.setdefault(current, {})[m.group(1).strip("\"'")] = _strip_comment(m.group(2))
    return result


def set_key(text: str, section: str, key: str, literal: str) -> str:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        m = _SECTION_RE.match(line)
        if m and m.group(1) == section and not line.strip().startswith("[["):
            start = i
            break
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", f"[{section}]", f"{key} = {literal}"]
        return "\n".join(lines) + "\n"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _SECTION_RE.match(lines[j]):
            end = j
            break
    for j in range(start + 1, end):
        if lines[j].lstrip().startswith("#"):
            continue
        m = _KEY_RE.match(lines[j])
        if m and m.group(1).strip("\"'") == key:
            indent = re.match(r"\s*", lines[j]).group(0)
            old = m.group(2)
            comment = old[len(_strip_comment(old)):].strip()
            lines[j] = f"{indent}{key} = {literal}" + (f" {comment}" if comment.startswith("#") else "")
            return "\n".join(lines) + "\n"
    insert_at = end
    while insert_at > start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines.insert(insert_at, f"{key} = {literal}")
    return "\n".join(lines) + "\n"


def power_settings(secs) -> Tuple[str, Optional[int], bool]:
    """(Schlüssel, Watt, Autotuning an?) – altes (psu_power_limit) und neues (power_target) Format."""
    at = secs.get("autotuning", {})
    fmt = str(value(secs.get("format", {}).get("version")) or "")
    if "power_target" in at or "mode" in at:
        key = "power_target"
    elif "psu_power_limit" in at:
        key = "psu_power_limit"
    else:
        key = "power_target" if fmt.startswith("2") else "psu_power_limit"
    val = value(at.get(key))
    watts = int(float(val)) if isinstance(val, (int, float)) else None
    return key, watts, bool(value(at.get("enabled", "false")))


def chain_settings(secs) -> Dict[int, bool]:
    chains: Dict[int, bool] = {}
    for name, vals in secs.items():
        m = re.fullmatch(r"hash_chain\.(\d+)", name)
        if m:
            chains[int(m.group(1))] = value(vals.get("enabled", "true")) is not False
    for cid in S9_CHAINS:
        chains.setdefault(cid, True)
    return dict(sorted(chains.items()))


def with_power(text: str, watts: int) -> str:
    """Leistungsgrenze setzen. Setzt immer autotuning.enabled = true (Autotuning wird nie abgeschaltet)."""
    secs = sections(text)
    key, _, _ = power_settings(secs)
    text = set_key(text, "autotuning", "enabled", "true")
    if key == "power_target" and "mode" in secs.get("autotuning", {}):
        text = set_key(text, "autotuning", "mode", "'power_target'")
    return set_key(text, "autotuning", key, str(int(watts)))
