"""Manual, cached school-plan analysis."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from .auth import AuthenticationError
from .client import ProviderError
from .entity import HAEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AnalyzeButton(entry)])

class AnalyzeButton(HAEntity, ButtonEntity):
    _attr_name = "Analyze weekplan"
    _attr_icon = "mdi:calendar-search"
    def __init__(self, entry):
        self._configure(entry, "analyze_weekplan")
    async def async_press(self):
        try:
            await self.runtime.analyze()
        except (AuthenticationError, ProviderError, ValueError) as error:
            raise HomeAssistantError(str(error)) from error
