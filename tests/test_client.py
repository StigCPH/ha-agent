import pytest
from custom_components.ha_agent.client import project_url, parse_response, ProviderError, make_request
def response(text,**updates):
    return {"status":"completed","id":"resp_fake","output":[{"type":"message","content":[{"type":"output_text","text":text}]}],"usage":{"input_tokens":10},**updates}
def test_project_url_accepts_only_the_expected_azure_shape():
    assert project_url("https://example.services.ai.azure.com/api/projects/test/").endswith("/test")
    for value in ["http://example.services.ai.azure.com/api/projects/test","https://example.com/api/projects/test","https://user:pass@example.services.ai.azure.com/api/projects/test","https://example.services.ai.azure.com/api/projects/test?x=y","https://example.services.ai.azure.com/not-a-project"]:
        with pytest.raises(ValueError):project_url(value)
def test_completed_text_and_usage_are_preserved():
    result=parse_response(response("Hello"),False)
    assert result["data"]=="Hello" and result["usage"]["input_tokens"]==10 and result["response_id"]=="resp_fake"
def test_structured_json_is_parsed():
    value=response("",output=[{"type":"function_call","name":"ha_result","arguments":'{"items":[]}'}])
    assert parse_response(value,True)["data"]=={"items":[]}
def test_invalid_json_is_rejected():
    value=response("",output=[{"type":"function_call","name":"ha_result","arguments":"not JSON"}])
    with pytest.raises(ProviderError):parse_response(value,True)
def test_incomplete_results_are_not_treated_as_success():
    with pytest.raises(ProviderError):parse_response(response("partial",status="incomplete"),False)
def test_tools_are_not_executed_or_accepted():
    with pytest.raises(ProviderError):parse_response(response("",output=[{"type":"function_call","name":"turn_on"}]),False)
def test_request_has_no_device_tools_or_retry_instruction():
    body=make_request([{"role":"user","content":"Example"}],{"type":"object"})
    assert body["max_output_tokens"]==6000 and "tools" not in body and "text" not in body
    assert body["input"][0]["tools"][0]["strict"] and body["tool_choice"]["name"]=="ha_result"
    assert body["input"][-1]["type"]=="message"
def test_plain_conversation_messages_have_explicit_provider_type():
    assert make_request([{"role":"user","content":"Hello"}])["input"][0]["type"]=="message"
def test_other_tool_cannot_masquerade_as_a_typed_result():
    value=response("",output=[{"type":"function_call","name":"turn_on","arguments":"{}"}])
    with pytest.raises(ProviderError):parse_response(value,True)
def test_plain_message_is_not_accepted_as_a_forced_result():
    with pytest.raises(ProviderError):parse_response(response('{"items":[]}'),True)
