"""Constants for the Volkswagen Connect integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "volkswagen_connect"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_BRAND = "brand"
CONF_OTP = "otp"
# Persisted website-portal session cookies (enables the optional authproxy
# data source + silent refresh across restarts).
CONF_WEBSITE_COOKIES = "website_cookies"

# Polling cadence. The portal delivers at most one dataset per 15 min, so there
# is no value in polling faster; we add a small offset to avoid hammering on the
# exact slot boundary.
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

# Vehicle "status" sensor states
STATUS_OK = "ok"
STATUS_NO_DATA = "no_data"
STATUS_NOT_CONFIGURED = "not_configured"
