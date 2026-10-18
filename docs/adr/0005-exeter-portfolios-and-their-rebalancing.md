# ADR 0005: Exeter's portfolios are used as described, with the 25 size-momentum sort flagged as annual

**Status:** accepted (Day 1, v0.1.1)

## Context

Besides its factors, the Exeter Xfi Centre publishes the portfolios behind them: the six 2×3
sorts on size and book-to-market and on size and momentum, 25 portfolios on each 5×5 sort, and
ten deciles on book-to-market and on size. They are the natural test assets for UK asset-pricing
tests (Day 8) and the natural place to see which stocks carry a premium (Day 1, Section 6.4).

Two facts emerged on Day 1.

1. **The factors are exactly their portfolios.** HML, SMB and UMD rebuilt from the six 2×3
   portfolios (HML and UMD as ½(SH + BH) − ½(SL + BL), SMB as small minus big averages) match the
   published factors to 10⁻⁸ in every month from 1980 to 2016.
2. **The 25 size-momentum portfolios carry almost no momentum premium**: high-minus-low spreads
   of 0.2 to 4.6 points a year, none significant, against 14.8% and 8.8% in the six. Each archive
   includes a file of stock counts. For the 25 portfolios the counts are listed by *year*; for
   the six behind UMD, by *month*. The 25 are evidently re-formed once a year,
   while the six are re-formed monthly. A momentum signal decays
   within months (Jegadeesh and Titman, 1993), so annual re-formation discards most of it.

## Decision

1. **The six 2×3 portfolios and the deciles are used freely**, with the rebuild check in the
   validation suite ("Exeter's factors are their portfolios") guarding the link to the factors.
2. **The 25 size-momentum portfolios are not used as momentum test assets.** Where a 5×5 momentum
   sort is needed (Days 2 and 8), it is rebuilt monthly or taken from a source that re-forms it
   monthly. They are kept in the gallery as a demonstration of the holding-period effect, with
   the reason in the chart's subtitle.
3. **All portfolio returns are turned into excess returns over Exeter's own risk-free rate**,
   not the FRED interbank rate, so that the portfolios and the factors share one denominator.

## Consequences

* An inference ("annual re-formation") is stated as an inference, since Exeter's web page does
  not document it (Limitations, item 10).
* Day 2's holding-period analysis can measure the same effect directly on AQR's and Exeter's
  monthly series, and should reproduce the gap.
