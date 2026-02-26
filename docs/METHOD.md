# Methods (EVP)

For each `(drug, PT)` pair, metrics are computed from 2x2 ABCD counts:

- PRR = `(A/(A+B)) / (C/(C+D))`
- Chi-square (1 df, Yates): `((|AD-BC| - N/2)^2 * N) / ((A+B)(C+D)(A+C)(B+D))`
- ROR = `(A/B) / (C/D)` and 95% CI on `ln(ROR) ± 1.96*sqrt(1/A+1/B+1/C+1/D)`
- IC = `log2(A/E[A])`, `E[A] = (A+B)(A+C)/N`, with normal-approx CI

Implementation detail:
- `metrics.py` applies **Haldane–Anscombe correction** (`+0.5` to all four cells) whenever any of `A, B, C, D` is zero.
- This is the same logic used by the main pipeline before computing PRR/ROR/IC and chi-square statistics.

