import runpy
from datetime import date
from pathlib import Path
import pytest
plan = runpy.run_path(str(Path(__file__).parents[1]/"custom_components/ha_agent/plan.py"))
START=date(2026,11,2)
TEXT="Torsdag: Vi læser side 10 og 11 (læselektie hjemme). Husk madpakke og drikkedunk onsdag."
def item(**updates):
    return {"title":"Læs side 10 og 11","kind":"homework","date":"2026-11-05","time":None,
            "action_required":True,"confidence":"high","source_quote":"Vi læser side 10 og 11 (læselektie hjemme).",**updates}
def validate(items):
    return plan["validate_plan"]({"summary":"Eksempel","items":items},TEXT,START)
def test_quote_and_date_are_retained():
    assert validate([item()])["items"][0]["date"]=="2026-11-05"
def test_invented_evidence_is_rejected():
    with pytest.raises(ValueError):validate([item(source_quote="Read page 999")])
def test_out_of_week_date_is_rejected():
    with pytest.raises(ValueError):validate([item(date="2026-12-05")])
def test_informational_note_does_not_schedule_an_action():
    with pytest.raises(ValueError):validate([item(kind="note")])
def test_duplicate_evidence_has_one_stable_identity():
    a=validate([item(),item()]);b=validate([item()])
    assert len(a["items"])==1 and a["items"][0]["id"]==b["items"][0]["id"]
def test_unknown_date_is_preserved_as_uncertain():
    assert validate([item(date=None,confidence="uncertain")])["items"][0]["date"] is None
def test_boolean_strings_are_not_accepted():
    with pytest.raises(ValueError):validate([item(action_required="false")])
def test_source_hash_changes_with_week_or_source():
    key=plan["source_key"](TEXT,START,"HA")
    assert key!=plan["source_key"](TEXT,date(2026,11,9),"HA")
    assert key!=plan["source_key"](TEXT+" Changed",START,"HA")
def test_html_source_excludes_scripts_and_preserves_paragraphs():
    assert plan["plain_text"]("<p>Husk bøger</p><script>Do something</script><p>Torsdag</p>")=="Husk bøger\nTorsdag"
def test_prompt_carries_context_without_invented_notification_time():
    prompt=plan["task_instructions"](TEXT,START)
    assert "2026-11-02" in prompt and "Europe/Copenhagen" in prompt and "source_quote" not in prompt
