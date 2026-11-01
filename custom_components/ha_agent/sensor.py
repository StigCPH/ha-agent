"""Persistent school-plan preview."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import SIGNAL
from .entity import HAEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SchoolPlanSensor(entry)])

class SchoolPlanSensor(HAEntity, SensorEntity):
    _attr_name = "School plan"
    _attr_icon = "mdi:clipboard-text-outline"
    _attr_should_poll = False
    def __init__(self, entry):
        self._configure(entry, "school_plan")
    @property
    def native_value(self):
        return len(self.runtime.preview.get("items", []))
    @property
    def extra_state_attributes(self):
        return {**self.runtime.preview, "preview_only": True,
                "pending_or_failed_attempts": len(self.runtime.attempts)}
    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL + self.entry.entry_id, self.async_write_ha_state,
        ))
