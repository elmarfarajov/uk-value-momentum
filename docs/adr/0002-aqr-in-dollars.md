# ADR 0002: AQR's UK factors are in US dollars, and are converted to sterling

**Status:** accepted (Day 1)

## Context

AQR's documentation does not state the currency of its country factors, and they are easy to
read as local-currency returns. The data say otherwise. Over the 366 months from January 1986
to June 2016:

| Comparison | Correlation |
|---|---|
| AQR UK market excess vs Exeter's sterling market excess | 0.823 |
| AQR UK market excess vs Exeter's market translated into dollars | 0.996 |

Regressing the gap (AQR minus Exeter) on the pound's monthly change against the dollar gives
a slope of 1.016 and an R² of 0.978. The gap *is* the exchange rate. AQR's risk-free rate is
the US one-month Treasury bill, which fits the same reading.

A sterling investor's question ("does momentum pay in the UK?") needs sterling returns. A
dollar series mixes in a currency position that has nothing to do with the strategy.

## Decision

`ukfactors.panel.to_sterling` converts every AQR series before it meets a sterling one, with
`x` the month's change in dollars per pound (FRED `DEXUSUK`, month-end):

* A **long/short factor** `r_L − r_S` earned in sterling is worth `(r_L − r_S)(1 + x)` in
  dollars, so the sterling factor is the dollar factor divided by `1 + x`.
* The **market**'s dollar excess return `MKT` over the US bill becomes a dollar total return
  `MKT + rf_US`, then a sterling total return `(1 + MKT + rf_US)/(1 + x) − 1`, then an excess
  return over the UK rate (FRED `IR3TIB01GBM156N`, the three-month interbank rate, converted
  as `(1 + r)^(1/12) − 1`).

The UK Treasury-bill series on FRED stops in 2017, which is why the interbank rate is used.

## Consequences

* For long/short factors the conversion is second-order. The sterling and dollar versions
  correlate above 0.999, and annual means differ by 11 to 19 basis points. For the market it
  is first-order.
* After conversion, AQR's UK market correlates 0.996 with Exeter's. The validation suite holds
  both the converted correlation (> 0.99) and the gap's loading on the exchange rate (within
  0.05 of one).
* The UK rate on FRED currently ends in January 2026, so the sterling market excess return
  ends there too, while the long/short factors run to July 2026.
* Any comparison across countries (the four-market charts) stays in dollars, as AQR publishes
  it, and says so in its caption.
