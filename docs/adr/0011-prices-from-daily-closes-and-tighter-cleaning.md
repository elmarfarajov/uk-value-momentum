# ADR 0011: Stock prices come from daily closes, and unit flips that reverse are caught

**Status:** accepted (Day 2). Revises ADR 0003. Day 1 corrected (see the Errata in the Day 1 note).

## Context

On Day 2 the first J × K grid was impossible:

- twelve-month momentum earned +12.9% a year with an 11-month window and −16.9% with a 12-month
  one;
- the 52-week-high strategy lost 62% a year.

The returns themselves were the problem. Pooled across stocks, monthly returns had a first-order
autocorrelation of −0.14 and a third-order one of +0.32. Real monthly stock returns are close to
serially uncorrelated.

Two defects in Yahoo's data explained it:

1. **Monthly bars mishandle dividends.** With `interval="1mo"` and dividend adjustment, many
   investment trusts showed a spike in each ex-dividend month (+8% to +15% in March, June and
   November for ALW and BUT) that reversed the next month. Quarterly dividends produced the
   third-order autocorrelation.
2. **Unit flips smaller than the thresholds.** FCIT's monthly closes alternated between about 170
   and 700. MYI, TMPL and JEGI flipped by about ×5 and back. MNKS jumped ×4.6 in July 2001 and
   never reversed, an unadjusted consolidation. All stayed inside the +400% / −80% limits of
   ADR 0003.

## Decision

1. **Prices are daily adjusted closes, sampled at each month's last trading day** (`interval="1d"`,
   `resample("ME").last()`). The ex-dividend spikes disappear. FCIT's series becomes smooth.
2. **The impossible-move limit is +300%** (was +400%). The −80% floor stays. Between +300% and
   +400% the only series affected was MNKS's consolidation.
3. **Unit flips that reverse are caught.** A series is dropped if two months within 36 have returns
   each at least a factor of 3 in size, of opposite sign, and cancelling to within a quarter of the
   larger. This catches JEGI, MYI and TMPL. It keeps genuine crashes that do not reverse, such as
   Taylor Wimpey (−72%, October 2008) and Costain (−79%, March 2020).
4. **A data-quality check guards the result.** The validation suite requires the pooled
   autocorrelation of cleaned stock returns at lags 1 to 3 to stay below 0.05 in absolute value. It
   is +0.007, −0.020 and +0.023. A synthetic test injects five-fold flips that reverse, a lasting
   crash and a lasting rally, and requires exactly the flips to be dropped.

## Consequences

- 22 series are excluded and 327 kept (39 and 310 before). The monthly standard deviation of stock
  returns fell from 15% to 9.5%.
- Day 1's survivorship numbers change: the survivors' premium is 4.0% a year, not 7.7%, and
  survivor momentum earns 4.1%, not 6.8%, against AQR's 6.1%. The direction of the momentum bias
  reverses (ADR 0009). Factor-level results are unaffected.
- The fix was found because a result looked wrong. The autocorrelation check now makes the same
  defect a failing test rather than a surprising chart.
