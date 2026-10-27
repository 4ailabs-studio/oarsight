import httpx
import pytest

from oarsight import api
from oarsight.api import ApiError, ChatClient, parse_json_content
from oarsight.usage import UsageLog, audio_cost, token_cost


def test_parse_json_tolerates_code_fences():
    assert parse_json_content('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_content('{"a": 1}') == {"a": 1}


def test_costs():
    assert token_cost("muse-wonder-1.0", 1_000_000, 0) == pytest.approx(4.0)
    assert token_cost("muse-spark-1.3", 1_000_000, 1_000_000, cached_tokens=1_000_000) == pytest.approx(0.15 + 4.25)
    assert token_cost("unknown-model", 10, 10) is None
    assert audio_cost(3600.9) == pytest.approx(0.18)


def _response(content='{"ok": true}', status=200):
    return httpx.Response(
        status,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                      "completion_tokens_details": {"reasoning_tokens": 40}},
        },
    )


def test_chat_json_logs_usage(tmp_path):
    transport = httpx.MockTransport(lambda request: _response())
    log = UsageLog(tmp_path / "usage.jsonl")
    client = ChatClient("k", usage=log, transport=transport)
    assert client.chat_json("stage", "muse-spark-1.3", "sys", "user") == {"ok": True}
    record = log.records[0]
    assert (record.input_tokens, record.output_tokens, record.reasoning_tokens) == (100, 50, 40)
    assert record.cost_usd == pytest.approx((100 * 1.25 + 50 * 4.25) / 1e6)
    assert (tmp_path / "usage.jsonl").read_text().count("\n") == 1


def test_cost_summary_flags_unpriced_calls():
    from oarsight.usage import CallRecord

    log = UsageLog()
    log.add(CallRecord("a", "muse-spark-1.3", 1.0, cost_usd=0.01))
    log.add(CallRecord("b", "meta-models/muse-spark-open-1026", 1.0, cost_usd=None))
    assert log.cost_summary() == "$0.0100 + 1 call(s) without a known price (billed by the provider)"


def test_retries_rate_limits_then_succeeds(monkeypatch):
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(429, headers={"retry-after": "0"}) if calls["n"] < 3 else _response()

    client = ChatClient("k", transport=httpx.MockTransport(handler))
    assert client.chat_json("s", "muse-spark-1.3", "sys", "user") == {"ok": True}
    assert calls["n"] == 3


def test_contributor_mode_models_are_refused_before_any_request():
    def handler(request):
        raise AssertionError("no request should be sent")

    client = ChatClient("k", transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="Contributor"):
        client.chat_json("s", "muse-spark-1.3-contributor", "sys", "user")


def test_client_errors_are_not_retried():
    client = ChatClient("k", transport=httpx.MockTransport(lambda r: httpx.Response(400, text="bad request")))
    with pytest.raises(ApiError) as exc:
        client.chat_json("s", "muse-spark-1.3", "sys", "user")
    assert exc.value.status == 400
