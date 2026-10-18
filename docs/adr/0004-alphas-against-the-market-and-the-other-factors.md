# ADR 0004: Every premium is reported raw, against the market, and against the other factors

**Status:** accepted (Day 1, v0.1.1)

## Context

A factor's raw mean answers one question: what did holding it earn? An investor who already
holds other factors asks another: what does this one add? In the UK the two answers differ
sharply for value. Its raw mean is 3.0% a year (Sharpe 0.21, *t* = 1.1). Its alpha against the
market and momentum is 7.6% (*t* = 3.5). Reporting only one of the two would mislead either way:
the raw figure understates what value adds to a momentum investor, and the alpha overstates
what a value-only investor earned.

The negative correlation between value and momentum (−0.61) is what drives the gap. It is also
why HML Devil, the value measure most negatively correlated with momentum, has the lowest raw
mean of the value measures and the highest alpha.

## Decision

1. **Three numbers per factor, always together.** The raw mean and Sharpe ratio (Table 2), the
   CAPM alpha, and the alpha against a fixed set of controls (Table 10). The controls are fixed in
   advance, not chosen to flatter: value and momentum against each other and the market; HML,
   HML Devil and UMD against the Fama-French-Carhart set; QMJ against all four; SMB against the
   rest.
2. **Newey-West errors with the automatic lag**, the same rule as for means. The regression code
   is our own (`ukfactors.analysis.regress`), so it runs without statsmodels in the installed
   wheel, and the validation suite holds it to statsmodels' HAC estimator (agreement 7 × 10⁻¹⁵).
3. **Alphas are annualised by twelve and stated with their sample.** Each regression uses the
   common months of its series, which differ by factor (Table 10 lists them).

## Consequences

* The headline "UK value does not work" and "UK value works" are both reported, with the
  condition under which each is true.
* Days 5 and 8 inherit the convention. Value's lost decade is decomposed raw and
  momentum-hedged, and the risk-versus-mispricing tests use the same control sets.
* An alpha against other *traded* factors is a statement about combinations of factors, not
  about risk. Day 8 asks the risk question with macro and sentiment variables instead.
