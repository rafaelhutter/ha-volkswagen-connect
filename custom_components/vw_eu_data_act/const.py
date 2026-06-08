"""Constants for the Volkswagen EU Data Act integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "vw_eu_data_act"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_BRAND = "brand"

# Polling cadence. The portal delivers at most one dataset per 15 min, so there
# is no value in polling faster; we add a small offset to avoid hammering on the
# exact slot boundary.
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

# Vehicle "status" sensor states
STATUS_OK = "ok"
STATUS_NO_DATA = "no_data"
STATUS_NOT_CONFIGURED = "not_configured"
