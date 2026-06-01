# Ultracode benchmark — deepseek-v4-flash

Baseline = raw single-shot deepseek-v4-flash. Ultracode = the harness (decompose → fan-out → adversarially verify → loop-until-dry → synthesize) driving the same model.

## Headline

| metric | baseline | ultracode (verified) | ultracode (pre-verify) |
|---|---|---|---|
| overall recall | 0.962 | 0.923 | 0.923 |
| mean precision | 0.976 | 1.0 | 1.0 |
| total findings | 30 | 24 reported | 27 raw |
| total spurious | 1 | 0 | 0 |
| tokens | 8422 | 13168 | — |

## Per task

| task | planted | baseline R/P | ultracode R/P (survivors) | ultra found pre-verify |
|---|---|---|---|---|
| auth | 4 | 1.0/1.0 | 0.75/1.0 | 0.75 |
| bigbug | 12 | 1.0/1.0 | 1.0/1.0 | 1.0 |
| vulnflask | 10 | 0.9/0.929 | 0.9/1.0 | 0.9 |

_* near-clean task: precision (not flooding nits) matters most._
