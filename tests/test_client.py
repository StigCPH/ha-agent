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
    assert parse_response(response('{"items":[]}'),True)["data"]=={"items":[]}
def test_invalid_json_is_rejected():
    with pytest.raises(ProviderError):parse_response(response("not JSON"),True)
def test_incomplete_results_are_not_treated_as_success():
    with pytest.raises(ProviderError):parse_response(response("partial",status="incomplete"),False)
def test_tools_are_not_executed_or_accepted():
    with pytest.raises(ProviderError):parse_response(response("",output=[{"type":"function_call","name":"turn_on"}]),False)
def test_request_has_no_device_tools_or_retry_instruction():
    body=make_request([{"role":"user","content":"Example"}],{"type":"object"})
    assert body["max_output_tokens"]==6000 and "tools" not in body and body["text"]["format"]["strict"]
