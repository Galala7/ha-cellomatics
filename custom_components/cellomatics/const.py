"""Constants for the Cellomatics Irrigation integration."""

DOMAIN = "cellomatics"

CONF_SITE_ID = "site_id"
CONF_VALVE_COUNT = "valve_count"

# Per-counter pulse-to-litre conversion factors. Each pulse from the
# controller's flow meter represents this many litres. Values vary by meter:
# confirmed as 10 L/pulse for main and zone 2, 1 L/pulse for fertilizer.
CONF_PULSE_FACTOR_MAIN = "pulse_factor_main"
CONF_PULSE_FACTOR_ZONE2 = "pulse_factor_zone2"
CONF_PULSE_FACTOR_FERT = "pulse_factor_fert"

# Cellomatics controllers support 4-6 valves; 6 is used as a safe default
# for existing config entries created before valve count detection was added.
DEFAULT_VALVE_COUNT = 6
DEFAULT_PULSE_FACTOR_MAIN = 10
DEFAULT_PULSE_FACTOR_ZONE2 = 10
DEFAULT_PULSE_FACTOR_FERT = 1

BASE_URL = "https://www.cellomatics.com"
