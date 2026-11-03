<!-- prompt_version: book_strategy_read_v5 | placeholders in {braces} are filled by chart_read.py; a human can fill them by hand for any other model -->
Instrument: {instrument}
Charts attached (in order): {chart_list}

FACTS (from code / data; trust these over your own reading of numbers):
{facts}

BOOK STRATEGY (independent; use only this):
{strategy}

Task: check the attached chart(s) against this book strategy only. Return JSON with these fields:
- side_scored: long or short (see How to score)
- conditions: for every condition id above: status (met / not_met / unclear) and the evidence you see
- levels: the price levels or zones this book's strategy uses that you can see (kind, price_low, price_high, which chart, evidence)
- trigger_seen: status (yes / no / unclear) = is the book's own trigger on the latest bars; bar = the bar number where it last appeared, or null; evidence (name the trigger variant letter when the book lists several)
- invalidated: does the chart show the book's invalidation for the side_scored read (yes / no / unclear), with evidence
- statement: one or two sentences beginning "{book} strategy:" that say what the book's strategy sees now and what it would still need
- cannot_read: what the image does not let you see, or null
