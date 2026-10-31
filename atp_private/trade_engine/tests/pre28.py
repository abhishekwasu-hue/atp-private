"""The reading before the 28 Oct owner order (B1 whole-base band, B2 structural departure, B3 refined confluence, C1 swing reference,
G4 opening gap, C4 Nison candles) — for tests that pin an EARLIER reading of a fixture (their own concern is not the zone band / the CHoCH reference)."""
PRE28_ZONES = {"zone_band_rule": "swing", "level_band_rule": "wick", "z_depart_structure": "atr", "htf_confluence_refine": "band"}
PRE28_CHOCH = {"choch_ref_rule": "candle", "choch_gap_rule": "none"}
PRE28_CANDLES = {"candle_std": "compare", "pullback_form_fact": "off", "opening_gaps": "off", "gap_areas": "off"}      # C4 (Nison) off, C3 fact off
PRE28 = {**PRE28_ZONES, **PRE28_CHOCH, **PRE28_CANDLES}
