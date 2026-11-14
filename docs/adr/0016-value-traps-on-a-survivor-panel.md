# ADR 0016: Testing value traps on a survivor panel, with price proxies

**Status:** accepted (Day 6)

## Context

The value-trap question is about single stocks: do cheap companies with poor quality keep
falling? Answering it properly needs company accounts, to measure both cheapness (book-to-market)
and quality (profitability, growth, leverage, payout), on a sample that includes companies that
later failed. The free UK data has neither accounts (ADR 0015) nor dead companies. The Yahoo panel
holds the current FTSE 350 members (ADR 0003).

AQR's QMJ factor is built from accounts and includes delisted companies, so it answers the
question at factor level without either problem.

## Decision

- The main evidence is at factor level: AQR's UK QMJ against HML, HML Devil and VAL, July 1993
  onwards.
- A stock-level test is reported with price proxies:
  - cheapness = the return from months *t*−60 to *t*−13 (long-term losers, De Bondt and Thaler
    1985);
  - quality = safety, measured as past 36-month volatility.
  The cheapest 30% each month are split into thirds by volatility. A trap is a loss of 30% or more
  over the next twelve months.
- The stock-level results are labelled as survivor-only throughout: on charts, in the note and in
  the README. Returns of risky cheap stocks are presented as an upper bound, and trap rates as
  lower bounds.

## Consequences

- The note can rank trap rates by volatility. That ranking would only widen if failures were
  added back.
- The note cannot say whether quality-filtered value beats plain value at stock level. On
  survivors, the riskiest cheap stocks earn the most, which is the opposite of the factor-level
  result and most likely an artefact of the sample.
- A point-in-time constituent list with delisted prices would remove the bias. It would replace
  the Yahoo panel in this test without other changes.
