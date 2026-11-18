"""Stand-in for Trade's `upstox_api` (Upstox REST) - owner order SRV2, 18 Nov. The calls go to ATP's own Upstox app through ATP's broker
budget (registered callables); pure helpers and the PAPER fill are copied verbatim from Trade 813358b upstox_api.py (line numbers given).
LIVE order calls are refused here: LIVE is not wired (DECISIONS 18 Nov SRV2); a refusal never touches an open position."""
import time
import uuid

from atp_private.srv2 import host as _H

__srv2_io__ = True
_LIVE = "LIVE orders are not wired in ATP for this bot (owner's words needed)"


SYMBOL_INSTRUMENT_KEYS = {                                               # Trade L46-50, verbatim
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX",
}


def get_instrument_key(symbol):
    """Trade L54-56, verbatim."""
    return SYMBOL_INSTRUMENT_KEYS.get(symbol, SYMBOL_INSTRUMENT_KEYS["NIFTY"])


def fetch_upstox_option_chain(access_token, symbol, expiry_index=0):
    """(Upstox /option/chain rows, reason) for the expiry at `expiry_index` (Trade L573)."""
    return _H.need("option_chain")(access_token, symbol, expiry_index)


def fetch_option_expiries(access_token, symbol):
    """The expiry dates "YYYY-MM-DD", nearest first (Trade L551)."""
    return _H.need("option_expiries")(access_token, symbol)


def fetch_candles(*args, **kwargs):
    return _H.need("candles")(*args, **kwargs)


def fetch_ltp_map_detailed(access_token, instrument_keys):
    """(ltp by instrument key, error detail or None) - Trade L863: no keys => ({}, None); a key without a price is left out (never 0)."""
    if not instrument_keys:
        return {}, None
    try:
        res, err = _H.need("ltp")(access_token, list(instrument_keys))
    except _H.HostNotReady:
        raise
    except Exception as e:                                              # noqa: BLE001 - as Trade: an exception => ({}, detail)
        return {}, f"Exception: {e}"
    return {k: float(v) for k, v in (res or {}).items() if v is not None}, err


def fetch_ltp_map(access_token, instrument_keys):
    """Trade L905, verbatim."""
    result, _error_detail = fetch_ltp_map_detailed(access_token, instrument_keys)
    return result


def fetch_option_greeks(access_token, instrument_keys):
    """{key: {delta, gamma, theta, vega, iv}} (Trade L937); no adapter / no keys => {} (Trade: {} on any failure)."""
    if not instrument_keys:
        return {}
    try:
        return _H.get("option_greeks", lambda *a: {})(access_token, list(instrument_keys)[:50]) or {}
    except Exception:                                                   # noqa: BLE001
        return {}


def _funds(access_token):
    try:
        return _H.get("funds", lambda *a: None)(access_token)
    except Exception:                                                   # noqa: BLE001
        return None


def get_available_margin(access_token):
    """Trade L723: equity available margin, None on failure."""
    f = _funds(access_token)
    return float(f.get("available_margin", 0)) if f else None


def get_total_capital(access_token):
    """Trade L741: available + used margin (equity), None on failure."""
    f = _funds(access_token)
    return float(f.get("available_margin", 0)) + float(f.get("used_margin", 0)) if f else None


def fetch_required_margin(access_token, orders):
    """Trade L783 asks Upstox's margin calculator; not wired => None (Trade's result on failure: PAPER stores no margin)."""
    return None


def fetch_broker_positions(access_token):
    """Trade L1006: the broker's own positions (LIVE reconciliation). Not wired => None (Trade's result on failure)."""
    return None


def upload_to_google_drive(file_bytes, filename, mime_type="text/csv"):
    """Trade L513 (Drive backup of Trade's database): not part of ATP - nothing uploaded."""
    return None


def broker_order_quantity(order):
    """Upstox ला जाणारी खरी quantity. MCX commodity साठी Upstox API `quantity` **lots** मध्ये घेतं (Margin API वरून
    पडताळलेलं: SILVER quantity=30 => 30 lots), म्हणून MCX orders मध्ये `broker_quantity` (= lots) असतं; आपली
    `quantity` (units = lots × lot_size) Order Log / charges साठीच राहते. बाकी सर्व instruments साठी `quantity`."""
    return order.get("broker_quantity", order.get("quantity"))



def extract_order_ids(resp):
    """
    🎓 वापरकर्त्याने सापडवलेली bug — established Upstox Multi Order API च्या अधिकृत डॉक्युमेंटेशन प्रमाणे
    (place-multi-order), यशस्वी झाल्यावर `data` हा dict-with-"order_ids" नसून **objects ची list**
    असते — `[{"correlation_id":.., "order_id":..}, ...]`. established कोड आधी चुकीचं dict-आकार
    गृहीत धरायचा (`resp["data"]["order_ids"]`) — त्यामुळे प्रत्यक्ष LIVE order यशस्वी झाला तरी
    `AttributeError: 'list' object has no attribute 'get'` (crash) यायचा.

    established PAPER mode (execute_order_leg_set, याच फाईलमध्ये) established स्वतःचं सिम्युलेटेड
    रिस्पॉन्स वेगळ्या, जुन्या dict-shape मध्ये (`{"order_ids": [...]}`) देतो — तेही चालू राहावं म्हणून
    दोन्ही स्वरूपं इथेच, एकाच ठिकाणी हाताळली आहेत (भविष्यात Upstox ने आकार बदलला तरी फक्त इथेच फिक्स
    करावा लागेल).
    """
    data = resp.get("data")
    if data is None:
        return []
    if isinstance(data, dict):
        return data.get("order_ids", [])  # established PAPER mode चं सिम्युलेटेड स्वरूप
    if isinstance(data, list):
        return [item.get("order_id") for item in data if isinstance(item, dict) and item.get("order_id")]
    return []




def execute_order_leg_set(access_token, orders, trading_mode):
    """Trade L1024-1052. PAPER verbatim: every leg filled at its current LTP (no order leaves ATP). LIVE: refused (not wired)."""
    if trading_mode == "LIVE":
        return None, {"status": "error", "errors": [{"message": _LIVE}]}

    instrument_keys = [o["instrument_token"] for o in orders]
    ltp_map = fetch_ltp_map(access_token, instrument_keys)
    if any(ltp_map.get(k) is None for k in instrument_keys):
        return None, {"status": "error", "errors": [{"message": "Paper fill साठी एका किंवा अधिक legs ची LTP मिळाली नाही."}]}

    batch_id = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    order_ids = [f"PAPER-{batch_id}-{i}" for i in range(len(orders))]
    return 200, {"status": "success", "data": {"order_ids": order_ids}, "paper_fills": ltp_map}


def _live_only(name):
    def fn(*args, **kwargs):
        raise _H.HostNotReady(f"upstox_api.{name}: {_LIVE}")
    fn.__name__ = name
    return fn


for _n in ("place_multi_leg_order", "place_stop_loss_order", "cancel_order", "fetch_order_book", "get_order_details",
           "_verify_and_annotate_fills"):
    globals()[_n] = _live_only(_n)
