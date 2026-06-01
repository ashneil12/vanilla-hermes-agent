# Ultracode benchmark — deepseek-v4-flash

Baseline = raw single-shot deepseek-v4-flash. Ultracode = the harness (decompose → fan-out → adversarially verify → loop-until-dry → synthesize) driving the same model.

## Headline

| metric | baseline | ultracode (verified) | ultracode (pre-verify) |
|---|---|---|---|
| overall recall | 1.0 | 1.0 | 1.0 |
| mean precision | 1.0 | 0.944 | 0.949 |
| total findings | 22 | 21 reported | 39 raw |
| total spurious | 0 | 2 | 2 |
| tokens | 8854 | 692712 | — |

## Per task

| task | planted | baseline R/P | ultracode R/P (survivors) | ultra found pre-verify |
|---|---|---|---|---|
| large2 | 21 | 1.0/1.0 | 1.0/0.944 | 1.0 |

_* near-clean task: precision (not flooding nits) matters most._
