"""Persistent previews and single-flight school-plan analysis."""
import asyncio
from datetime import timedelta
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SIGNAL
from .plan import plain_text, source_key, task_instructions, validate_plan, PLAN_SCHEMA

class Runtime:
    def __init__(self, hass: HomeAssistant, entry, client):
        self.hass, self.entry, self.client = hass, entry, client
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.preview")
        self.preview: dict[str, Any] = {}
        self.attempts: dict[str, str] = {}
        self.last_response: dict[str, Any] = {}
        self.lock = asyncio.Lock()

    async def load(self):
        saved = await self.store.async_load() or {}
        self.preview = saved.get("preview", {})
        self.attempts = saved.get("attempts", {})
        self.last_response = saved.get("last_response", {})

    async def save(self):
        await self.store.async_save({"preview": self.preview, "attempts": self.attempts, "last_response": self.last_response})
        async_dispatcher_send(self.hass, SIGNAL + self.entry.entry_id)

    async def analyze(self, source_entity=None, week_offset=None, force=False):
        async with self.lock:
            settings = {**self.entry.data, **self.entry.options}
            entity = source_entity or settings.get("source_entity")
            if not entity:
                raise ValueError("Choose a school-plan source entity first")
            offset = settings.get("week_offset", 1) if week_offset is None else week_offset
            if offset not in (0, 1):
                raise ValueError("Week offset must be 0 or 1")
            attribute = "ugeplan_next" if offset else "ugeplan"
            state = self.hass.states.get(entity)
            raw = state.attributes.get(attribute) if state else None
            if not isinstance(raw, str) or state.state in ("unavailable", "unknown"):
                raise ValueError("The selected school plan is unavailable")
            text = plain_text(raw)
            if len(text) < 40 or len(text) > 40000:
                raise ValueError("The school plan is empty or too large")
            today = dt_util.now().date()
            start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
            key = source_key(text, start, self.client.agent)
            if self.preview.get("source_key") == key and not force:
                return {**self.preview, "cached": True}
            if key in self.attempts and not force:
                raise ValueError("This source already has an unfinished/failed attempt. Review it before explicitly retrying with force.")
            self.attempts[key] = "pending"
            # Bound retained attempts; no source text or tokens are stored here.
            self.attempts = dict(list(self.attempts.items())[-30:])
            await self.save()
            try:
                reply = await self.client.generate(
                    [{"role": "user", "content": task_instructions(text, start)}], PLAN_SCHEMA,
                )
                # Retain a completed provider response before semantic validation,
                # so rejected evidence can be reviewed without another paid call.
                self.last_response = {**reply, "source_key": key}
                await self.save()
                result = validate_plan(reply["data"], text, start)
                self.preview = {
                    **result, "source_key": key, "source_entity": entity,
                    "source_attribute": attribute, "analyzed_at": dt_util.utcnow().isoformat(),
                    "response_id": reply["response_id"], "usage": reply["usage"],
                    "reminders_enabled": False,
                }
                self.attempts.pop(key, None)
            except Exception:
                self.attempts[key] = "failed_or_uncertain"
                await self.save()
                raise
            await self.save()
            return {**self.preview, "cached": False}
