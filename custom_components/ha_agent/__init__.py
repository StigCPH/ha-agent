"""HA: Foundry-backed AI Task, conversation and school-plan previews."""
import asyncio
import logging
import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from .auth import AuthenticationError, CertificateIdentity, TokenProvider
from .client import FoundryClient, ProviderError
from .const import *
from .runtime import Runtime

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.AI_TASK, Platform.CONVERSATION, Platform.SENSOR, Platform.BUTTON]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    settings = {**entry.data, **entry.options}
    try:
        identity = await hass.async_add_executor_job(
            CertificateIdentity.load, settings[CONF_TENANT], settings[CONF_CLIENT],
            settings[CONF_KEY], settings[CONF_CERT],
        )
        tokens = TokenProvider(async_get_clientsession(hass), identity)
        await tokens.token()
    except AuthenticationError as error:
        raise ConfigEntryAuthFailed(str(error)) from error
    except (OSError, ValueError, TimeoutError, aiohttp.ClientError) as error:
        raise ConfigEntryNotReady("HA identity is unavailable") from error
    client = FoundryClient(async_get_clientsession(hass), tokens, settings[CONF_PROJECT], settings[CONF_AGENT])
    runtime = Runtime(hass, entry, client)
    await runtime.load()
    entry.runtime_data = runtime
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, "analyze_weekplan"):
        async def analyze(call: ServiceCall):
            entries = hass.data.get(DOMAIN, {})
            entry_id = call.data.get("entry_id")
            if entry_id:
                selected = entries.get(entry_id)
            else:
                selected = next(iter(entries.values())) if len(entries) == 1 else None
            if selected is None:
                raise HomeAssistantError("Select one HA config entry")
            try:
                return await selected.analyze(
                    call.data.get("source_entity"), call.data.get("week_offset"), call.data.get("force", False),
                )
            except (AuthenticationError, ProviderError, ValueError) as error:
                raise HomeAssistantError(str(error)) from error
        hass.services.async_register(
            DOMAIN, "analyze_weekplan", analyze,
            schema=vol.Schema({
                vol.Optional("entry_id"): cv.string,
                vol.Optional("source_entity"): cv.entity_id,
                vol.Optional("week_offset"): vol.All(vol.Coerce(int), vol.In([0, 1])),
                vol.Optional("force", default=False): cv.boolean,
            }), supports_response=SupportsResponse.ONLY,
        )
    if settings.get(CONF_AUTO) and settings.get(CONF_SOURCE):
        async def analyze_changed():
            try:
                await runtime.analyze()
            except Exception as error:
                _LOGGER.warning("HA automatic preview was not updated: %s", type(error).__name__)
        @callback
        def changed(event):
            hass.async_create_task(analyze_changed())
        entry.async_on_unload(async_track_state_change_event(hass, [settings[CONF_SOURCE]], changed))
    return True

async def _options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "analyze_weekplan")
    return True
