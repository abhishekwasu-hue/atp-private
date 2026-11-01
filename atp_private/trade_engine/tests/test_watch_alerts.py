"""EN1 WATCH alerts on Telegram (DECISIONS 118 / 119, M53 INFO tier): a model firing without the full required set ⇒ one plain line per
new (symbol · visit · model), at most once a day; no card, no position; the missing piece in words, never a raw code."""
import json

import atp_private.trade_engine.engine_signal as ES

W = {"model": "E2", "name": "Confirmation", "direction": -1, "visit_id": "1H:H:2030-01-07 09:15@2030-01-08 10:00",
     "watch_why": "required set incomplete — no_handover", "area": {"id": 3, "lo": 55699.45, "hi": 55970.15, "role": "resistance"}}


def test_watch_text_is_plain_words():
    t = ES.watch_text("banknifty", W)
    assert t.startswith("ℹ️ WATCH · BANKNIFTY bear call (Confirmation) · area 55,699–55,970")
    assert "no handover seen" in t and "no_handover" not in t and "Action: none" in t
    en3 = {**W, "watch_why": "one entry per cluster per visit (EN3) — this place was entered earlier in the visit", "direction": 1}
    assert "bull put" in ES.watch_text("NIFTY", en3) and "one entry per cluster" in ES.watch_text("NIFTY", en3)


def test_alert_watch_once_per_visit_and_model_per_day(tmp_path):
    p, sent = str(tmp_path / "alerts.json"), []
    send = lambda m: sent.append(m) or True                                # noqa: E731
    assert ES.alert_watch("BANKNIFTY", [W], send=send, state_path=p, now="2030-01-08 10:05") == 1
    assert ES.alert_watch("BANKNIFTY", [W], send=send, state_path=p, now="2030-01-08 10:10") == 0     # same visit + model ⇒ once
    assert ES.alert_watch("BANKNIFTY", [{**W, "model": "E3"}], send=send, state_path=p, now="2030-01-08 10:10") == 1
    assert ES.alert_watch("BANKNIFTY", [W], send=send, state_path=p, now="2030-01-09 10:05") == 1     # a new day
    assert len(sent) == 3 and json.load(open(p))["_watch"]["_day"] == "2030-01-09"


def test_a_failed_send_is_retried_and_never_raises(tmp_path):
    p = str(tmp_path / "alerts.json")
    def boom(m):
        raise RuntimeError("telegram down")
    assert ES.alert_watch("NIFTY", [W], send=boom, state_path=p, now="2030-01-08 10:05") == 0
    assert ES.alert_watch("NIFTY", [W], send=lambda m: True, state_path=p, now="2030-01-08 10:06") == 1


def test_heartbeat_once_a_day_and_silent_line(tmp_path):
    """M53 MS-6: one quiet "bot alive" line a day."""
    p, sent = str(tmp_path / "alerts.json"), []
    send = lambda m: sent.append(m) or True                                # noqa: E731
    assert ES.alert_heartbeat(["NIFTY", "BANKNIFTY"], send=send, state_path=p, now="2030-01-08 09:31")
    assert not ES.alert_heartbeat(["NIFTY", "BANKNIFTY"], send=send, state_path=p, now="2030-01-08 09:46")
    assert ES.alert_heartbeat(["NIFTY"], send=send, state_path=p, now="2030-01-09 09:31")
    assert len(sent) == 2 and sent[0].startswith("🟢 Bot चालू · NIFTY / BANKNIFTY · PAPER")
