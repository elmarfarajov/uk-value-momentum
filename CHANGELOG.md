# Changelog

## v0.2.0: The anatomy of momentum (Day 2)

### Added

* `ukfactors.momentum`: formation returns, Jegadeesh-Titman overlapping portfolios and the J x K
  grid, event-time profiles, residual momentum (Blitz-Huij-Martens), the 52-week high, decile
  returns, quintile transitions, spells, industry composition, the UK market's sterling total
  return, market states (Cooper-Gutierrez-Hameed), conditional betas (Grundy-Martin), calendar-month
  and seasonal-dummy regressions, predictive regressions, summaries.
* `ukfactors.sectors`: ICB industries from Wikipedia's free-text sector labels; constituents now
  carry their sector.
* Twenty-two charts, the Day 2 note (19 tables), ADRs 0009-0011.
* Six validation checks (19 in all): Jegadeesh-Titman portfolios against a brute-force loop,
  residual momentum against statsmodels, signals that use only the past, event time against the
  K = 1 strategy, serially clean stock returns, unit flips that reverse.
* Eighteen tests (74 in all, 99% coverage).

### Fixed

* **Stock prices.** Yahoo's monthly bars mishandle dividend adjustments; prices are now daily
  adjusted closes sampled at month end (ADR 0011).
* **Cleaning.** Impossible-move ceiling +300% (was +400%), and unit flips of at least a factor of 3
  that reverse within 36 months are caught. 22 series excluded, 327 kept (39 and 310 before).
* **Day 1 corrected.** The survivors' premium is 4.0% a year (was 7.7%), and survivor momentum
  earns 4.1% against AQR's 6.1% (was 6.8%); see the Errata in the Day 1 note. Factor-level results
  are unchanged.
* The 52-week-high ranking lost months to ties; ties are now broken by 12-1 momentum.
* A sector rule matched "biotechnology" to Technology before Health Care.

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
