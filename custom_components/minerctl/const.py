"""Konstanten für die minerctl-Integration."""
DOMAIN = "minerctl"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 15          # Sekunden zwischen API-Abfragen
CONFIG_REFRESH = 60                 # Sekunden zwischen Config-Lesungen per SSH
DEFAULT_NAME = "S9"
DEFAULT_USER = "root"

POWER_MIN, POWER_MAX, POWER_STEP = 100, 1800, 10

# Presets: aktive Boards + Leistungsgrenze in Watt. Autotuning bleibt immer an.
DEFAULT_PRESETS = {
    "min":    {"label": "Minimum",   "boards": [7],       "power": 150},
    "min2":   {"label": "Minimum 2", "boards": [7],       "power": 200},
    "medium": {"label": "Medium",    "boards": [6, 8],    "power": 700},
    "max":    {"label": "Maximum",   "boards": [6, 7, 8], "power": 1420},
}
