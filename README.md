# minerctl für Home Assistant

Steuert einen Antminer S9 (und andere Antminer) mit **Braiins OS** direkt aus Home Assistant.
Status über die Miner-API (Port 4028), Änderungen über SSH (Port 22).

## Installation

**Installation über HACS:**
1. HACS → oben rechts *⋮* → *Benutzerdefinierte Repositories*.
2. Repository `https://github.com/thisdev/minerctl-ha`, Typ *Integration*, hinzufügen.
3. „minerctl" suchen, *Herunterladen*, danach Home Assistant neu starten.

## Einrichten
*Einstellungen → Geräte & Dienste → Integration hinzufügen → „minerctl“*
- IP-Adresse des Miners, Name (z. B. S9)
- SSH-Benutzer `root`, Passwort leer lassen, wenn Braiins OS keins hat

## Entitäten

| Entität | Typ | Funktion |
|---|---|---|
| Zustand | Sensor | läuft / gestoppt / änderung / nicht erreichbar, Attribute: Preset, aktive Boards, letzter Fehler |
| Hashrate, Hashrate Durchschnitt | Sensor | TH/s gesamt |
| Board 6/7/8 Hashrate, Chiptemperatur | Sensor | je Board |
| Leistung | Sensor | geschätzter Verbrauch laut Miner (ohne Netzteilverluste) |
| Effizienz | Sensor | J/TH |
| Leistungsgrenze | Zahl | 100–1800 W setzen |
| Preset | Auswahl | Minimum, Minimum 2, Medium, Maximum |
| Mining | Schalter | bosminer stoppen/starten |
| Board 6/7/8 | Schalter | einzelne Boards an/aus (mindestens eins bleibt an) |
| Mining neu starten | Taste | bosminer neu starten |
| Original-Config wiederherstellen | Taste | standardmäßig deaktiviert |

Diagnose: Lüfter, Board-Temperatur, Pool, aktive Leistungsgrenze (inkl. Drosselung durch Dynamic Power Scaling).

## Presets anpassen
*Gerät → Integration „minerctl“ → Konfigurieren*: Boards (z. B. `6, 8`) und Watt je Preset, Abfrageintervall.

| Preset | Boards | Leistung |
|---|---|---|
| Minimum | 7 | 150 W |
| Minimum 2 | 7 | 200 W |
| Medium | 6, 8 | 700 W |
| Maximum | 6, 7, 8 | 1420 W |

## Wichtig
- Jede Änderung startet bosminer neu (beim S9 ca. 30–60 s ohne Hashrate). Automationen daher mit Hysterese bauen.
- Vor jeder Änderung wird `/etc/bosminer.toml.bak` angelegt, vor der ersten zusätzlich `/etc/bosminer.toml.minerctl-orig`.
- Startet bosminer mit einer Änderung nicht, wird die vorherige Config automatisch wiederhergestellt.
- Der SSH-Host-Key wird nicht geprüft (gedacht für das eigene Heimnetz).
