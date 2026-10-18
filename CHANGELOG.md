# Changelog

## v0.1.1: Day 1 extended

### Added

* `ukfactors.analysis`: factor regressions with Newey-West errors, the value-momentum frontier and
  tangency weight, rolling correlations, calendar-year returns, start-date sensitivity,
  autocorrelations and Ljung-Box tests, drawdown episodes, factors rebuilt from Exeter's 2x3
  portfolios, 5x5 grids and deciles, market states, bootstrap Sharpe distributions.
* Thirteen new charts (24 in all): alphas, the mix, rolling correlation, the 5x5 grids, the six
  factor legs, deciles, calendar years, start dates, bootstrap distributions, autocorrelation,
  drawdown episodes, rates and currency, market states.
* The Day 1 note doubled to about twenty pages: a new Section 6 with eleven tables (20 in all) and
  five new references.
* Four validation checks (13 in all): regressions and autocorrelations against statsmodels, the
  tangency weight against a brute-force search, and Exeter's factors against their portfolios.
* ADR 0004 (alphas reported raw, against the market and against the other factors) and ADR 0005
  (Exeter's portfolios, with the 25 size-momentum sort flagged as annual).
* Seventeen tests (56 in all, 98% coverage); synthetic Exeter portfolio files in the fixtures.

### Found

* UK value's alpha is significant once momentum is controlled for (7.6% a year, *t* = 3.5).
* Exeter's 25 size-momentum portfolios are re-formed once a year and show almost no momentum
  premium.

### Fixed

* Chart subtitles were cut off at the right edge; the wrap width is now narrower.

## v0.1.0: Fifty-four years of UK factors (Day 1)

### Added

* `ukfactors.data`: loaders for AQR's *Value and Momentum Everywhere* and *Quality Minus Junk*
  workbooks, the Exeter Xfi Centre factors and portfolios, FRED's UK rate and GBP/USD, and
  today's FTSE 350 from Wikipedia and Yahoo. Every download is fingerprinted in a manifest.
* `ukfactors.panel`: one monthly panel in sterling, 1972 to 2026, converting AQR's dollar
  series to sterling.
* `ukfactors.stats`: Newey-West *t*-statistics, Lo (2002) Sharpe ratio standard errors,
  stationary-bootstrap intervals, drawdowns, decade statistics.
* `ukfactors.survivorship`: removes Yahoo's pence/pound and ×10 unit flips, builds 12-1
  momentum, and measures the survivorship bias.
* `ukfactors.validation`: nine checks, all passing on the real data.
* `ukf` command line: `data fetch|list`, `stats`, `validate`, `gallery`.
* Eleven charts, the Day 1 note, ADRs 0001-0003, 39 tests on synthetic data (98% coverage).

### Found

* AQR's UK factors are in US dollars.
* Exeter's downloadable files differ from the statistics in its 2013 paper, and end in June
  2016, not December 2017.
