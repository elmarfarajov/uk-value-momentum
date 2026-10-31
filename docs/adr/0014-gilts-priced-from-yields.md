# ADR 0014: Gilt returns priced from the OECD ten-year yield

**Status:** accepted (Day 4)

## Context

Time-series momentum needs a UK government bond return series back to the 1970s. Free total-return
gilt indices with that history are not available for redistribution. FRED publishes the OECD's UK
long-term government bond yield (`IRLTLT01GBM156N`), monthly from 1960, in the public domain.

## Decision

- Each month, buy a par ten-year gilt paying a semi-annual coupon equal to last month's yield.
  Sell it a month later at this month's yield with 9 11/12 years left. The return is the price
  change plus a month of coupon: `P(y_t) - 1 + y_{t-1}/12`.
- The price uses the annuity formula with a fractional number of coupon periods. The validation
  suite checks it against an explicit sum of cash flows (with a maturity giving whole periods).
  It also checks that a flat yield earns exactly y/12.
- Excess return = gilt return − the UK three-month rate (ADR 0004's risk-free series).

## Consequences

- The OECD yield is a monthly average, not a month-end value. Monthly returns are therefore
  smoothed a little, and month-to-month autocorrelation is overstated. That works in favour of the
  one-month lookback; the note flags the one-month cell of the lookback grid for this reason.
- Convexity, the roll-down of the curve and the exact coupon schedule are ignored. The series is a
  proxy for a constant-maturity index, not a tradable gilt.
