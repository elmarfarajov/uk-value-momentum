# uk-value-momentum

**Value and momentum in the UK stock market, 1972–2026.** A fifteen-day empirical study:
factors, momentum's anatomy, value's lost decade, crashes, risk or mispricing, trading costs
and UK stamp duty, the 2014 AIM stamp-duty natural experiment, short sellers, Brexit and the
gilt crisis, machine learning, and a final working paper.

[![CI](https://github.com/elmarfarajov/uk-value-momentum/actions/workflows/ci.yml/badge.svg)](https://github.com/elmarfarajov/uk-value-momentum/actions/workflows/ci.yml)

![Fifty-four years of UK value and momentum](docs/images/long-history.png)

## Day 1 in numbers

| Factor (sterling) | Sample | Mean a year | Sharpe | 95% bootstrap interval | Newey-West *t* |
|---|---|---|---|---|---|
| Momentum (AQR, rank-weighted) | 1972–2026 | 7.2% | 0.49 | [0.22, 0.80] | 3.32 |
| UMD (AQR, Fama-French style) | 1987–2026 | 12.8% | 0.83 | [0.42, 1.33] | 4.51 |
| Value (AQR, rank-weighted) | 1981–2026 | 3.0% | 0.21 | [−0.14, 0.59] | 1.14 |
| HML (AQR) | 1988–2026 | 5.6% | 0.49 | [0.09, 0.94] | 2.33 |
| 50/50 value and momentum | 1981–2026 | | 0.86 | | |

* UK momentum clears a *t* of 3 in both constructions and both sources; UK value does not.
* Value and momentum correlate −0.61, so the mix's worst drawdown is 25%, against 70% for value
  alone.
* **AQR's UK factors are in US dollars** (undocumented). Everything here is converted to
  sterling ([ADR 0002](docs/adr/0002-aqr-in-dollars.md)).
* **Exeter's files are not its paper:** momentum averages 0.99% a month in the files against
  0.77% in Gregory et al. (2013).
* Free stock data is survivor data: today's FTSE 350 "beat" the market by 7.7% a year.

Read the full note: [Fifty-four years of UK factors](docs/notes/fifty-four-years-of-uk-factors.md).
All charts: [GALLERY.md](docs/GALLERY.md). Checks: [VALIDATION.md](docs/VALIDATION.md).

## Data, honestly

No raw data is in this repository. AQR's, Exeter's and Yahoo's files are theirs to license.
`ukf data fetch` downloads them into `data/raw` (gitignored) and records each file's URL, time
and SHA-256 in a manifest ([ADR 0001](docs/adr/0001-two-sources-kept-local.md)).

| Source | What | Terms |
|---|---|---|
| [AQR data library](https://www.aqr.com/Insights/Datasets) | value, momentum, market, SMB, HML, HML Devil, UMD, QMJ for the UK and other markets | cite AQR Capital Management, LLC |
| [Exeter Xfi Centre](https://business-school.exeter.ac.uk/research/centres/xfi/famafrench/) | UK SMB, HML, UMD, market, risk-free rate, 1980–2016 | academic use; cite Gregory, Tharyan and Christidis (2013) |
| [FRED](https://fred.stlouisfed.org/) | UK three-month interbank rate, GBP/USD | public domain |
| Yahoo Finance and Wikipedia | today's FTSE 350 prices, used only to measure survivorship bias | personal research use |

The tests and CI never need these files: `tests/conftest.py` writes synthetic data in each
source's own format. Validation checks that need the real data report SKIP without it.

## Usage

```bash
pip install -e ".[dev]"
ukf data fetch          # download everything into data/raw
ukf data list           # what is stored, with SHA-256
ukf stats               # summary statistics of every UK factor, in sterling
ukf validate --out docs/VALIDATION.md
ukf gallery             # redraw every chart in docs/images
```

## Layout

```
src/ukfactors/
  data/          store (manifest, hashes), aqr, exeter, fred, yahoo
  panel.py       one monthly panel in sterling (dollar-to-sterling conversion)
  stats.py       Newey-West, Lo (2002) Sharpe SE, stationary bootstrap, drawdowns
  survivorship.py  cleaning Yahoo's unit flips, 12-1 momentum, the survivorship bias
  validation.py  nine checks against independent methods and published numbers
  gallery/       every chart, registered so the gallery page and the images cannot drift
docs/notes/      one methodology note per day
docs/adr/        architecture decision records
```

## Related work

This project follows [meridian-investment-platform](https://github.com/elmarfarajov/meridian-investment-platform),
a portfolio management platform whose risk and attribution modules use factor models like
the ones measured here, and [private-markets-lab](https://github.com/elmarfarajov/private-markets-lab),
built alongside it.

## Roadmap

Fifteen days, one release each; see [ROADMAP.md](ROADMAP.md).

## Licence

Code: MIT. Data: see the table above. If you use this work, see [CITATION.cff](CITATION.cff).
