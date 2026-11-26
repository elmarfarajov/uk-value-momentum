# ADR 0017: Volatility forecasts from monthly returns

**Status:** accepted (Day 7)

## Context

Barroso and Santa-Clara (2015) scale momentum by its realised volatility over the previous 126
trading days. Daniel and Moskowitz (2016) use a GARCH forecast fitted to daily returns. AQR
publishes its UK factors monthly only. The Yahoo stock panel has month-end prices, and rebuilding
UMD from it would bring back the survivorship problem measured on Day 1 (ADR 0003).

## Decision

- **Volatility forecast:** the standard deviation of the previous six monthly returns,
  annualised. This is the shortest window that is not dominated by a single month.
- **Constant volatility:** the weight is the target divided by the forecast. It is reported
  uncapped, as in the paper, and with a cap of two as a robustness check.
- **Dynamic strategy:** the mean forecast regresses UMD on the bear indicator times the market's
  six-month variance, using data up to the previous month only. It starts after ten years.

## Consequences

- The constant-volatility weight is noisy: its median is 1.44 and it exceeded two in 29% of months.
- The dynamic weight is unbounded. In June 2005 it reached 15.3, when UMD's six-month volatility was
  2%. The note reports the strategy with and without those months and with a cap.
- The results understate what daily data would deliver. The direction of every finding matches
  the published daily-data results.
