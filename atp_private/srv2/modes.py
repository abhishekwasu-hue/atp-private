"""atp_private.srv2.modes - the owner's two agent modes for the 15M SRv2 bot (ATP ADR-0029, owner decision AGENT-MODES 20 Nov).

- `human_confirm` (the default when a deployment is created): the bot's setup goes to Trade's Vision, a Telegram card is sent, only the
  owner's ✅ places the entry; no ✅ before the card's deadline = no entry.
- `auto`: the bot places the entry itself when its rules (and Vision, when on) agree.

No new trading rule lives here. Each mode is a set of values of Trade's OWN Vision settings (`vision/config.py`, copied AS IS), and
Trade's own gate (`vision/gate.py`) applies them:

| ATP mode       | Vision | Trade settings written                                            | What Trade's gate then does                         |
|----------------|--------|-------------------------------------------------------------------|-----------------------------------------------------|
| human_confirm  | (any)  | vision_mode human_confirm, approval_required True                 | card + ✅ only from `telegram:<id>`; timeout = REJECTED |
| auto           | on     | vision_mode auto_veto, approval_required False, vision_fail_action skip | Vision's verdict decides (disagree = skip; Vision unavailable = skip) |
| auto           | off    | vision_mode off, approval_required False                          | the bot's own rules decide (full dashboard lots)    |

`vision_fail_action = skip` for `auto` with Vision on is the one value chosen here (Trade's default is `ignore`): "Vision agrees" cannot
be read from a Vision that did not answer. Logged as OPEN_QUESTIONS SRV2-Q5 (default: skip).

The switch is written through Trade's `VC.save`, which keeps its own change history (`vision_settings_history`); `apply()` also returns
an audit record (who, when, from -> to) for ATP's audit log. `auto` is refused unless the caller says the deployment is the owner's
(ATP enforces the organisation; this is the second lock). Exits never pass through this module or the gate (ADR-0004).
"""
from __future__ import annotations

import datetime as _dt

BOT = "srv2_momentum_reversal"
HUMAN_CONFIRM = "human_confirm"
AUTO = "auto"
MODES = (HUMAN_CONFIRM, AUTO)
DEFAULT = HUMAN_CONFIRM
# Trade's own setting keys this module writes (nothing else is touched)
KEYS = ("vision_mode", "approval_required", "vision_fail_action")


class ModeRefused(PermissionError):
    """The switch is not allowed (unknown mode, `auto` outside the owner's deployment, or no audited actor)."""


def trade_settings(mode, vision_on=True):
    """The Trade Vision setting values for an ATP agent mode (see the table above)."""
    if mode == HUMAN_CONFIRM:
        return {"vision_mode": "human_confirm", "approval_required": True}
    if mode == AUTO:
        if vision_on:
            return {"vision_mode": "auto_veto", "approval_required": False, "vision_fail_action": "skip"}
        return {"vision_mode": "off", "approval_required": False}
    raise ModeRefused(f"unknown agent mode {mode!r} - one of {MODES}")


def current(path=None):
    """(mode, vision_on) read back from Trade's stored Vision settings. Anything that is not exactly an `auto` row reads as
    human_confirm (fail-closed: an unreadable or hand-edited row never means auto)."""
    from atp_private.trade_engine.vision import config as VC
    try:
        s = VC.load(BOT, path)
    except Exception:                                                    # noqa: BLE001 - unreadable => the safe mode
        return HUMAN_CONFIRM, True
    if not s.get("approval_required", True):
        if s.get("vision_mode") == "auto_veto":
            return AUTO, True
        if s.get("vision_mode") == "off":
            return AUTO, False
    return HUMAN_CONFIRM, True


def apply(mode, by, owner_deployment, vision_on=True, path=None, trading_mode_fn=None, now=None):
    """Write the mode into Trade's Vision settings for the bot and return the audit record
    {"bot", "by", "at", "from", "to", "vision_on", "settings"}.

    - `by` (who switched; ATP's user id / name) is required: an unaudited switch is refused.
    - `auto` only with `owner_deployment=True` (ATP: the owner's organisation and his own deployment).
    - Switching TO human_confirm is always allowed (the safe direction)."""
    if mode not in MODES:
        raise ModeRefused(f"unknown agent mode {mode!r} - one of {MODES}")
    if not str(by or "").strip():
        raise ModeRefused("a mode switch needs the actor (by) for the audit")
    if mode == AUTO and owner_deployment is not True:
        raise ModeRefused("auto is the owner's own switch - refused for this deployment")
    from atp_private.trade_engine.vision import config as VC
    before = current(path)
    changes = trade_settings(mode, vision_on)
    if mode == HUMAN_CONFIRM:                                            # back to Trade's default fail rule
        changes = {**changes, "vision_fail_action": VC.BOT_DEFAULTS["vision_fail_action"]}
    saved = VC.save(BOT, changes, f"atp:{by}", path, trading_mode_fn=trading_mode_fn)
    at = now or _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")
    return {"bot": BOT, "by": str(by), "at": str(at), "from": before[0], "from_vision_on": before[1], "to": mode,
            "vision_on": bool(vision_on) if mode == AUTO else True, "settings": {k: saved.get(k) for k in KEYS}}


def ensure_default(by, path=None, trading_mode_fn=None):
    """A new deployment: write human_confirm unless the stored settings already hold a mode (never switches an existing auto row
    silently; that needs `apply`). Returns the audit record when written, else None."""
    from atp_private.trade_engine.vision import store as VS
    with VS.connect(path) as c:
        row = c.execute("SELECT 1 FROM vision_settings WHERE bot=?", (BOT,)).fetchone()
    if row is not None:
        return None
    return apply(HUMAN_CONFIRM, by, owner_deployment=False, path=path, trading_mode_fn=trading_mode_fn)


CARD_FIELDS = ("signal_id", "symbol", "direction", "level", "setup_tf", "signal_ts", "created_at", "status", "verdict", "deadline",
               "decided_at", "decided_by", "decision_reason", "executed_at", "exec_note")


def cards(limit=50, path=None):
    """Read-only: the bot's latest Vision cards (newest first) for ATP's card-status list - Trade's `vision_signals` rows, only the
    display fields (no images, no Vision text, no secrets). Statuses are Trade's own: QUEUED / RUNNING / PENDING_HUMAN / APPROVED /
    EXECUTED / REJECTED / SHADOWED / DRIFT_REJECTED / EXPIRED / DONE. An unreadable store returns [] (display only)."""
    from atp_private.trade_engine.vision import store as VS
    try:
        n = max(1, min(int(limit), 500))
        with VS.connect(path) as c:
            rows = c.execute(f"SELECT {', '.join(CARD_FIELDS)} FROM vision_signals WHERE bot=? ORDER BY created_at DESC LIMIT ?",
                             (BOT, n)).fetchall()
        return [dict(r) for r in rows]
    except Exception:                                                    # noqa: BLE001 - display only, never blocks
        return []
