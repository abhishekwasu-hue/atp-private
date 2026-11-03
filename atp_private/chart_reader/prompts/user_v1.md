<!-- prompt_version: abhi_read_v5 | placeholders in {braces} are filled by chart_read.py; a human can fill them by hand for any other model -->
Instrument: {instrument}
Charts attached (in order): {chart_list}

FACTS (from code / data; trust these over your own reading of numbers):
{facts}

Task: read the attached chart(s) with the four steps. Return JSON with these fields:
- trend: direction (up / down / sideways / unclear), the swing evidence you see
- areas: each buyer or seller area you see (side, price_low, price_high, which chart, evidence)
- correction: is price correcting into one of those areas now; is momentum weakening (yes / no / unclear); evidence
- commitment_candle: present or not on the latest bars; evidence
- area_of_interest_statement: one or two sentences: "At <lo>-<hi> (<chart>) <buyers/sellers> defended before; <what price must still show there>; the read is invalid if <structure level> is closed beyond and stays beyond." If nothing is valid, say in one line why.
- watch_next: what to watch on the next bars (price behaviour only)
- cannot_read: what the image does not let you see, or null
