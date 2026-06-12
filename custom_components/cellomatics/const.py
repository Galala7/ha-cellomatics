"""Constants for the Cellomatics Irrigation integration."""

DOMAIN = "cellomatics"

CONF_SITE_ID = "site_id"
CONF_VALVE_COUNT = "valve_count"

# Cellomatics controllers support 4-6 valves; 6 is used as a safe default
# for existing config entries created before valve count detection was added.
DEFAULT_VALVE_COUNT = 6

BASE_URL = "https://www.cellomatics.com"
