# Ultracode benchmark — deepseek-v4-pro

Baseline = raw single-shot deepseek-v4-pro. Ultracode = the harness (decompose → fan-out → adversarially verify → loop-until-dry → synthesize) driving the same model.

## Headline

| metric | baseline | ultracode (verified) | ultracode (pre-verify) |
|---|---|---|---|
| overall recall | 1.0 | 1.0 | 1.0 |
| mean precision | 0.923 | 0.929 | 0.929 |
| total findings | 13 | 12 reported | 14 raw |
| total spurious | 1 | 1 | 1 |
| tokens | 2979 | 81392 | — |

## Per task

| task | planted | baseline R/P | ultracode R/P (survivors) | ultra found pre-verify |
|---|---|---|---|---|
| bigbug | 12 | 1.0/0.923 | 1.0/0.929 | 1.0 |

_* near-clean task: precision (not flooding nits) matters most._
