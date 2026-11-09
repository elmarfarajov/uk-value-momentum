# ADR 0015: Studying value's lost decade without book values

**Status:** accepted (Day 5)

## Context

The plan for Day 5 was to decompose UK value's 2007-2020 loss as Arnott, Harvey, Kalesnik and
Linnainmaa (2021) do for the US. Their decomposition splits the return of HML into revaluation
(the change in the book-to-market spread between value and growth), migration (stocks moving
between portfolios) and profitability. It needs company book values each year. The free UK data
used by this project (AQR factor returns, Exeter portfolio returns, Yahoo prices) has none.

## Decision

- The AHKL decomposition is **not attempted**. The note says so at the start, and does not
  approximate it with a proxy that could be mistaken for it.
- The day studies what return data can answer: the depth and length of the loss in three UK value
  definitions and four markets; a sup-Wald test for a break in the mean (Andrews 1993) with a
  block-bootstrap p-value; the probability of such a loss under the pre-2007 distribution; the
  attribution of the loss to loadings on other factors; the factor's sensitivity to gilt yields;
  and which leg lost (Exeter's top and bottom book-to-market deciles, to June 2016).
- The lost decade is fixed as January 2007 to September 2020. September 2020 is HML Devil's
  trough and the month the break test's statistic peaks. The start is the conventional one.

## Consequences

- The note cannot say how much of the loss came from value stocks getting cheaper relative to
  growth stocks. Day 13 (machine learning on the cross-section) will need fundamentals. If a free
  UK source of book values is found, the decomposition should be added then.
- The Exeter results stop in June 2016, four years before the trough.
