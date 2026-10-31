"""PR #385 review: a full-row digest pin of the DEFAULT reading (the earlier pins — tests/test_trigger_5m.py PIN15 / PIN15_C,
tests/test_entry_models_broken_back.py, the dossier pin — now hold what-ifs and stay as they are). Default = DECISIONS 76 lifecycle
(`break_hold_rule = follow_through`), DECISIONS 79 origin base (`entry_area_refine_base = origin`), DECISIONS 64 visit rule
(`visit_end_rule = away_not_reached`), DECISIONS 58 label rule (`label_rule = evidence_count`); both trigger modes (15M decide rows,
5M decide5 rows) on the abc fixture and the 12 Oct synthetic fixture (both mirrors). Synthetic only (CI-safe)."""
import hashlib
import json

import pytest

from atp_private.trade_engine.decision3 import engine as E3
from atp_private.trade_engine.decision3 import settings as S3

DEFAULT = {"break_hold_rule": "follow_through", "entry_area_refine_base": "origin", "visit_end_rule": "away_not_reached",
           "label_rule": "evidence_count", "zone_band_rule": "base", "z_depart_structure": "bos", "htf_confluence_refine": "h1_origin",
           "choch_ref_rule": "swing", "choch_gap_rule": "opening", "candle_std": "nison", "pullback_form_fact": "on", "gap_areas": "on"}


def _digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _engine(name, trigger_tf):
    if name == "abc":
        from atp_private.trade_engine.tests.test_decision3_method import _abc_m15
        return E3.V22(_abc_m15(), s={"maturity_sigma_d": -1e6, "ltf_choch": False, "c0_volume_required": False,
                                      "trigger_tf": trigger_tf})
    from atp_private.trade_engine.tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=name == "oct12_bull")
    return E3.V22(m15, s={"level_death_side": "role", "trigger_tf": trigger_tf}, ltf=ltf, futures=fut)


def _rows(name, trigger_tf):
    V = _engine(name, trigger_tf)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    if name == "abc":                                    # no 5M frame on abc: every decide row, read under each trigger mode
        return V.run()
    if trigger_tf == "15M":
        return [V.decide(t) for t in range(len(ts)) if ts.dt.normalize().iloc[t] == last]
    F = V.trigger_frame()                                # the 5M candles of the last session (decide5 rows)
    return [V.decide5(j) for j in range(F.n) if str(F.end[j])[:10] == str(last)[:10]]


# pins the default reading after Abhi 29 Oct (one general 1H area band rule, levels.area_band: decisions and entries identical on
# these fixtures; only WATCH lines added by the wider bands (oct12: E1 at 09:30; abc: E2 + E4 on 11 Feb, E1 on 21 Feb); before / after: trade-data review/area_band/2026-10-29) on top of
# the owner review 28 Oct (6) R5 (a filled opening-gap zone is no area — only the area lists change;
# decisions and entries identical; before / after: trade-data review/b4g6_proof/2026-10-28b) on top of the 28 Oct order B / C1 / G4 (B1 whole-base zone bands, B2 structural departure, B3 refined
# confluence, C1 swing reference, G4 opening gap, C3 pullback-form fact, C4 Nison candles, C5 equal-band label, G3 gap areas (DECISIONS 136) — every decision, entry model and active area identical on these fixtures; only the
# zone band values and the new facts change; before / after: trade-data review/b_zones/2026-10-28) on top of the reading after Q56 (a week bar known only once its week ended — only the Weekly channel values change; decisions
# and entries identical) on top of the EN merge (PR #397, owner ✅ DECISIONS 119: EN1 entry only with the full required set, else a
# WATCH — abc: 5 setups ⇒ 0 entries + 6 watch alerts; EN2 distal invalidation; EN3 one entry per cluster visit) on top of the Z merge (PR #395, owner ✅ DECISIONS 117: + zone / level facts `z` in the snapshot; entries
# unchanged) on top of the SW merge (PR #392, owner ✅ DECISIONS 115: SW3 Daily side + SW external swings for BREAK-2), the
# synthetic windows on the realistic Daily history (tests/sw_daily_history.py, M50 A1) — abc DOWN 5 setups (4 before SW), oct12 bear
# DOWN / bull UP 0 setups (0 before: the default flip rule reads the supply BROKEN); before / after: trade-data review/sw_replay/2026-10-26;
# earlier pin: PR #385 + DECISIONS 94. Change only with a before / after chart.
# EN2 (DECISIONS 83; owner ✅ DECISIONS 149): abc E4 (b) WATCH rows on a broken area — 15 Feb 13:15 invalidation 19,453.07 (the retest
# extreme, inside the band) ⇒ 19,463.20 (the band's far edge) + facts distal_edge / model_invalidation; 11 Feb 11:45 + fact distal_edge
# 19,836.84 only (its retest extreme already beyond). Was 3948bdf3392c90f8d4f7797ea71c8ac3a0504f6dd9f8e5cae83717ecf61e661c (both).
PIN_DEFAULT = {("abc", "15M"): "8f89c4bdd394034fb3cee0621db274e1772d5d50e86406a68216198701b6122b",
               ("abc", "5M"): "8f89c4bdd394034fb3cee0621db274e1772d5d50e86406a68216198701b6122b",
               ("oct12_bear", "15M"): "c9a614f4fb97ea0ecac8083b49f26643d738ed1d5a32d08b8001f53f39b67abc",
               ("oct12_bear", "5M"): "3792360d9ef828610b05b53268a7db2ddef68d899b959d792a022a8fa3000ba3",
               ("oct12_bull", "15M"): "b6ead69169993e91d9310d78e086583483dd613ade83d790c2fcd3e07cd197e6",
               ("oct12_bull", "5M"): "da125f6fe9796e5da06cf7027a34942fcddf324a0e24ba3ee0b7f06bbcf1618b"}


@pytest.fixture(scope="module", autouse=True)
def _sw_daily_history(sw_daily_history_ctx):
    """M50 A1: the pinned synthetic windows sit on a realistic Daily history (tests/sw_daily_history.py), as the live engine's full
    stored Daily — SW3 reads each fixture's own trend."""
    with sw_daily_history_ctx():
        yield


def test_the_pinned_settings_are_the_defaults():
    assert {k: S3.DEFAULTS[k] for k in DEFAULT} == DEFAULT


@pytest.mark.parametrize("name,trigger_tf", sorted(PIN_DEFAULT))
def test_default_reading_full_rows_are_pinned(name, trigger_tf):
    rows = _rows(name, trigger_tf)
    assert rows and _digest(rows) == PIN_DEFAULT[(name, trigger_tf)]
