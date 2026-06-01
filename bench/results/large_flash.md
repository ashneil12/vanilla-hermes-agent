# Ultracode benchmark — deepseek-v4-flash

Baseline = raw single-shot deepseek-v4-flash. Ultracode = the harness (decompose → fan-out → adversarially verify → loop-until-dry → synthesize) driving the same model.

## Headline

| metric | baseline | ultracode (verified) | ultracode (pre-verify) |
|---|---|---|---|
| overall recall | 1.0 | 0.952 | 1.0 |
| mean precision | 1.0 | 0.939 | 0.9 |
| total findings | 21 | 20 reported | 40 raw |
| total spurious | 0 | 2 | 4 |
| tokens | 3707 | 288371 | — |

## Per task

| task | planted | baseline R/P | ultracode R/P (survivors) | ultra found pre-verify |
|---|---|---|---|---|
| large | 21 | 1.0/1.0 | 0.952/0.939 | 1.0 |

_* near-clean task: precision (not flooding nits) matters most._
