"""atp_private.srv2.settings - the settings of the Trade bot "15M SRv2" (`15m_dynamic_sr`), AS IS (owner order SRV2, 18 Nov).

DEFAULTS is Trade cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"] copied verbatim (Trade 813358b, cloud_db.py L464-579, comments
included); STRIKE_STEP / _STRIKE_RELATIVE_FIELDS / scale_strike_relative_defaults are cloud_db L757-770; merged() is the merge of
cloud_db._get_strategy_settings_ungated (defaults scaled by the strike step, symbol_enabled True only for NIFTY, the stored row wins).
The stored row is the owner's own (ATP stores it; `atp_private.srv2.host`). Nothing here is a new rule.
"""

STRATEGY_KEY = "15m_dynamic_sr"
SIGNAL_SYMBOLS_CHOICES = ("NIFTY", "BANKNIFTY", "SENSEX")               # cloud_db L1324
SIGNAL_SYMBOLS_DEFAULT = ("NIFTY", "BANKNIFTY")                         # cloud_db L1325

DEFAULTS = {
    "lots": 1,
    "signal_source": "engine",       # 🎓 Abhi (Monday PAPER): own / engine / both — M56 O4 (owner default M56-Q5): srv2 engine-only unless set
    "engine3_use_1m": True,          # 🎓 Abhi Z-1o (a): engine (decision3) ला 1m spot ⇒ swings2 candle आतला high / low क्रम (False ⇒ जुनं)
    # 🎓 Abhi (layer 1 ✅): swing scale = his calibration (advanced). रिकामं ⇒ approved swings2 scale (D1 = 4, D2 = 6)
    "engine3_swing_k_d1": "", "engine3_swing_k_d2": "",
    # 🎓 Abhi (L1-c, advanced): Daily swing = N bars दोन्ही बाजूला. रिकामं ⇒ provisional N = 2 (decision3 default, आजचं वर्तन)
    "engine3_daily_pivot_n": "",
    # 🎓 Abhi (live switches, advanced): each Chart Reader layer ⇒ method (रिकामं, default) किंवा त्याचा जुना what-if
    # (engine3_live.METHOD_SWITCHES: visit structure / close_away / touch_window, commitment volume approach_and_opposite / opposite,
    # lines logic / sigma, RSI divergence zone / all, verdict method / score). रिकामं ⇒ method = आजचं वर्तन.
    "engine3_zone_visit_rule": "", "engine3_commit_volume_rule": "", "engine3_line_rule": "", "engine3_div_degree_rule": "",
    "engine3_verdict_rule": "",
    "engine3_entry_gate": "",            # engine3_live.METHOD_SWITCHES: "" / models = entry models E1–E4 (decision3 default) ·
                                         # legacy_k = जुना ③ BOS + K pullback gate (deploy शिवाय fallback)
    "engine3_daily_leg_read": "",        # "" / compare = Daily leg स्वभाव शेजारच्या legs शी तुलनेने (Abhi 21 Oct) · elliott = जुनं वाचन
    "engine3_entry_cluster_rule": "",    # "" / cluster = एकाच visit मधले overlapping areas = एक location (lead, provisional) · area = वेगळे
    "engine3_daily_range_rule": "",      # "" / structure = range रचनेतून (T7, Abhi 21 Oct) · c13 = जुनं दोन समान H + दोन समान L
    "engine3_range_state_rule": "",      # "" / structure = row चा range_state रचनेतून · overlap = जुनं §5.3 overlap + doji
    "engine3_trigger_tf": "",            # "" / 5m = entry trigger 5M closes वर, प्रत्येक model (Abhi, DECISIONS 37) · 15m = जुनं (what-if)
    "engine3_visit_end_rule": "",        # "" / away_not_reached = visit रचनेने संपते, move start पुढे सरकतो (Abhi, DECISIONS 64) · single_swing = जुनं (what-if)
    # 🎓 Abhi (entry models E1–E4, decision3 `entries`): कोणते models signal देतात (signal switch फक्त — execution ला हात नाही;
    # paper/engine_entry.model_on, चुकीचं / रिकामं ⇒ default ON). OFF ⇒ त्या model चे signals / cards नाहीत. Execution (lots, legs,
    # strikes, SL / target / TSL, एका वेळी एकच position) = याच पानाचे आजचे settings. `entries` नसलेले engine rows ⇒ जुनाच मार्ग.
    "engine3_model_e1_on": True, "engine3_model_e2_on": True, "engine3_model_e3_on": True, "engine3_model_e4_on": True,
    # 🎓 Abhi (merged band — check): approval संदेश / pre-open / 15:45 सारांशात पट्ट्याची रुंदी (pts) दाखवतो; रुंदी यापेक्षा जास्त ⇒
    # "⚠️ merged band — check" ओळ. फक्त दाखवणं — निर्णय / gate / order बदलत नाही (bots_common/plain_text.band_warn_pts). Default 150.
    "approval_band_warn_pts": 150,
    # 🎓 Abhi (DECISIONS 53, BW-1): engine areas ना "merged band — check" ओळ नाही (method = default; एक base, कधीच merge नाही) ·
    # width = जुनी 150-pt ओळ (what-if). Bot चे स्वतःचे पट्टे ⇒ ओळ तशीच. फक्त दाखवणं (bots_common/plain_text.band_warn_rule).
    "approval_band_warn_rule": "method",
    # 🎓 Abhi (pre-open charts): pre-open संदेशाच्या वर लहान crux (जवळचा area, entry क्रम, invalidation, target) + प्रत्येक symbol चे
    # Daily / 1H / 15M charts (album). फक्त दाखवणं — निर्णय / gate / order बदलत नाही; chart अयशस्वी ⇒ "(chart unavailable)", संदेश
    # तसाच जातो. Default ON (Abhi ने मागितलं); बंद ⇒ जुनाच संदेश (bots_common/preopen_crux.py).
    "preopen_charts": True,
    # 🎓 Abhi (owner order N7): pre-open charts Telegram ला कसे — "album" (एकच silent album, दोन्ही index चे 6 photos, default) /
    # "link" (संदेशात dashboard link ओळ, album नाही) / "off" (charts नाहीत). फक्त दाखवणं (bots_common/preopen_crux.charts_send).
    "preopen_charts_send": "album",
    # 🎓 Level memory (वापरकर्त्याचा निर्णय: "levels तिथेच राहावेत, बदलू नयेत", डीफॉल्ट चालू) — Dynamic S/R refresh मध्ये जुने levels त्याच
    # किंमतीवर (बघा level_memory.py; logic तोच compute_dynamic_sr, फक्त स्मरण). बंद ⇒ जुनं वर्तन (ताजे top-5, बाकी STALE).
    "level_memory_enabled": True,
    "max_hits_per_zone": 2,   # बघा 1m_instant मधली टिप्पणी
    "itm_depth_points": 100,
    "naked_itm_depth_points": 100,
    "hedge_width_points": 150,
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("RSI setting 60/40 अशी करा") — established single,
    # सममित rsi_neutral_level (50, Support<50/Resistance>50) ऐवजी आता 1m_instant/mcx_futures
    # सारखाच dual-threshold RSI गेट.
    "entry_rsi_gate_enabled": True,
    "rsi_support_max": 40,           # Support/Bullish साठी RSI यापेक्षा कमी हवा
    "rsi_resistance_min": 60,        # Resistance/Bearish साठी RSI यापेक्षा जास्त हवा
    # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
    # सुद्धा पाहिजे") — फक्त त्या दिशेचे नवीन trades थांबतात (आधीच उघडलेले चालूच राहतात). डीफॉल्ट
    # दोन्ही चालू (जुनंच वर्तन).
    "bullish_entry_enabled": True,
    "bearish_entry_enabled": True,
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (15M साठी "Minimum Level-Hold Duration", 5M सारखाच पण
    # 1-मिनिट candles वरून, बफर शिवाय — TOUCH_TOLERANCE_PCT) — डीफॉल्ट बंद. `first_trade_only` True =
    # फक्त त्या level वर आज पहिला खरा trade होईपर्यंत; 2रा trade गेटशिवाय.
    "entry_min_hold_gate_enabled": False,
    "entry_min_hold_minutes": 3,
    "entry_min_hold_first_trade_only": True,
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("3 वेगवेगळे timeframe आहेत, selection user friendly
    # असू द्या, डीफॉल्ट 15 मिनिट ठेवा, 30 आणि 60 मिनिट optional राहील") — आधी तिन्ही (15M/30M/60M)
    # नेहमीच एकत्र तपासले जायचे, निवडीची सोयच नव्हती.
    "active_timeframes": ["15M"],    # ["15M"] | ["15M","30M"] | ["15M","30M","60M"] | इ. — किमान एक हवा
    "entry_pcr_gate_enabled": True,
    "pcr_bullish_min": 0.80,
    "pcr_bearish_max": 1.10,
    "spread_sl_spot_pct": 0.15,
    "spread_sl_premium_points": 10,
    "spread_tsl_spot_pct": 0.30,
    "spread_tsl_premium_points": 25,
    "spread_target_pct_of_premium": 80,
    "carry_forward_min_profit_pct": 30,
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Same level war pahilya trade cha sl tsl hit jhalyas
    # kiman 15 minute same level war trade ghewu naye, cooldown") — 1m_instant सारखीच (वरची
    # टिप्पणी बघा) — त्याच exact level वर आधीचा SL/TSL-प्रकारचा exit किती मिनिटांपूर्वी झाला हे
    # थेट live_trades वरून बघणारा गेट. डीफॉल्ट 15 मिनिटं — 0 केलं की बंद.
    "sl_tsl_cooldown_minutes": 15,
    # 🎓 Abhi 7a ("loss नंतर lock-out नाही") — bot च्या स्वतःच्या (non-engine) मार्गातला symbol-व्यापी post-SL cooldown
    # (srv2 `srv2_strategy_state.last_sl_hit_time` पासून) आधी hard-coded 30 मिनिटं होता. आता setting: default बंद ⇒ cooldown नाही;
    # चालू ⇒ जुनं वर्तन तंतोतंत, `post_sl_cooldown_minutes` मिनिटं (default 30). फक्त 15M SRv2 (MCX चा `sl_cooldown_minutes` वेगळा).
    "post_sl_cooldown_enabled": False,
    "post_sl_cooldown_minutes": 30,
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Naked Option Buy आणि Credit Spread दोन्ही
    # independently optional असायला पाहिजेत — कमी कॅपिटल असलेला user फक्त naked करणं
    # पसंत करतो") — आधी credit spread नेहमीच चालायचा (toggle नव्हता), फक्त naked ऐच्छिक
    # होता. आता दोन्ही स्वतंत्रपणे on/off — डीफॉल्ट True (आधीच्याच वर्तनाशी सुसंगत).
    "credit_spread_enabled": True,
    "naked_enabled": True,
    "naked_lots": 1,                 # 🎓 1m_instant सारखीच सुधारणा — Credit Spread पासून स्वतंत्र lots
    "naked_hedge_enabled": False,
    "naked_hedge_width_points": 150,
    "naked_sl_spot_pct": 0.05,
    "naked_sl_premium_points": 10,
    "naked_tsl_spot_pct": 0.10,
    "naked_tsl_premium_points": 20,
    "naked_target_spot_pct": 0.40,
    "naked_target_premium_points": 50,
    "naked_eod_hour": 15,            # Naked trades कधीच carry-forward नाहीत, नेहमी आजच 3:00pm ला बंद
    "naked_eod_minute": 0,
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("user defined trailing stop loss for all strategies") —
    # 1m_instant सारखीच, Premium Points आधारित सतत Trailing Stop (TSL सक्रिय झाल्यानंतर, Breakeven
    # ऐवजी). डीफॉल्ट बंद.
    "spread_trailing_sl_enabled": False,
    "spread_trailing_distance_points": 8,
    "naked_trailing_sl_enabled": False,
    "naked_trailing_distance_points": 15,
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("PAPER/LIVE toggle + broker selection, per strategy") —
    # 1m_instant सारखीच. डीफॉल्ट नेहमी PAPER, broker_account_ids रिकामी (= शुद्ध Upstox).
    "trading_mode": "PAPER",
    "broker_account_ids": [],
    # 🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL") — 1m_instant
    # सारखीच, डीफॉल्ट बंद.
    "broker_side_sl_enabled": False,
}

STRIKE_STEP = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100}
_STRIKE_RELATIVE_FIELDS = ("itm_depth_points", "naked_itm_depth_points", "hedge_width_points", "naked_hedge_width_points")


def scale_strike_relative_defaults(defaults, symbol):
    step = STRIKE_STEP.get(symbol, STRIKE_STEP["NIFTY"])
    baseline_step = STRIKE_STEP["NIFTY"]
    if step == baseline_step:
        return defaults
    scaled = dict(defaults)
    for field in _STRIKE_RELATIVE_FIELDS:
        if field in scaled:
            scaled[field] = max(round(scaled[field] / baseline_step) * step, step)
    return scaled


def merged(symbol, stored=None):
    """cloud_db._get_strategy_settings_ungated for `15m_dynamic_sr`: defaults (scaled) + symbol_enabled default + the stored row."""
    out = scale_strike_relative_defaults(dict(DEFAULTS), symbol)
    out["symbol_enabled"] = symbol == "NIFTY"
    if stored:
        out.update(stored)
    return out


def clean_signal_symbols(value):
    """cloud_db.clean_signal_symbols (L1328): list / "NIFTY,BANKNIFTY" -> [..] upper, order kept, no duplicates; unknown / empty -> ValueError."""
    items = value.split(",") if isinstance(value, str) else list(value or [])
    out = list(dict.fromkeys(str(x).strip().upper() for x in items if str(x).strip()))
    bad = [x for x in out if x not in SIGNAL_SYMBOLS_CHOICES]
    if bad:
        raise ValueError(f"signal_symbols: {bad} - one of {SIGNAL_SYMBOLS_CHOICES}")
    if not out:
        raise ValueError("signal_symbols: at least one symbol")
    return out
