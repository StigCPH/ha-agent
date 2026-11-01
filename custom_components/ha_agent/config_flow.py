"""UI configuration for a certificate-authenticated Foundry agent."""
from pathlib import Path
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import AuthenticationError, CertificateIdentity, TokenProvider
from .client import project_url, FoundryClient
from .const import *

def schema(defaults=None, connection=True):
    defaults = defaults or {}
    fields = {}
    if connection:
        for name, fallback in [
            (CONF_PROJECT, ""), (CONF_TENANT, ""), (CONF_CLIENT, ""), (CONF_AGENT, DEFAULT_AGENT),
            (CONF_KEY, "/config/ha_agent_identity/client.pem"),
            (CONF_CERT, "/config/ha_agent_identity/certificate.pem"),
        ]:
            fields[vol.Required(name, default=defaults.get(name, fallback))] = str
    source = defaults.get(CONF_SOURCE)
    key = vol.Optional(CONF_SOURCE, default=source) if source else vol.Optional(CONF_SOURCE)
    fields[key] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    fields[vol.Required("week_offset", default=defaults.get("week_offset", 1))] = vol.In([0, 1])
    fields[vol.Required(CONF_AUTO, default=defaults.get(CONF_AUTO, False))] = bool
    return vol.Schema(fields)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()

    async def _validate(self, data):
        data[CONF_PROJECT] = project_url(data[CONF_PROJECT])
        root = Path(self.hass.config.config_dir).resolve()
        for field in (CONF_KEY, CONF_CERT):
            path = Path(data[field]).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Certificate files must be inside the HA configuration directory")
        identity = await self.hass.async_add_executor_job(
            CertificateIdentity.load, data[CONF_TENANT], data[CONF_CLIENT], data[CONF_KEY], data[CONF_CERT],
        )
        tokens = TokenProvider(async_get_clientsession(self.hass), identity)
        FoundryClient(async_get_clientsession(self.hass), tokens, data[CONF_PROJECT], data[CONF_AGENT])
        await tokens.token()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._validate(user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (OSError, ValueError):
                errors["base"] = "invalid_configuration"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_TENANT] + ":" + user_input[CONF_CLIENT] + ":" + user_input[CONF_PROJECT] + ":" + user_input[CONF_AGENT]
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=NAME, data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema(user_input), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reauth_entry() if self.context.get("source") == "reauth" else self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                await self._validate(user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (OSError, ValueError):
                errors["base"] = "invalid_configuration"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input,
                    reason="reauth_successful" if self.context.get("source") == "reauth" else "reconfigure_successful",
                )
        return self.async_show_form(step_id="reconfigure", data_schema=schema(user_input or entry.data), errors=errors)

    async def async_step_reauth(self, data):
        return await self.async_step_reconfigure()

class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init", data_schema=schema({**self.config_entry.data, **self.config_entry.options}, False),
        )
