# Operator OS — Hermes profile (v3.8)

The strongly-opinionated **Operator OS** persona for the Hermes agent: a Hormozi-style business
co-founder that challenges you, explores with you, and stands its ground — backed by a 27-doc
strategy knowledge base. This is not a stock Hermes assistant. It's a business sparring partner.

## What's here
- `SOUL.md` — the v3.8 brain (the agent's identity / system prompt). Loaded as slot #1 of the
  stable system prompt via Hermes' `load_soul_md()` hook (`$HERMES_HOME/SOUL.md`).
- `skills/operatoros-kb/` — the searchable KB (25 bundled docs in `kb/`) + a `SKILL.md` that
  teaches retrieval (the writing-quality gate, brand voice, brutal-honesty, the master index).
- `CHANGELOG-v3.8.md` — exactly what changed from v3.7 and why.

## Install as a profile (recommended for dogfooding)
```bash
mkdir -p ~/.hermes/profiles/operatoros/skills
cp profiles/operatoros/SOUL.md                ~/.hermes/profiles/operatoros/SOUL.md
cp -r profiles/operatoros/skills/operatoros-kb ~/.hermes/profiles/operatoros/skills/
hermes -p operatoros chat
```
`hermes -p operatoros` swaps `HERMES_HOME` to the operatoros profile, so the agent boots with the
v3.8 brain + the KB skill and nothing else changes. (`~/.local/bin/operatoros` wrapper optional.)

## Make it the fork default (so the fork IS Operator OS out of the box)
Point `hermes_cli/default_soul.py::DEFAULT_SOUL_MD` at this `SOUL.md` (or seed it into the default
profile). Tracked as the next Phase-P step — it flips the fork's default identity for **every**
instance, so it's a deliberate change, not a silent one. For the dogfood swap, either approach
works: run the `operatoros` profile, or make it the default before pointing the Hermes app at the
fork.

## Voice tailoring (future enrichment)
Ash thinks out loud and rants through problems — which is exactly why v3.8 adds the Founder
Cognition + Strategic Exploration protocols (a statement isn't a decision; many ideas are probes).
A deeper tailoring pass can mine his real session history (e.g. the pve10 session DB) to calibrate
tone and recurring patterns. Not required for the agent to work well; it sharpens the fit.
