# ADR 0009: Stock-level evidence comes from survivors, is read comparatively, and every headline is checked against the factors

**Status:** accepted (Day 2)

## Context

Day 2 asks questions that factor files cannot answer:

- Which formation and holding periods pay?
- What happens to a cohort of winners over five years?
- Does residual momentum beat raw momentum?
- How much do the portfolios turn over?
- Which industries do they hold?

These need stock-level returns. The only free source is today's FTSE 350, a survivor sample
(ADR 0003).

Day 2 measured the direction of the bias. Survivorship removes the losers that later failed, so
the losers that remain are the ones that recovered:

- the survivors' loser decile earns 11.4% a year, more than the average survivor (10.1%);
- the short leg of survivor momentum loses 1.3% a year, while Exeter's survivorship-free short
  leg earns 4.5%;
- survivor momentum earns 4.1% a year against AQR's 6.1% over the same months.

The bias therefore *understates* momentum, and understates it most in the short leg.

## Decision

1. **Levels from survivors are not reported as estimates of UK momentum.** Every stock-level chart
   says it is built from survivors, and its subtitle reports the comparison it supports: one
   formation window against another, raw against residual momentum, or the shape of the event-time
   profile.
2. **Each stock-level headline is checked against survivorship-free series where possible.**
   - the market-state result is shown for AQR MOM, AQR UMD and Exeter UMD next to the survivors;
   - the April effect is shown in five sources;
   - leg and size results come from Exeter's monthly portfolios;
   - survivor momentum is plotted against AQR and Exeter (correlation 0.82 with UMD since 2001).
3. **Long-short comparisons are preferred to single legs.** Survivorship affects both legs, so a
   difference between two long-short strategies on the same stocks is less biased than either
   strategy's level.
4. **Equal weights, deciles and at least 30 stocks with a signal** for every stock-level portfolio.
   The cross-section has 179 stocks in 2001 and 327 in 2026.

## Consequences

- A J × K cell with *t* = 1.5 on survivors is not evidence against momentum. The long factor
  histories of Day 1 remain the evidence for the premium; Day 2 adds its anatomy.
- When Day 11 needs the short leg, it must use disclosed short positions, not survivor losers.
- A survivorship-free stock-level dataset (LSPD, Datastream) would replace this sample if
  available. The code takes any price panel.
