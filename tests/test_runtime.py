from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import pytest
from custom_components.ha_agent import runtime as module

TEXT="<h2>Uge 45</h2><p>Torsdag læser vi side 10 og 11 (læselektie hjemme). Husk drikkedunk onsdag.</p>"
RESULT={"summary":"Eksempel","items":[{"title":"Læs side 10 og 11","kind":"homework","date":"2026-11-05","time":None,"action_required":True,"confidence":"high","source_quote":"Torsdag læser vi side 10 og 11 (læselektie hjemme)."}]}
class MemoryStore:
    saved={}
    def __init__(self,*args):pass
    async def async_load(self):return self.saved.get("data")
    async def async_save(self,data):self.saved["data"]=data.copy()
@pytest.fixture
def setup(monkeypatch):
    MemoryStore.saved={}
    monkeypatch.setattr(module,"Store",MemoryStore)
    monkeypatch.setattr(module,"async_dispatcher_send",lambda *args:None)
    monkeypatch.setattr(module.dt_util,"now",lambda:datetime(2026,11,1,tzinfo=timezone.utc))
    state=SimpleNamespace(state="available",attributes={"ugeplan_next":TEXT})
    hass=SimpleNamespace(states=SimpleNamespace(get=lambda entity:state))
    entry=SimpleNamespace(entry_id="fake",data={"source_entity":"sensor.example","week_offset":1},options={})
    client=SimpleNamespace(agent="HA",generate=AsyncMock(return_value={"data":RESULT,"response_id":"resp_fake","usage":{"input_tokens":10}}))
    return module.Runtime(hass,entry,client),state,client
@pytest.mark.asyncio
async def test_unchanged_source_is_not_billed_twice(setup):
    runtime,_,client=setup
    first=await runtime.analyze();second=await runtime.analyze()
    assert not first["cached"] and second["cached"] and client.generate.await_count==1
    assert first["reminders_enabled"] is False
@pytest.mark.asyncio
async def test_single_flight_concurrent_requests_are_deduplicated(setup):
    runtime,_,client=setup
    await asyncio.gather(runtime.analyze(),runtime.analyze())
    assert client.generate.await_count==1
@pytest.mark.asyncio
async def test_restart_reuses_persisted_preview(setup):
    runtime,_,client=setup
    await runtime.analyze()
    fresh=module.Runtime(runtime.hass,runtime.entry,client)
    await fresh.load()
    assert (await fresh.analyze())["cached"] and client.generate.await_count==1
@pytest.mark.asyncio
async def test_uncertain_failure_is_not_automatically_replayed(setup):
    runtime,_,client=setup
    client.generate.side_effect=TimeoutError("fixture")
    with pytest.raises(TimeoutError):await runtime.analyze()
    with pytest.raises(ValueError):await runtime.analyze()
    assert client.generate.await_count==1
@pytest.mark.asyncio
async def test_explicit_force_can_retry_a_failed_attempt(setup):
    runtime,_,client=setup
    client.generate.side_effect=TimeoutError("fixture")
    with pytest.raises(TimeoutError):await runtime.analyze()
    client.generate.side_effect=None
    assert not (await runtime.analyze(force=True))["cached"]
    assert client.generate.await_count==2
@pytest.mark.asyncio
async def test_invalid_evidence_does_not_replace_last_good_preview(setup):
    runtime,state,client=setup
    good=await runtime.analyze()
    state.attributes["ugeplan_next"]=TEXT+"<p>Changed.</p>"
    client.generate.return_value={"data":{"summary":"Bad","items":[{**RESULT["items"][0],"source_quote":"Invented"}]},"response_id":"resp_bad","usage":{}}
    with pytest.raises(ValueError):await runtime.analyze()
    assert runtime.preview["source_key"]==good["source_key"]
@pytest.mark.asyncio
async def test_unavailable_source_has_no_model_call(setup):
    runtime,state,client=setup
    state.state="unavailable"
    with pytest.raises(ValueError):await runtime.analyze()
    assert client.generate.await_count==0
