# Ultracode benchmark — deepseek-v4-flash

Baseline = raw single-shot deepseek-v4-flash. Ultracode = the harness (decompose → fan-out → adversarially verify → loop-until-dry → synthesize) driving the same model.

## Headline

| metric | baseline | ultracode (verified) | ultracode (pre-verify) |
|---|---|---|---|
| overall recall | 1.0 | 1.0 | 1.0 |
| mean precision | 0.865 | 0.813 | 0.801 |
| total findings | 31 | 27 reported | 65 raw |
| total spurious | 4 | 7 | 9 |
| tokens | 8072 | 297434 | — |

## Per task

| task | planted | baseline R/P | ultracode R/P (survivors) | ultra found pre-verify |
|---|---|---|---|---|
| auth | 4 | 1.0/1.0 | 1.0/0.833 | 1.0 |
| fileops | 4 | 1.0/0.8 | 1.0/0.875 | 1.0 |
| web | 4 | 1.0/1.0 | 1.0/0.857 | 1.0 |
| concurrency | 3 | 1.0/0.6 | 1.0/0.5 | 1.0 |
| bigbug | 12 | 1.0/0.923 | 1.0/1.0 | 1.0 |

_* near-clean task: precision (not flooding nits) matters most._
