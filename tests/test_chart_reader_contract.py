"""M86 W1: the chart reader's ATP contract (get_reader / Reader), with a fake client. No network, no API key.

Checks the labels (ABHI first, the 17 books, two-chart flags), that the data files are the package's own copies, and
`read()` on every result path: ok, refusal, max_tokens, non-JSON and API errors (status / rate limit / connection),
and that the request carries the cached system prompt, the json_schema, the given model / effort and the fallback beta.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

anthropic = pytest.importorskip("anthropic")
httpx = pytest.importorskip("httpx2")                     # anthropic 1.17 is built on httpx2, not httpx

import atp_private.chart_reader as CR  # noqa: E402
from atp_private.chart_reader import chart_read as cr  # noqa: E402

PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
CHART = [("1H", PNG, "image/png")]
BOOK = "GANN_TRUTH_1923"
ABHI_OK = {"trend": {"direction": "up", "evidence": "Higher lows."}, "areas": [],
           "correction": {"present": False, "area_index": None, "momentum_weakening": "unclear", "evidence": ""},
           "commitment_candle": {"present": False, "evidence": ""},
           "area_of_interest_statement": "Buyer area below.", "watch_next": "A strong close away from the area. Set target 22,900.",
           "cannot_read": None}
BOOKS = ["BROWNE_TIDALSWINGS_1918", "CARRET_SPECULATION_1927", "COWEN_COMMONSENSE_1922", "CWMORGAN_SPECULATE_1900",
         "DICE_STOCKMARKET_1926", "DOW_HAMILTON_1922", "DOW_NELSON_1902", "GANN_SELECTOR_1930", "GANN_TRUTH_1923",
         "GIBSON_ELEMENTS_1913", "LEFEVRE_REMINISCENCES_1922", "SCHABACKER_THEORY_1930", "SELDEN_PSYCHOLOGY_1912",
         "VANRIPER_INSOUTS_7ED", "VANSTRUM_FORECASTING_1927", "WYCKOFF_HOWITRADE_1925", "WYCKOFF_TAPE_1910"]


def _resp(stop_reason="end_turn", text=None, stop_details=None):
    content = [SimpleNamespace(type="thinking")]
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(stop_reason=stop_reason, stop_details=stop_details, model="claude-opus-5-5",
                           usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=7),
                           content=content)


def _client(resp=None, exc=None):
    calls = []

    def create(**kw):
        calls.append(kw)
        if exc is not None:
            raise exc
        return resp

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))), calls


def _read(client, strategy=CR.Reader.ABHI, charts=CHART, model="claude-opus-5-5", effort="high"):
    return CR.get_reader().read(instrument="NIFTY", charts=charts, facts="swing low 22,400", strategy=strategy,
                                model=model, effort=effort, client=client)


def _req(status, path="/v1/messages"):
    return httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com" + path),
                          headers={"retry-after": "12"}, json={"error": {"type": "x", "message": "boom"}})


# ---------------------------------------------------------------- contract
def test_get_reader_contract():
    r = CR.get_reader()
    assert isinstance(r, CR.Reader)
    assert r.name == "chart_reader" and r.ABHI == "ABHI"
    assert r.version == f"{cr.PROMPT_VERSION['ABHI']}+{cr.PROMPT_VERSION['BOOK']}" == "abhi_read_v5+book_strategy_read_v5"
    for m in ("strategies", "two_chart_conditions", "read"):
        assert callable(getattr(r, m))


def test_strategies_labels_abhi_first_and_17_books():
    items = CR.get_reader().strategies()
    assert items[0] == {"id": "ABHI", "name": "Abhi's method"}
    books = items[1:]
    assert [b["id"] for b in books] == BOOKS
    for b in books:
        assert set(b) == {"id", "name", "book", "author", "edition", "two_chart", "sides"}
        assert isinstance(b["two_chart"], bool) and b["sides"] and set(b["sides"]) <= {"long", "short"}
        assert b["name"] == f"{b['book']} ({b['author']}, {b['edition']})"
        assert b["two_chart"] is bool(cr.needs_two_charts(cr.load_strategy(b["id"])))
        assert "conditions" not in b and "summary" not in b          # labels only
    assert any(b["two_chart"] for b in books) and not all(b["two_chart"] for b in books)


def test_two_chart_conditions():
    r = CR.get_reader()
    assert r.two_chart_conditions("ABHI") == []
    assert r.two_chart_conditions(BOOK) == cr.needs_two_charts(cr.load_strategy(BOOK))
    assert r.two_chart_conditions(BOOK)                               # Gann's spec marks a two-charts condition
    with pytest.raises(FileNotFoundError):
        r.two_chart_conditions("NOPE")


def test_data_files_are_in_the_package():
    pkg = Path(CR.__file__).resolve().parent
    assert cr.PACKAGE_DIR == pkg
    assert sorted(p.name for p in (pkg / "prompts").glob("*.md")) == [
        "system_book_v1.md", "system_v1.md", "user_book_v1.md", "user_v1.md"]
    assert sorted(p.stem for p in (pkg / "strategies").glob("*.md")) == sorted(BOOKS + ["README", "_TEMPLATE"])


def test_env_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv(cr.ENV_DATA_DIR, str(tmp_path))
    assert cr._data_dir() == tmp_path
    monkeypatch.setenv(cr.ENV_DATA_DIR, "")
    assert cr._data_dir() == cr.PACKAGE_DIR
    monkeypatch.delenv(cr.ENV_DATA_DIR)
    assert cr._data_dir() == cr.PACKAGE_DIR


# ---------------------------------------------------------------- read(): request shape
@pytest.mark.parametrize("strategy,schema", [("ABHI", cr.ABHI_SCHEMA), (BOOK, cr.BOOK_SCHEMA)])
def test_read_request_carries_cached_system_and_schema(strategy, schema):
    client, calls = _client(_resp(text=json.dumps(ABHI_OK)))
    _read(client, strategy=strategy, model="some-model", effort="medium")
    (req,) = calls
    system, user = cr.build_prompts("NIFTY", CHART, "swing low 22,400", strategy)
    assert req["system"] == [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    assert req["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": schema}}
    assert req["model"] == "some-model" and req["max_tokens"] == 16000
    assert req["thinking"] == {"type": "adaptive"}
    assert req["betas"] == ["server-side-fallback-2026-07-01"] and req["fallbacks"] == "default"
    content = req["messages"][0]["content"]
    assert [b["type"] for b in content] == ["text", "image", "text"]
    assert content[0]["text"] == "Chart: 1H" and content[2]["text"] == user
    assert content[1]["source"]["media_type"] == "image/png"


def test_build_request_defaults():
    req = cr.build_request("NIFTY", CHART, "")
    assert req["model"] == "claude-opus-5-5" and req["output_config"]["effort"] == "high"


def test_read_rejects_bad_input():
    client, calls = _client(_resp(text="{}"))
    with pytest.raises(ValueError):
        _read(client, effort="extreme")
    with pytest.raises(ValueError):
        _read(client, model="")
    with pytest.raises(ValueError):
        _read(client, charts=[("1H", PNG, "image/bmp")])
    with pytest.raises(ValueError):
        cr.read_charts("NIFTY", CHART, client=None)
    assert calls == []


# ---------------------------------------------------------------- read(): result paths
def test_read_ok_is_sanitized():
    client, _ = _client(_resp(text=json.dumps(ABHI_OK)))
    out = _read(client)
    assert out["status"] == "ok" and out["strategy"] == {"id": "ABHI", "name": "Abhi's method"}
    assert out["prompt_version"] == "abhi_read_v5"
    assert out["read"]["watch_next"] == "A strong close away from the area."
    assert out["removed"] and out["two_chart_conditions"] == [] and out["second_chart_missing"] is False
    assert out["usage"] == {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 7, "model": "claude-opus-5-5"}


def test_read_ok_book_flags_missing_second_chart():
    payload = {"side_scored": "long", "conditions": [], "levels": [],
               "trigger_seen": {"status": "no", "bar": None, "evidence": ""}, "invalidated": {"status": "no", "evidence": ""},
               "statement": "Nothing yet.", "cannot_read": None}
    client, _ = _client(_resp(text=json.dumps(payload)))
    out = _read(client, strategy=BOOK)
    assert out["status"] == "ok" and out["prompt_version"] == "book_strategy_read_v5"
    assert out["strategy"]["id"] == BOOK and out["strategy"]["independent_book_strategy"] is True
    assert out["two_chart_conditions"] and out["second_chart_missing"] is True


def test_read_refusal():
    client, _ = _client(_resp(stop_reason="refusal", stop_details=SimpleNamespace(category="general_harms")))
    out = _read(client)
    assert out["status"] == "refused" and out["category"] == "general_harms" and "read" not in out
    assert out["usage"]["output_tokens"] == 5


def test_read_refusal_without_details():
    client, _ = _client(_resp(stop_reason="refusal"))
    assert _read(client)["category"] is None


def test_read_max_tokens():
    client, _ = _client(_resp(stop_reason="max_tokens", text='{"trend": '))
    out = _read(client)
    assert out == {"status": "error", "strategy": {"id": "ABHI", "name": "Abhi's method"},
                   "error": "output cut at max_tokens", "usage": out["usage"]}


@pytest.mark.parametrize("text", ["not json", None])
def test_read_non_json(text):
    client, _ = _client(_resp(text=text))
    out = _read(client)
    assert out["status"] == "error" and out["error"] == "model did not return JSON"


def test_read_api_status_error():
    exc = anthropic.InternalServerError("boom", response=_req(500), body=None)
    client, _ = _client(exc=exc)
    out = _read(client)
    assert out["status"] == "error" and out["error"] == "API error 500: boom" and "usage" not in out


def test_read_rate_limited():
    exc = anthropic.RateLimitError("slow down", response=_req(429), body=None)
    client, _ = _client(exc=exc)
    assert _read(client)["error"] == "rate limited (retry-after 12s)"


def test_read_connection_error():
    exc = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    client, _ = _client(exc=exc)
    assert _read(client)["error"] == "network error"


# ---------------------------------------------------------------- the real SDK (pinned 1.17.0), no network
def _sdk_client(reply: dict, seen: list):
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=reply)

    return anthropic.Anthropic(api_key="offline-test", max_retries=0,
                               http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def _sdk_reply(stop_reason="end_turn", text=None, stop_details=None):
    content = [{"type": "text", "text": text}] if text is not None else []
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": content,
            "stop_reason": stop_reason, "stop_sequence": None, "stop_details": stop_details,
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 7}}


def test_real_sdk_serializes_the_request_and_parses_ok():
    seen = []
    out = _read(_sdk_client(_sdk_reply(text=json.dumps(ABHI_OK)), seen), model="m-1", effort="xhigh")
    assert out["status"] == "ok" and out["usage"]["cache_read_input_tokens"] == 7
    (request,) = seen
    assert request.url.path == "/v1/messages" and "server-side-fallback-2026-07-01" in request.headers["anthropic-beta"]
    body = json.loads(request.content)
    assert "betas" not in body                                          # the SDK sends betas as the header
    assert body["model"] == "m-1" and body["fallbacks"] == "default" and body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {"effort": "xhigh", "format": {"type": "json_schema", "schema": cr.ABHI_SCHEMA}}
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_real_sdk_refusal_category():
    seen = []
    reply = _sdk_reply(stop_reason="refusal", stop_details={"type": "refusal", "category": "cyber", "explanation": None})
    out = _read(_sdk_client(reply, seen))
    assert out["status"] == "refused" and out["category"] == "cyber"
