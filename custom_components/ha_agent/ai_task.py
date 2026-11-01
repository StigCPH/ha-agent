"""Reusable HA AI Task provider."""
import copy
import json
import probatio
from homeassistant.components import ai_task, conversation
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from .auth import AuthenticationError
from .client import ProviderError
from .entity import HAEntity

def strict_schema(schema):
    value = copy.deepcopy(schema)
    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                properties = node.setdefault("properties", {})
                required = set(node.get("required", []))
                for key, child in list(properties.items()):
                    if key not in required:
                        properties[key] = {"anyOf": [child, {"type": "null"}]}
                node["required"] = list(properties)
                node["additionalProperties"] = False
            for child in list(node.values()): visit(child)
        elif isinstance(node, list):
            for child in node: visit(child)
    visit(value)
    return value

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HATask(entry)])

class HATask(HAEntity, ai_task.AITaskEntity):
    _attr_name = "AI Task"
    _attr_supported_features = ai_task.AITaskEntityFeature.GENERATE_DATA

    def __init__(self, entry):
        self._configure(entry, "ai_task")

    async def _async_generate_data(self, task, chat_log):
        if task.llm_api is not None:
            raise HomeAssistantError("HA does not enable device-control tools in this version")
        schema = None
        if task.structure:
            schema = strict_schema(probatio.to_openapi(
                task.structure, custom_serializer=llm.selector_serializer, openapi_version="3.1.0",
            ))
        try:
            reply = await self.runtime.client.generate([{"role": "user", "content": task.instructions}], schema)
        except (AuthenticationError, ProviderError, ValueError) as error:
            raise HomeAssistantError(str(error)) from error
        text = reply["data"] if isinstance(reply["data"], str) else json.dumps(reply["data"], ensure_ascii=False)
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=self.entity_id, content=text),
        )
        return ai_task.GenDataTaskResult(conversation_id=chat_log.conversation_id, data=reply["data"])
