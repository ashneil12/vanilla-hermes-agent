# Ultracode benchmark — deepseek-v4-pro

Baseline = raw single-shot deepseek-v4-pro. Ultracode = the harness (decompose → fan-out → adversarially verify → loop-until-dry → synthesize) driving the same model.

## Headline

| metric | baseline | ultracode (verified) | ultracode (pre-verify) |
|---|---|---|---|
| overall recall | 1.0 | 0.812 | 1.0 |
| mean precision | 0.707 | 0.817 | 0.833 |
| total findings | 22 | 13 reported | 33 raw |
| total spurious | 6 | 3 | 3 |
| tokens | 10445 | 199156 | — |

## Per task

| task | planted | baseline R/P | ultracode R/P (survivors) | ultra found pre-verify |
|---|---|---|---|---|
| auth | 4 | 1.0/1.0 | 1.0/1.0 | 1.0 |
| fileops | 4 | 1.0/0.8 | 0.75/1.0 | 1.0 |
| web | 4 | 1.0/0.8 | 0.75/0.75 | 1.0 |
| concurrency | 3 | 1.0/0.6 | 0.667/1.0 | 1.0 |
| nearclean* | 1 | 1.0/0.333 | 1.0/0.333 | 1.0 |

_* near-clean task: precision (not flooding nits) matters most._
