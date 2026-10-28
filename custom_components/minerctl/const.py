"""Konstanten für die minerctl-Integration."""
DOMAIN = "minerctl"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 15          # Sekunden zwischen API-Abfragen
CONFIG_REFRESH = 60                 # Sekunden zwischen Config-Lesungen per SSH
DEFAULT_NAME = "S9"
DEFAULT_USER = "root"

POWER_MIN, POWER_MAX, POWER_STEP = 100, 1800, 10

# Presets: nur Leistungsgrenze in Watt. Autotuning bleibt immer an.
# Board-Auswahl entfällt – [hash_chain.N] enabled = false wirkt auf dem S9 nicht (siehe README).
# Realistischer Bereich mit 3 Boards ca. 400–1420 W (darunter greift der Tuner-Floor).
DEFAULT_PRESETS = {
    "eco":    {"label": "Eco",      "power": 400},
    "medium": {"label": "Medium",   "power": 700},
    "max":    {"label": "Maximum",  "power": 1420},
}
