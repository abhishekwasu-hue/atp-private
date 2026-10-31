# Abhi's standing preferences — binding in EVERY session, read FIRST: OWNER_RULES.md
@OWNER_RULES.md

# CLAUDE.md - atp-private

- **This repository is PRIVATE.** Method / engine / strategy code (the Trade engine snapshot, the chart reader, the
  KB and the Method Pack) lives only here. **Never copy any of it to the public ATP repository** (code, text, numbers,
  fixtures, logs or screenshots of it), and never paste it into a public issue, PR or chat.
- ATP (public) only holds the boundary: a provider interface and a loader that imports `atp_private.*` if present.
- No secrets in this repository: no keys, tokens, `.env` files or server addresses. Deploy keys stay on the hosts.
- Engine code comes in only as the owner ordered it (Trade order M65: the snapshot, AS IS, import paths only). Never
  invent or "fix" method logic here; a change to the method needs Abhi's approval first.
- Work on a `claude/<name>` branch with a PR; `main` is protected (the initial skeleton commit was the only direct one).
- Rules for ATP work in general: the public repo's CLAUDE.md and docs/WORKING_RULES.md.
