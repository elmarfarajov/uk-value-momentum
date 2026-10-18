# Changelog

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
