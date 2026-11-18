"""Stand-in for Trade's `notifications` (Telegram) - owner order SRV2, 18 Nov. The send goes to the owner's linked Telegram chat through
ATP (`send` adapter); the text, the policy, the local log, the cool-down and the heartbeat are Trade 813358b notifications.py, verbatim
apart from the folder (Trade's `data/` next to the code => the bot's state folder `config.DATA_DIR` on ATP's data volume)."""
import datetime
import json
import os

import requests

from atp_private.srv2 import host as _H

__srv2_io__ = True


def _data():
    from atp_private.trade_engine.config import DATA_DIR
    return DATA_DIR


def _p(*parts):
    return os.path.join(_data(), *parts)


def _load_telegram_credentials():
    """notifications._load_telegram_credentials (Trade L57-74), the environment part: the bot's own Telegram bot (TELEGRAM_BOT_TOKEN /
    TELEGRAM_CHAT_ID in the worker's environment, set from SRV2_TELEGRAM_* in ATP's .env). Trade's config-file / .env-file fallbacks
    are not used in ATP. (None, None) when not set."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        return token, chat_id
    return None, None


def send_telegram_message(message, timeout=10, silent=False, kind=None):
    """Trade L76-99: through the bot's own Telegram bot when its credentials are set (Trade's code, verbatim); otherwise through
    ATP to the owner's linked chat (`send` adapter). Never raises."""
    message = _plain(message)
    go, silent = _policy(kind, silent)
    _log_locally(tag(kind, go, silent) + message)
    if not go:
        return True
    token, chat_id = _load_telegram_credentials()
    if not token or not chat_id:
        try:
            return bool(_H.need("send")(message, silent, kind))
        except Exception:                                               # noqa: BLE001 - Trade: any failure => False
            return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML", **({"disable_notification": True} if silent else {})},
            timeout=timeout,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _plain(text):
    """N11: the outgoing text without internal words (bots_common.plain_text.dejargon); any failure ⇒ the text as is."""
    try:
        from atp_private.trade_engine.bots_common import plain_text as PT
        return PT.dejargon(text)
    except Exception:                                                    # noqa: BLE001 — display only
        return text


def _policy(kind, silent):
    """(send?, silent?) from notify_policy (N1); a policy failure never blocks a message (send, as asked)."""
    try:
        from atp_private.trade_engine import notify_policy
        return notify_policy.resolve(kind, silent)
    except Exception:                                                    # noqa: BLE001
        return True, bool(silent)



def tag(kind, go, silent):
    """The log prefix of one Telegram send (N1 proof: count per type, sound / silent / off) — "{tg:<type>:<sound|silent|off>} "."""
    return "{tg:" + (kind or "other") + ":" + ("off" if not go else "silent" if silent else "sound") + "} "



def send_telegram_photo(png_bytes, caption, timeout=20, silent=False, kind=None):
    """Chart image + caption (HTML, Telegram मर्यादा 1024 chars) — Vision V0 साठी. send_telegram_message सारखंच: कधीच raise नाही,
    credentials नसतील तर फक्त local log. Image नसेल (None) तर फक्त text संदेश."""
    if not png_bytes:
        return send_telegram_message(caption, timeout=timeout, silent=silent, kind=kind)
    caption = _plain(caption)                                           # N11: no internal words
    go, silent = _policy(kind, silent)
    _log_locally(tag(kind, go, silent) + "[photo] " + caption)
    if not go:
        return True
    token, chat_id = _load_telegram_credentials()
    if not token or not chat_id:
        return False
    quiet = {"disable_notification": "true"} if silent else {}
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "HTML", **quiet},
            files={"photo": ("chart.png", png_bytes, "image/png")},
            timeout=timeout,
        )
        if resp.status_code == 400:                                     # HTML parse चूक ⇒ एकदा साध्या text caption सह
            import re
            plain = re.sub(r"<[^>]+>", "", caption).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id": chat_id, "caption": plain[:1024], **quiet},
                files={"photo": ("chart.png", png_bytes, "image/png")},
                timeout=timeout,
            )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def send_telegram_media_group(items, timeout=30, silent=False, kind=None):
    """Abhi (pre-open charts): [(png_bytes, caption)] ⇒ एकच album (sendMediaGroup, 2–10 images; caption साधा मजकूर, ≤ 1024). एकच image ⇒
    send_telegram_photo. Album अयशस्वी ⇒ एकेक photo (send_telegram_photo). send_telegram_message सारखंच: कधीच raise नाही, token
    कधीच छापत नाही; credentials नाहीत ⇒ False. रिटर्न bool (सगळे पोहोचले)."""
    items = [(b, str(c or "")) for b, c in (items or []) if b][:10]
    if not items:
        return False
    if len(items) == 1:
        return send_telegram_photo(items[0][0], items[0][1], timeout=timeout, silent=silent, kind=kind)
    go, silent = _policy(kind, silent)
    _log_locally(tag(kind, go, silent) + f"[album {len(items)}] " + " | ".join(c for _, c in items))
    if not go:
        return True
    token, chat_id = _load_telegram_credentials()
    if not token or not chat_id:
        return False
    media = [{"type": "photo", "media": f"attach://p{i}", "caption": c[:1024]} for i, (_, c) in enumerate(items)]
    files = {f"p{i}": (f"chart{i}.png", b, "image/png") for i, (b, _) in enumerate(items)}
    try:
        resp = requests.post(f"https://api.telegram.org/bot{token}/sendMediaGroup",
                             data={"chat_id": chat_id, "media": json.dumps(media), **({"disable_notification": "true"} if silent else {})},
                             files=files, timeout=timeout)
        if resp.status_code == 200:
            return True
    except requests.ConnectionError:                                    # पोहोचलंच नाही ⇒ एकेक photo
        pass
    except requests.RequestException:                                   # उदा. ReadTimeout: album कदाचित पोहोचला ⇒ पुन्हा नाही (duplicate नको)
        return False
    return all([send_telegram_photo(b, c, timeout=timeout, silent=silent or i > 0, kind=kind) for i, (b, c) in enumerate(items)])



def _log_locally(message):
    try:
        os.makedirs(_data(), exist_ok=True)
        from atp_private.trade_engine.config import get_ist_now
        ts = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_p("notifications_log.txt"), "a") as f:
            f.write(f"[{ts}] {message}\n")
    except OSError:
        pass


def notify_entry(script_name, symbol, strategy, direction, strikes_summary, net_credit, trade_id):
    message = (
        f"🟢 <b>New entry — {script_name}</b>\n"
        f"{symbol} | {strategy} | {direction}\n"
        f"Strikes: {strikes_summary}\n"
        f"Net Credit: {net_credit} | Trade ID: {trade_id}"
    )
    return send_telegram_message(message, kind="fill_exit")


def _rs(x):
    """N12: the one signed ₹ helper (paper.watch._rs), imported lazily (no import cycle)."""
    from atp_private.trade_engine.paper.watch import _rs as f
    return f(x)


def notify_exit(script_name, symbol, trade_id, reason, pnl=None):
    pnl_str = f"\nP&L: {_rs(pnl)}" if pnl is not None else ""
    message = f"🔴 <b>Position closed — {script_name}</b>\n{symbol} | Trade ID: {trade_id}\nReason: {reason}{pnl_str}"
    return send_telegram_message(message, kind="fill_exit")




def cooldown_ok(key, cooldown_min=60, now=None, path=None):
    """M53 MS-2: True when `key` was not sent within `cooldown_min` minutes (and records the send). Small JSON state file next to the
    local log. Never raises; any state failure ⇒ True (the message is still sent). cooldown_min <= 0 ⇒ always True."""
    try:
        if float(cooldown_min) <= 0:
            return True
        import time
        t = time.time() if now is None else float(now)
        p = path or _p("alert_cooldown.json")
        try:
            with open(p, encoding="utf-8") as f:
                st = json.load(f)
            if not isinstance(st, dict):
                st = {}
        except (OSError, ValueError):
            st = {}
        last = st.get(key)
        if isinstance(last, (int, float)) and 0 <= t - last < float(cooldown_min) * 60:
            return False
        st = {k: v for k, v in st.items() if isinstance(v, (int, float)) and t - v < 86400}   # prune old keys
        st[key] = t
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(st, f)
        return True
    except Exception:                                                    # noqa: BLE001
        return True




def _error_cooldown_min():
    try:
        import yaml

        from atp_private.trade_engine import paper
        with open(os.path.join(os.path.dirname(os.path.dirname(paper.__file__)), "config.yaml"), encoding="utf-8") as f:
            v = (yaml.safe_load(f) or {}).get("error_alert_cooldown_min")
        return 60 if v is None else float(v)
    except Exception:                                                    # noqa: BLE001
        return 60


def notify_error(script_name, error_detail):
    first = str(error_detail).strip().splitlines()[0][:200] if str(error_detail).strip() else ""
    if not cooldown_ok(f"err|{script_name}|{first}", _error_cooldown_min()):
        _log_locally(f"(duplicate error alert suppressed) {script_name}: {first}")
        return False
    message = f"⚠️ <b>Error — {script_name}</b>\n{error_detail}"
    return send_telegram_message(message, kind="error")


def write_heartbeat(script_name):
    """Trade L300: the 'last good cycle' file (in the bot's state folder); Trade's external ping is not used in ATP."""
    d = _p("heartbeats")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{script_name}.txt"), "w") as f:
        f.write(datetime.datetime.now().isoformat())                    # noqa: DTZ005 - Trade L310, verbatim
