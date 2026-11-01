"""Shared entity identity."""
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, NAME

class HAEntity:
    _attr_has_entity_name = True
    def _configure(self, entry, suffix):
        self.entry = entry
        self.runtime = entry.runtime_data
        self._attr_unique_id = entry.entry_id + "_" + suffix
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=NAME,
            manufacturer="Microsoft Foundry", model=self.runtime.client.agent,
        )
