# ADR 0013: Time-series momentum conventions

**Status:** accepted (Day 4)

## Context

Time-series momentum (Moskowitz, Ooi and Pedersen 2012, "MOP") goes long an asset whose own
excess return over the past year was positive and short one whose return was negative, with each
position scaled by the asset's volatility. MOP used daily futures data and a 60-day
centre-of-mass volatility estimate. This project has only monthly UK series.

## Decision

1. **Signal:** the sign of the cumulative log excess return over the past 12 months, known at the
   month end. The linear (clipped z-score) and moving-average rules are reported as variants.
2. **Scaling:** position = signal × 10% / σ_t, where σ_t is an annualised EWMA volatility of
   monthly excess returns (centre of mass 6 months, at least 12 months of data), known at t.
3. **Portfolio:** equal weight across the assets available each month. Holding periods above
   one month average the last K positions (overlapping portfolios).
4. **Inference:** MOP's pooled regression of r_t/σ_{t-1} on r_{t-h}/σ_{t-h-1}, with standard
   errors clustered by month. The diversified Sharpe ratio is also compared with a placebo that
   shifts each asset's signal in time by a random offset (it keeps persistence and time long).

## Consequences

- **The volatility target is missed upwards.** A 6-month EWMA of monthly data uses about 13
  effective observations. Its estimate averages about 15% below the true volatility, and
  1/σ̂ is biased upwards. Positions therefore run at about 12% volatility, not 10%
  (validation check "Volatility scaling equalises risk"). Scaling still equalises risk across
  assets: 10% to 40% volatile assets end within 1.2% of each other. Sharpe ratios are unaffected
  because the bias scales returns and volatility together.
- With three asset classes the portfolio is far less diversified than MOP's 58 futures. Its
  Sharpe ratio should be compared with single-asset-class results, not with MOP's headline.
