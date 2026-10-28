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
| Zustand | Sensor | läuft / gestoppt / änderung / nicht erreichbar, Attribute: Preset, letzter Fehler |
| Hashrate, Hashrate Durchschnitt | Sensor | TH/s gesamt |
| Board 6/7/8 Hashrate, Chiptemperatur | Sensor | je Board |
| Leistung | Sensor | geschätzter Verbrauch laut Miner (ohne Netzteilverluste) |
| Effizienz | Sensor | J/TH |
| Leistungsgrenze | Schieberegler | Watt setzen; Grenzen passen sich automatisch an die Zahl laufender Boards an (~130–470 W je Board) |
| Preset | Auswahl | Eco, Medium, Maximum (reine Leistungsstufen) |
| Mining | Schalter | bosminer stoppen/starten |
| Mining neu starten | Taste | bosminer neu starten |
| Original-Config wiederherstellen | Taste | standardmäßig deaktiviert |

Diagnose: Lüfter, Board-Temperatur, Pool, aktive Leistungsgrenze (inkl. Drosselung durch Dynamic Power Scaling).

## Modi (Presets)
Reine Leistungsstufen – Autotuning bleibt immer an, alle Boards laufen (siehe „Boards abschalten").
*Gerät → Integration „minerctl“ → Konfigurieren*: Watt je Modus und Abfrageintervall.

| Modus | Leistung |
|---|---|
| Eco | 400 W |
| Medium | 700 W |
| Maximum | 1420 W |

Nutzbarer Bereich mit 3 Boards ca. **400–1420 W**. Darunter erreicht der Tuner die Vorgabe nicht
(Floor ~380 W), deutlich höhere Werte bringen kaum mehr Hashrate.

Der Leistungs-Schieberegler erkennt automatisch die Zahl laufender Boards und passt seine Grenzen an
(~130–470 W je Board). Zu hohe Werte sind ungefährlich: Das Autotuning fährt ein Board nie über seinen
sicheren Punkt – ein unerreichbarer Zielwert läuft einfach am Board-Maximum.

## Boards abschalten (softwareseitig nicht möglich)
Auf dem getesteten S9 (Braiins OS / BOSer 0.1.0) wirkt das Abschalten einzelner Hashboards per
`[hash_chain.N] enabled = false` **nicht** – alle Boards hashen weiter (bestätigt per Kaltstart,
bosminer-Neustart und Braiins-Weboberfläche). Deshalb gibt es in HA **keine** Board-Schalter; gesteuert
wird nur die Leistung. Der Code dafür bleibt für andere Firmware/Modelle erhalten.

**Workaround für weniger Boards:** einzelne Hashboards **direkt am Miner physisch abstecken**
(Gerät vorher stromlos machen). Das ist aktuell der einzige verlässliche Weg zu 1- oder 2-Board-Betrieb.

**Mithelfen:** Du kennst einen funktionierenden Weg, Boards auf dieser BOS-Version per Software
abzuschalten? Bitte ein [Issue oder einen Pull Request](https://github.com/thisdev/minerctl-ha/issues)
öffnen oder melden – danke!

## Wichtig
- Jede Änderung startet bosminer neu (beim S9 ca. 30–60 s ohne Hashrate). Automationen daher mit Hysterese bauen.
- Vor jeder Änderung wird `/etc/bosminer.toml.bak` angelegt, vor der ersten zusätzlich `/etc/bosminer.toml.minerctl-orig`.
- Startet bosminer mit einer Änderung nicht, wird die vorherige Config automatisch wiederhergestellt.
- Der SSH-Host-Key wird nicht geprüft (gedacht für das eigene Heimnetz).
