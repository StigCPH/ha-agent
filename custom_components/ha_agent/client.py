"""Bounded, tool-free calls to a Foundry agent's own endpoint."""
import json
from urllib.parse import quote, urlsplit

import aiohttp
from .auth import AuthenticationError
from .const import API_VERSION

class ProviderError(Exception):
    """Sanitized provider failure; callers must not blindly replay an uncertain call."""

def project_url(value):
    parts = urlsplit(value.strip().rstrip("/"))
    if (parts.scheme != "https" or not parts.hostname
        or not parts.hostname.endswith(".services.ai.azure.com")
        or parts.username or parts.password or parts.port not in (None, 443)
        or parts.query or parts.fragment
        or len(parts.path.split("/")) != 4 or not parts.path.startswith("/api/projects/")
        or not parts.path.split("/")[-1]):
        raise ValueError("Use an HTTPS Microsoft Foundry project endpoint")
    return parts.geturl().rstrip("/")

def make_request(messages, structure=None):
    body = {"input": messages, "max_output_tokens": 6000, "store": True}
    if structure is not None:
        body["text"] = {"format": {"type": "json_schema", "name": "ha_agent_result",
                                  "strict": True, "schema": structure}}
    return body

def parse_response(data, structured):
    if data.get("status") != "completed":
        raise ProviderError("Foundry did not complete this response; it was not retried")
    outputs = data.get("output", [])
    if any(o.get("type") in ("function_call", "mcp_call", "computer_call") for o in outputs):
        raise ProviderError("The agent requested an unsupported action; nothing was executed")
    text = "".join(
        block.get("text", "") for output in outputs if output.get("type") == "message"
        for block in output.get("content", []) if block.get("type") == "output_text"
    )
    if not text.strip():
        raise ProviderError("Foundry returned no answer")
    if structured:
        try:
            value = json.loads(text)
        except (ValueError, TypeError) as error:
            raise ProviderError("Foundry returned invalid structured output") from error
    else:
        value = text
    return {"data": value, "response_id": data.get("id"), "usage": data.get("usage", {})}

class FoundryClient:
    def __init__(self, session, tokens, endpoint, agent):
        self.session, self.tokens = session, tokens
        self.endpoint = project_url(endpoint)
        if not agent or len(agent) > 63 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in agent):
            raise ValueError("Invalid Foundry agent name")
        self.agent = agent
        self.url = self.endpoint + "/agents/" + quote(agent, safe="") + "/endpoint/protocols/openai/responses?api-version=" + API_VERSION

    async def generate(self, messages, structure=None):
        if sum(len(str(m.get("content", ""))) for m in messages) > 60000:
            raise ValueError("The task is too large")
        token = await self.tokens.token()
        try:
            async with self.session.post(
                self.url, json=make_request(messages, structure),
                headers={"Authorization": "Bearer " + token,
                         "Foundry-Features": "AgentEndpoints=V1Preview"},
                timeout=aiohttp.ClientTimeout(total=120), allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise AuthenticationError(f"Foundry denied this agent connection (HTTP {response.status})")
                if response.status != 200:
                    raise ProviderError(f"Foundry returned HTTP {response.status}; the call was not retried")
                data = await response.json()
        except (aiohttp.ClientError, TimeoutError) as error:
            raise ProviderError("Foundry connection interrupted; delivery is uncertain and the call was not retried") from error
        return parse_response(data, structure is not None)
