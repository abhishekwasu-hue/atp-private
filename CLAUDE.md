# Abhi's standing preferences — binding in EVERY session, read FIRST: OWNER_RULES.md
@OWNER_RULES.md

# CLAUDE.md - atp-private

- **This repository is currently PUBLIC by the owner's decision (20-21 Nov, 'Sadhya public rahu de'): anything committed
  here is world-visible. Still never copy its code into the ATP repository. Secrets are never allowed.** Method / engine /
  strategy code (the Trade engine snapshot, the chart reader, the KB and the Method Pack) lives only here; never copy any of
  it (code, text, numbers, fixtures, logs or screenshots of it) into the ATP repository or an ATP issue / PR.
- ATP (public) only holds the boundary: a provider interface and a loader that imports `atp_private.*` if present.
- No secrets in this repository: no keys, tokens, `.env` files or server addresses. Deploy keys stay on the hosts.
- Engine code comes in only as the owner ordered it (Trade order M65: the snapshot, AS IS, import paths only). Never
  invent or "fix" method logic here; a change to the method needs Abhi's approval first.
- Work on a `claude/<name>` branch with a PR; `main` is protected (the initial skeleton commit was the only direct one).
- Rules for ATP work in general: the public repo's CLAUDE.md and docs/WORKING_RULES.md.
