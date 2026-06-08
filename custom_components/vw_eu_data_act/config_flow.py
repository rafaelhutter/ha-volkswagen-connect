"""Config flow for the Volkswagen EU Data Act integration."""

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

from .const import CONF_BRAND, CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .eu_data_act import (
    BRAND_CLIENT_IDS,
    DEFAULT_BRAND,
    EuDataActAuthError,
    EuDataActClient,
    EuDataActError,
)

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


async def _validate(hass, data: dict[str, Any]) -> None:
    """Validate credentials by logging in and listing vehicles."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    client = EuDataActClient(
        session,
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        brand=data.get(CONF_BRAND, DEFAULT_BRAND),
    )
    await client.login()
    await client.list_vehicles()


class EuDataActConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()
            try:
                await _validate(self.hass, user_input)
            except EuDataActAuthError as err:
                _LOGGER.debug("EU Data Act auth failed: %s", err)
                errors["base"] = "invalid_auth"
            except EuDataActError as err:
                _LOGGER.debug("EU Data Act cannot connect: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            new_data = {**reauth_entry.data, **user_input}
            try:
                await _validate(self.hass, new_data)
            except EuDataActAuthError:
                errors["base"] = "invalid_auth"
            except EuDataActError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data=new_data
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
        )
