# ADR 0010: One set of momentum conventions: formation, skip, deciles and overlapping cohorts

**Status:** accepted (Day 2)

## Context

"Momentum" names a family of strategies that differ in five choices. Each changes the answer:

- **the formation window:** how many months of past returns;
- **the skip:** how many recent months to leave out;
- **the breakpoints:** decile, quintile or 30% legs;
- **the weighting:** equal or value;
- **the holding period:** one month, or longer with overlapping cohorts.

The literature's defaults differ. Jegadeesh and Titman (1993) use deciles and overlapping
cohorts. Fama and French's UMD uses 30% legs within size groups. AQR's MOM uses rank weights.
Comparing results across days needs one convention, stated once.

## Decision

- **Timing.** A strategy is held from the start of month `h`. Its signal uses only returns to the
  end of month `h − 1 − skip`. The formation return over `j` months covers months `h − j − skip` to
  `h − 1 − skip`. The standard signal is "12-1": `j = 11`, `skip = 1`, months `h − 12` to `h − 2`.
- **Grid.** The J × K grid uses `J ∈ {1, 3, 6, 9, 12}` formation months, a one-month skip and
  `K ∈ {1, 3, 6, 9, 12}`. It is reported over common months from January 2001, the first month every
  cell exists.
- **Portfolios.** Stocks are ranked each month. Winners are the top decile and losers the bottom,
  equally weighted. A month needs at least 30 stocks with a signal. 20% and 30% legs are reported
  as robustness (Sharpe 0.40 and 0.33 against 0.32 for deciles).
- **Overlapping cohorts.** A K-month strategy owns the cohorts formed in the last K months, each
  with weight 1/K. A month enters the sample only when all K cohorts exist.
- **Residual momentum** follows Blitz, Huij and Martens (2011): 36-month regressions on the UK
  market (sterling total return), SMB and HML, with the 12-1 sum of residuals divided by their
  standard deviation.
- **Turnover** is half the sum of absolute changes in target weights, before price drift.
- **Ties.** When many stocks share a signal value, the ranking is broken by the 12-1 signal. This
  arises for the 52-week-high ratio, where 24% of stocks sit at exactly 1.

## Consequences

- The brute-force check in the validation suite reimplements the overlapping-cohort return with
  plain loops and matches it to 10⁻¹⁷.
- Results are comparable across Days 2 to 14. Value-weighted versions, which Day 9's cost
  analysis needs, will be added as an option rather than a new convention.
- Without the tie rule, the 52-week-high strategy lost half its months to empty deciles. The bug
  was caught on Day 2 (151 of 320 months) and fixed.
