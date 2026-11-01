"""HA as a reusable, tool-free conversation agent."""
from homeassistant.components import conversation
from homeassistant.helpers import intent
from .auth import AuthenticationError
from .client import ProviderError
from .entity import HAEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HAConversation(entry)])

class HAConversation(HAEntity, conversation.ConversationEntity):
    _attr_name = None
    supported_languages = "*"

    def __init__(self, entry):
        self._configure(entry, "conversation")

    async def _async_handle_message(self, user_input, chat_log):
        messages = [{"role": item.role, "content": item.content}
                    for item in chat_log.content if item.role in ("user", "assistant") and item.content]
        messages = [{"role": "developer", "content": "Respond in the user's language: " + user_input.language}] + messages[-20:]
        response = intent.IntentResponse(language=user_input.language)
        try:
            reply = await self.runtime.client.generate(messages)
            text = reply["data"]
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(agent_id=self.entity_id, content=text),
            )
            response.async_set_speech(text)
        except (AuthenticationError, ProviderError, ValueError) as error:
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, str(error))
        return conversation.ConversationResult(response=response, conversation_id=chat_log.conversation_id)
