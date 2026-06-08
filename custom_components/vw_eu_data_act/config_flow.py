"""Config flow for the Volkswagen EU Data Act integration.

Steps:
  user           -> email + password + brand; validates the EU Data Act login,
                    then starts the (optional) website-portal login.
  otp            -> shown only if the website portal requires email-OTP MFA.
  reauth_confirm -> re-enter password (e.g. after the portal SSO cookie expired).

The website portal is optional: if its login can't be completed the entry is
still created with the EU Data Act source only.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_BRAND,
    CONF_EMAIL,
    CONF_OTP,
    CONF_PASSWORD,
    CONF_WEBSITE_COOKIES,
    DOMAIN,
)
from .eu_data_act import (
    BRAND_CLIENT_IDS,
    DEFAULT_BRAND,
    EuDataActAuthError,
    EuDataActClient,
    EuDataActError,
)
from .website_portal import WebsitePortalClient, WebsitePortalError

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_BRAND, default=DEFAULT_BRAND): SelectSelector(
            SelectSelectorConfig(
                options=list(BRAND_CLIENT_IDS),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="brand",
            )
        ),
    }
)


class EuDataActConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._collected: dict[str, Any] = {}
        self._portal: WebsitePortalClient | None = None
        self._portal_ready = False
        self._is_reauth = False

    async def _validate_eudataact(self, data: dict[str, Any]) -> None:
        session = async_create_clientsession(self.hass, cookie_jar=aiohttp.CookieJar())
        client = EuDataActClient(
            session,
            email=data[CONF_EMAIL],
            password=data[CONF_PASSWORD],
            brand=data.get(CONF_BRAND, DEFAULT_BRAND),
        )
        await client.login()
        await client.list_vehicles()

    async def _start_portal(self) -> ConfigFlowResult:
        """Attempt the website-portal login; route to OTP step if required."""
        session = async_create_clientsession(self.hass, cookie_jar=aiohttp.CookieJar())
        self._portal = WebsitePortalClient(
            session, email=self._collected[CONF_EMAIL], password=self._collected[CONF_PASSWORD]
        )
        try:
            state = await self._portal.begin_login()
        except WebsitePortalError as err:
            _LOGGER.warning("Website portal login unavailable, continuing without it: %s", err)
            self._portal_ready = False
            return self._finish()
        if state == "otp_required":
            return self.async_show_form(
                step_id="otp", data_schema=vol.Schema({vol.Required(CONF_OTP): str})
            )
        self._portal_ready = True
        return self._finish()

    def _finish(self) -> ConfigFlowResult:
        data = dict(self._collected)
        if self._portal_ready and self._portal is not None:
            data[CONF_WEBSITE_COOKIES] = self._portal.export_cookies()
        if self._is_reauth:
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        return self.async_create_entry(title=self._collected[CONF_EMAIL], data=data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()
            try:
                await self._validate_eudataact(user_input)
            except EuDataActAuthError:
                errors["base"] = "invalid_auth"
            except EuDataActError:
                errors["base"] = "cannot_connect"
            else:
                self._collected = dict(user_input)
                return await self._start_portal()
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None and self._portal is not None:
            try:
                await self._portal.submit_otp(user_input[CONF_OTP].strip())
            except WebsitePortalError:
                errors["base"] = "invalid_otp"
            else:
                self._portal_ready = True
                return self._finish()
        return self.async_show_form(
            step_id="otp",
            data_schema=vol.Schema({vol.Required(CONF_OTP): str}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        self._is_reauth = True
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            self._collected = {**reauth_entry.data, **user_input}
            try:
                await self._validate_eudataact(self._collected)
            except EuDataActAuthError:
                errors["base"] = "invalid_auth"
            except EuDataActError:
                errors["base"] = "cannot_connect"
            else:
                return await self._start_portal()
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
        )
