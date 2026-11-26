# ADR 0018: Exeter's test portfolios, and the six monthly size-momentum portfolios

**Status:** accepted (Day 8)

## Context

Asset-pricing tests need test portfolios and factors built from the same universe. Exeter
publishes, for UK stocks from October 1980 to June 2016:

- 25 size × book-to-market portfolios and 25 size × momentum portfolios;
- 6 portfolios of each kind;
- the factors RMRF, SMB, HML and UMD.

On inspection, the 25 size-momentum portfolios have winner-minus-loser spreads of only 0-5% a
year, while UMD earns 11.8%. The readme in Exeter's archive counts their constituents by year,
while the six-portfolio file counts them by month. The 25 are re-sorted on momentum once a year,
so their signal is up to a year old. The six are rebalanced monthly, as UMD is. A check confirms
that UMD equals the average of the six portfolios' small and big winner-minus-loser spreads to
10⁻⁸.

## Decision

- **Main test set:** the 25 size-book-to-market portfolios plus the six monthly size-momentum
  portfolios (31 in all).
- **Robustness only:** the 25 annual size-momentum portfolios.
- **Excess returns:** over Exeter's own risk-free rate.
- **Macro innovations:** from FRED.
  - The three-month rate is stored as a monthly return (`fred.uk_rate`). It is converted back to an
    annual rate in percentage points before the term spread to the gilt yield is taken.
  - A validation check rebuilds the published rate.

## Consequences

- The momentum tests use portfolios built the way the factor is. The note reports that the
  annual 25 tell the same story more weakly.
- The cross-sectional tests stop in June 2016, when Exeter's data ends.
