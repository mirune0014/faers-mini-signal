# Methods (EVP)

This MVP computes classical disproportionality metrics from a 2x2 table per (drug, PT):

- PRR = (A/(A+B)) / (C/(C+D))
- Chi-square (1 df, Yates): ((|AD-BC| - N/2)^2 * N) / ((A+B)(C+D)(A+C)(B+D))
- ROR = (A/B) / (C/D); 95% CI via ln(ROR) ± 1.96*sqrt(1/A+1/B+1/C+1/D)
- IC = log2(A/E[A]); E[A] = (A+B)(A+C)/N; CI via normal approx

Edge cases: apply small epsilon (1e-12) to avoid division by zero; return NaN when undefined.

