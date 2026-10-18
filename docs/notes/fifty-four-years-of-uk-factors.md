# Fifty-four years of UK factors: what value and momentum have earned, and whether two sources agree

*Day 1 of 15 · uk-value-momentum v0.1.0 · data downloaded 18 October 2026*

## Summary

This note sets the foundation for a fifteen-day study of value and momentum in the UK stock
market. It assembles every free, survivorship-free source of UK factor returns into one
monthly panel in sterling, from January 1972 to July 2026. It then asks three questions
before any later day builds on the panel: what the factors have earned, whether independent
sources tell the same story, and how far the free alternatives would mislead.

The main findings:

1. **UK momentum is the strongest and steadiest premium in the panel.** AQR's rank-weighted
   momentum earned 7.2% a year in sterling from 1972 to 2026, with a Sharpe ratio of 0.49 and
   a Newey-West *t* of 3.3. Its 95% stationary-bootstrap interval is [0.22, 0.80]. The
   Fama-French-style UMD earned 12.8% a year from 1987 (Sharpe 0.83, *t* = 4.5).
2. **UK value is weak and fragile.** AQR's value earned 3.0% a year from 1981 (Sharpe 0.21,
   *t* = 1.1), and its interval includes zero. It has not regained its March 2007 peak, and it
   lost money in both the 1990s and the 2010s. Fama-French HML did better (Sharpe 0.49,
   *t* = 2.3). The gap between the two definitions is itself a finding for Day 5.
3. **Value and momentum hedge each other.** In the UK their correlation is −0.61. An equal
   mix of the two had a Sharpe ratio of 0.86 from 1981, against 0.21 for value and 0.54 for
   momentum alone over the same months.
4. **Two independent sources agree on momentum but not on value.** Over 1987 to 2016, AQR's
   and Exeter's UMD correlate 0.94. HML correlates only 0.77, and averages 4.9% a year in AQR
   against 1.5% in Exeter. A UK value result depends on how value is built.
5. **AQR's UK factors are in US dollars.** This is not documented. AQR's UK market correlates
   0.996 with Exeter's market translated into dollars, and only 0.82 with the sterling series.
   Every series here is converted (ADR 0002).
6. **Exeter's downloadable files are not the factors in its own paper.** The market reproduces
   the published Table 1 exactly. Momentum averages 0.99% a month in the files against 0.77% in
   the paper, and HML 0.39% against 0.31%.
7. **Free stock data is survivor data.** Today's FTSE 350 beat the market by 7.7% a year since
   2000, which no investor could have earned. Momentum built on those survivors is biased far
   less: 6.8% against 6.1%.

Every number above is computed by code in this repository and redrawn by `ukf gallery`. The
statistical machinery is held to independent references in [VALIDATION.md](../VALIDATION.md),
where all nine checks pass.

## 1. The question

Value (buying cheap stocks and selling expensive ones) and momentum (buying recent winners and
selling recent losers) are the two most studied anomalies in finance. They are also the two
that practitioners most often combine. Their US record is well known. The UK record is less
studied, and it is harder to measure: no single free source spans the past fifty years, and
the sources that exist disagree about definitions, universes and, as shown below, currency.

Day 1 asks:

* **What did each factor earn**, in sterling, with standard errors that respect
  autocorrelation and fat tails?
* **Do two independent sources agree**, month by month and on average?
* **What would a researcher who used free stock-level data get wrong**, and by how much?

The later days build on the answers. Day 2 dissects momentum, Day 5 value, Day 7 the crashes,
and Days 9 and 10 the costs. All of them use the panel built here.

## 2. Literature

Momentum was documented in US stocks by Jegadeesh and Titman (1993) and in the UK by Liu,
Strong and Xu (1999), who found significant UK momentum profits from 1977 to 1998 that
standard risk adjustments did not explain. Rouwenhorst (1998) showed the effect across twelve European markets. Carhart (1997)
added a momentum factor (UMD) to the Fama and French (1993) three-factor model, and that
construction is the one Exeter and AQR's companion series follow.

The value premium in the UK is more contested. Dimson, Nagel and Quigley (2003) found a
substantial UK value premium from 1955 to 2001 once small and illiquid stocks are handled
carefully. Gregory, Tharyan and Christidis (2013) built the Exeter factors and showed that
how well the Fama-French and Carhart models price UK portfolios depends on how the factors
are built, above all on the size breakpoints.

Asness, Moskowitz and Pedersen (2013) showed that value and momentum earn premia in every
market and asset class they studied, and that the two are negatively correlated everywhere.
That correlation is the basis for combining them. Their *Value and Momentum Everywhere* series
is the primary source here. Asness and Frazzini (2013) argued that the standard HML, which
divides book value by a market price up to eighteen months stale, mixes value with momentum.
They proposed "HML Devil", which uses current prices. Asness, Frazzini and Pedersen (2019)
added quality-minus-junk (QMJ).

On the statistics, Newey and West (1987, 1994) give the standard errors used throughout. Lo
(2002) shows that Sharpe ratios of autocorrelated returns need their own standard errors.
Politis and Romano (1994) give the stationary bootstrap. Brown, Goetzmann, Ibbotson and Ross
(1992) show how survivorship inflates measured performance. Harvey, Liu and Zhu (2016) argue
that after decades of factor mining a new factor should clear *t* > 3. UK momentum does; UK
value does not.

## 3. Data

### 3.1 Sources

**Table 1. Data sources.** All are downloaded by `ukf data fetch`, stored locally, never
committed, and fingerprinted (ADR 0001).

| Source | Series | UK coverage | Currency | Built from | Use here |
|---|---|---|---|---|---|
| AQR, *Value and Momentum Everywhere* | VAL, MOM (rank-weighted long/short), four markets | VAL 1981-07, MOM 1972-01, to 2026-07 | USD | Datastream to 1989, Compustat after; delisted firms included | primary series |
| AQR, *Quality Minus Junk* | MKT, SMB, HML, HML Devil, UMD, QMJ by country | MKT 1986-01, SMB/HML 1988-07, UMD 1987-01, QMJ 1993-07 | USD | as above | primary series |
| Exeter Xfi Centre (Gregory et al., 2013) | RMRF, SMB, HML, UMD, RF; sorted portfolios | 1980-10 to 2016-06 | GBP | London Share Price Database | independent check |
| FRED `IR3TIB01GBM156N` | UK three-month interbank rate (OECD) | 1957 to 2026-01 | GBP | OECD MEI | UK risk-free rate |
| FRED `DEXUSUK` | US dollars per pound, daily | 1971 to 2026 | n/a | Federal Reserve H.10 | currency conversion |
| Yahoo Finance and Wikipedia | adjusted month-end closes of today's FTSE 350 | 1999 to 2026-09 | GBP (pence or pounds) | Yahoo | survivorship measurement only |

Two departures from the plan are worth stating. The plan named the Bank of England as the
source of the UK risk-free rate. FRED's UK Treasury-bill series stops in 2017, so the OECD's
three-month interbank rate is used instead: it is available through FRED, runs to January
2026, and tracks Bank Rate closely. Second, the Exeter web page states coverage to December
2017, but the files themselves end in June 2016.

### 3.2 Factor construction

AQR's VAL and MOM are **rank-weighted** long/short portfolios. Within a market, each stock's
signal is ranked, and weights are proportional to the rank minus its cross-sectional mean, so
every stock is held. VAL uses book-to-price; MOM uses the return from month *t* − 12 to
*t* − 2. The companion SMB, HML and UMD follow Fama and French: 2×3 sorts on size and the
signal, with value-weighted legs.

Exeter's factors follow the same 2×3 recipe, but with UK breakpoints: the size cut is set at
the 350th-largest firm, not NYSE's median. That difference in universe and breakpoints
reappears in Section 5.2.

### 3.3 Currency

AQR does not document the currency of its country factors. ADR 0002 sets out the evidence that
they are in dollars, and Figure 5 shows it. With *x*_t the month's change in dollars per pound:

$$
f^{\text{GBP}}_t = \frac{f^{\text{USD}}_t}{1 + x_t}
\qquad\text{for a long/short factor,}
$$

$$
\text{MKT}^{\text{GBP}}_t = \frac{1 + \text{MKT}^{\text{USD}}_t + r^{\text{US}}_t}{1 + x_t} - 1 - r^{\text{UK}}_t
\qquad\text{for the market.}
$$

The long/short formula follows because a zero-cost position earning *r*_L − *r*_S in sterling
is worth (*r*_L − *r*_S)(1 + *x*) in dollars at month end. The UK rate is converted from an
annual percentage as *r*^UK_t = (1 + *R*_t/100)^(1/12) − 1.

### 3.4 The free survivor sample

Wikipedia lists today's FTSE 100 and FTSE 250. Yahoo has adjusted month-end closes for 349 of
them. Yahoo's London prices flip between pence and pounds (×100), and many investment trusts
flip by ×10. ADR 0003 explains why any series with a month above +400% or below −80% is
dropped whole rather than repaired. That rule drops 39 series and keeps 310. The last complete
month is September 2026.

## 4. Methods

For a monthly excess return series *r*_1, …, *r*_T:

**Annualised moments.** The mean is μ = 12 r̄, the volatility σ = √12 s, and the Sharpe ratio
SR = √12 r̄ / s, where *s* is the sample standard deviation.

**Newey-West t-statistic.** The long-run variance with Bartlett weights is

$$
\hat\Omega = \hat\gamma_0 + 2\sum_{j=1}^{q}\left(1-\frac{j}{q+1}\right)\hat\gamma_j,
\qquad
\hat\gamma_j = \frac1T\sum_{t=j+1}^{T}(r_t-\bar r)(r_{t-j}-\bar r),
$$

with the automatic lag *q* = ⌊4(T/100)^(2/9)⌋, which is 6 for the 655 months of MOM. The test
statistic is *t* = r̄ / √(Ω̂/T). The code reproduces statsmodels' HAC *t* to 1.3 × 10⁻¹⁵.

**Sharpe ratio standard error (Lo, 2002).** The monthly ratio's standard error is
√((1 + SR_m²/2)/T). Annualising multiplies it by

$$
\eta(q) = \frac{q}{\sqrt{q + 2\sum_{k=1}^{q-1}(q-k)\hat\rho_k}}, \qquad q = 12,
$$

which equals √12 when returns are serially uncorrelated and is smaller when they are
positively autocorrelated. In a Monte Carlo check, the formula's standard error is within 2.5%
of the simulated spread.

**Stationary bootstrap (Politis and Romano, 1994).** Each resample is built from blocks that
start at a uniformly random month and continue with probability 1 − 1/*b*, wrapping around the
end of the sample. Block lengths are therefore geometric with mean *b* = 6 months. Sharpe
intervals are the 2.5th and 97.5th percentiles of 2,000 resamples. The suite checks coverage
on an AR(1) with φ = 0.3: 90% at a nominal 95%. The intervals are a little narrow, so
borderline results are flagged as such.

**Drawdown.** The maximum fall of cumulative wealth *W*_t = ∏(1 + r_s) below its running peak,
with *W*_0 = 1, so a loss in the first month counts. It is checked against brute force.

**Survivors' momentum.** At the end of month *t* − 1, each stock with a full window gets the
signal ∏_{s=t−12}^{t−2}(1 + r_s) − 1. The strategy buys the top 30% and sells the bottom 30%,
equally weighted, holds them in month *t*, and needs at least 30 stocks. The suite checks that
the signal at *t* is exactly the return from *t* − 12 to *t* − 2, and that changing returns
from month *t* onward leaves it unchanged.

## 5. Results

### 5.1 What the factors earned

**Table 2. Summary statistics, monthly excess returns in sterling.** Means and volatilities are
annualised. The Sharpe interval is the 95% stationary bootstrap. MDD is the maximum drawdown.

| Factor | Source | Sample | Months | Mean | Vol | Sharpe | 95% interval | NW *t* | Skew | MDD |
|---|---|---|---|---|---|---|---|---|---|---|
| VAL | AQR | 1981-07 – 2026-07 | 541 | 3.0% | 14.2% | 0.21 | [−0.14, 0.59] | 1.14 | −0.28 | 70% |
| MOM | AQR | 1972-01 – 2026-07 | 655 | 7.2% | 14.6% | 0.49 | [0.22, 0.80] | 3.32 | −0.50 | 59% |
| MKT | AQR | 1986-01 – 2026-01 | 481 | 4.7% | 14.8% | 0.32 | [0.02, 0.68] | 2.03 | −0.94 | 52% |
| SMB | AQR | 1988-07 – 2026-07 | 457 | −2.3% | 11.8% | −0.20 | [−0.54, 0.14] | −1.11 | −0.23 | 71% |
| HML | AQR | 1988-07 – 2026-07 | 457 | 5.6% | 11.3% | 0.49 | [0.09, 0.94] | 2.33 | 0.14 | 49% |
| HML Devil | AQR | 1988-07 – 2026-07 | 457 | 3.7% | 13.7% | 0.27 | [−0.12, 0.66] | 1.34 | 0.21 | 61% |
| UMD | AQR | 1987-01 – 2026-07 | 475 | 12.8% | 15.4% | 0.83 | [0.42, 1.33] | 4.51 | −1.71 | 53% |
| QMJ | AQR | 1993-07 – 2026-07 | 397 | 5.3% | 9.3% | 0.57 | [0.19, 0.98] | 2.94 | −0.13 | 26% |
| RMRF | Exeter | 1980-10 – 2016-06 | 429 | 6.2% | 15.5% | 0.40 | [0.08, 0.76] | 2.49 | −0.99 | 50% |
| SMB | Exeter | 1980-10 – 2016-06 | 429 | 1.3% | 10.8% | 0.12 | [−0.23, 0.45] | 0.64 | −0.12 | 51% |
| HML | Exeter | 1980-10 – 2016-06 | 429 | 3.4% | 11.0% | 0.31 | [−0.16, 0.82] | 1.36 | −0.52 | 55% |
| UMD | Exeter | 1980-10 – 2016-06 | 429 | 11.8% | 14.9% | 0.79 | [0.40, 1.26] | 4.18 | −0.95 | 48% |

![Fifty-four years of UK value and momentum](../images/long-history.png)

*Figure 1. Growth of £1 in each factor, log scale, with UK bear markets and crises shaded.*

Three patterns stand out. **Momentum clears every hurdle.** Both constructions and both
sources give Sharpe ratios of 0.49 to 0.83, with *t*-statistics of 3.3 to 4.5, above Harvey,
Liu and Zhu's threshold of 3. **Value does not.** Rank-weighted VAL has a *t* of 1.1, HML
Devil 1.3 and Exeter's HML 1.4. Only AQR's standard HML clears 2. **Size is dead.** SMB is
negative in AQR's data since 1988 and insignificant in Exeter's.

The gap between HML (5.6%) and HML Devil (3.7%) is the Asness-Frazzini point in reverse. In
the US, using current prices *improves* HML. In the UK it lowers the mean. The stale price
in standard HML leaves it partly long recent winners, and recent winners did well in the UK:
HML correlates −0.31 with UMD, HML Devil −0.63. Day 5 decomposes this.

![A premium is an average over decades](../images/rolling-sharpe.png)

*Figure 2. Five-year rolling Sharpe ratios.*

A premium is an average over decades, not a promise for any five-year window. Figure 2 shows
that even momentum has had five-year stretches with nothing to show. Value spent most of
2010 to 2020 below zero.

### 5.2 Do two sources agree?

**Table 3. AQR against Exeter over their common months (sterling).**

| Factor | Months | AQR mean | Exeter mean | AQR vol | Exeter vol | Correlation | Tracking error |
|---|---|---|---|---|---|---|---|
| Market | 1986-01 – 2016-06 (366) | 4.1% | 5.1% | 15.5% | 15.4% | 0.996 | 1.4% |
| UMD | 1987-01 – 2016-06 (354) | 13.7% | 11.8% | 16.0% | 15.7% | 0.935 | 5.7% |
| SMB | 1988-07 – 2016-06 (336) | −2.5% | 0.2% | 12.1% | 11.6% | 0.833 | 6.9% |
| HML | 1988-07 – 2016-06 (336) | 4.9% | 1.5% | 11.7% | 11.3% | 0.767 | 7.9% |

![Two independent sources](../images/two-sources.png)

*Figure 3. AQR against Exeter, month by month.*

Momentum is robust to the source: the two UMDs correlate 0.94, and both earn more than 11% a
year. Value is not. AQR's HML earns three times Exeter's over the same months, with a tracking
error of 7.9% a year, as large as a typical factor's whole premium. The likely causes are
universe and breakpoints. Exeter splits size at the 350th firm and uses LSPD; AQR uses
Compustat with its own liquidity screens. Size is similarly fragile, with even the sign
differing between sources. These two disagreements are why every value result in later days
is reported in both sources where they overlap.

![The files are not the paper](../images/exeter-vs-paper.png)

*Figure 4. Exeter's downloadable factors against Table 1 of Gregory et al. (2013).*

**Table 4. Exeter's files against the published statistics, October 1980 to December 2010
(monthly %).**

| Factor | Mean: files | Mean: paper | SD: files | SD: paper | Skew: files | Skew: paper | Kurtosis: files | Kurtosis: paper |
|---|---|---|---|---|---|---|---|---|
| RMRF | 0.51 | 0.51 | 4.67 | 4.67 | −1.01 | −1.00 | 6.51 | 6.50 |
| SMB | 0.09 | 0.09 | 3.13 | 3.23 | 0.14 | 0.41 | 5.20 | 6.36 |
| HML | 0.39 | 0.31 | 3.31 | 3.40 | −0.61 | −0.67 | 9.36 | 10.04 |
| UMD | 0.99 | 0.77 | 4.35 | 4.16 | −0.96 | −1.26 | 8.93 | 10.87 |

The market matches to the printed precision. The kurtosis column is raw kurtosis, matching
the paper's convention. The factors do not match: the files were evidently rebuilt after
publication, probably with corrected data or revised breakpoints. Momentum's mean rose by
almost a third. A study that cites the paper's numbers while downloading the files reports
different results from those it cites.

### 5.3 Currency

![AQR's UK factors are in dollars](../images/currency.png)

*Figure 5. AQR's UK market against Exeter's in sterling and in dollars, and the gap against
the exchange rate.*

**Table 5. The currency evidence and the effect of conversion.**

| Statistic | Value |
|---|---|
| Correlation, AQR market vs Exeter sterling market (raw) | 0.823 |
| Correlation, AQR market vs Exeter market in dollars | 0.996 |
| Slope of (AQR − Exeter) on the pound's change | 1.016 |
| R² of that regression (366 months) | 0.978 |
| Correlation after conversion | 0.996 |
| UMD: dollar mean vs sterling mean | 12.6% vs 12.8% a year |
| HML: dollar mean vs sterling mean | 5.7% vs 5.6% a year |
| SMB: dollar mean vs sterling mean | −2.1% vs −2.3% a year |

For the market the currency is first-order: a dollar-based UK market return is a UK return
plus a currency position. For long/short factors it is second-order, 11 to 19 basis points a
year. It still matters, because it is systematic, and because a covariance with the market
inherits the market's currency error.

### 5.4 Distributions and drawdowns

![Fat tails](../images/distributions.png)

*Figure 6. Monthly return distributions against normals with the same mean and volatility.*

![The pain behind the premium](../images/drawdowns.png)

*Figure 7. Drawdowns.*

Every factor is fat-tailed, and momentum's left tail is the worst. UMD's skewness is −1.71.
Its worst month was April 2009 (−33%), the rebound after the financial crisis. The next worst
were November 2020 (−25%, the vaccine rally) and March 2000 (−17%). These are the "momentum
crashes" of Daniel and Moskowitz (2016): sharp market recoveries in which the shorted losers
rebound hardest. Day 7 models them.

Value's worst months tell a different story. February 2000 (−28%) and November 1999 (−23%)
were the peak of the technology bubble, when expensive stocks became more expensive. Value's
cumulative return peaked in March 2007 and has not recovered, a drawdown of 70% at its worst.
Momentum's peak was October 2020.

### 5.5 Diversification

![Value and momentum hedge each other](../images/world-correlations.png)

*Figure 8. Correlations of value and momentum across four markets, and of the UK factors.*

**Table 6. Correlations of UK factors, July 1993 to January 2026 (391 months, sterling).**

| | VAL | MOM | MKT | SMB | HML | UMD | QMJ |
|---|---|---|---|---|---|---|---|
| VAL | 1.00 | −0.65 | 0.11 | −0.17 | 0.70 | −0.53 | −0.31 |
| MOM | −0.65 | 1.00 | −0.26 | 0.00 | −0.35 | 0.86 | 0.40 |
| MKT | 0.11 | −0.26 | 1.00 | 0.04 | 0.12 | −0.33 | −0.53 |
| SMB | −0.17 | 0.00 | 0.04 | 1.00 | −0.20 | −0.10 | −0.32 |
| HML | 0.70 | −0.35 | 0.12 | −0.20 | 1.00 | −0.32 | −0.30 |
| UMD | −0.53 | 0.86 | −0.33 | −0.10 | −0.32 | 1.00 | 0.49 |
| QMJ | −0.31 | 0.40 | −0.53 | −0.32 | −0.30 | 0.49 | 1.00 |

Value and momentum correlate −0.65 in the UK over this window and −0.61 over the full sample.
The equal mix earns a Sharpe ratio of 0.86 since 1981, which is four times value's and 1.6
times momentum's. Its worst drawdown was 25%, against 70% for value and 59% for momentum. Quality is a hedge
against the market (−0.53) and sides with momentum (0.40). Day 6 asks whether quality is what
separates cheap stocks from value traps.

Across countries, value in one market correlates 0.44 to 0.69 with value in another, and
momentum 0.36 to 0.72. Japan is the least connected for both styles. The negative value-
momentum correlation holds in every market: from −0.52 to −0.63 within the same country, and
−0.25 to −0.51 across countries. This is the "everywhere" of Asness, Moskowitz and Pedersen.

### 5.6 Survivorship

![Free data remembers only the winners](../images/survivorship.png)

*Figure 9. Today's FTSE 350 against the market, and momentum on survivors against AQR's.*

**Table 7. Survivorship bias, 2000 to 2026.**

| Measure | Value |
|---|---|
| Series downloaded / excluded for impossible moves / kept | 349 / 39 / 310 |
| Survivors' equal-weighted return minus the UK market | **+7.7% a year** |
| Momentum on survivors: mean, vol, Sharpe, NW *t* | 6.8%, 16.5%, 0.41, 1.82 |
| AQR momentum, same 318 months: mean, vol, Sharpe, NW *t* | 6.1%, 17.2%, 0.36, 1.66 |
| Gap (survivors minus AQR) | +0.7% a year |
| Correlation | 0.77 |
| Stocks with a signal | 151 (2000) to 307 (2026) |

The survivors' premium is large and entirely spurious. It is the return of having known in
2000 which companies would still be listed in 2026. Part of it is a size tilt, because an
equal-weighted FTSE 350 leans towards the FTSE 250.

The momentum bias is small, and that is not obvious in advance. Survivorship lifts both the
past winners and the past losers, and a long/short strategy nets most of it out. It still
cannot be ignored: the survivors' version has a different sample, different volatility and a
correlation of only 0.77 with the clean factor.

### 5.7 Over time and across markets

![Decade by decade](../images/decades.png)

*Figure 10. Annualised returns by decade with 95% Newey-West intervals.*

**Table 8. Annualised mean by decade (NW *t* in brackets).**

| Decade | VAL | MOM | UMD | HML | MKT | QMJ |
|---|---|---|---|---|---|---|
| 1970s | – | −0.3% (−0.07) | – | – | – | – |
| 1980s | 9.5% (2.63) | 9.4% (3.29) | 6.1% (1.45) | – | 8.6% (0.84) | – |
| 1990s | −3.2% (−0.56) | 12.8% (2.45) | 15.7% (3.77) | −1.3% (−0.33) | 6.4% (1.51) | −0.8% (−0.30) |
| 2000s | 10.8% (1.74) | 4.8% (0.59) | 9.2% (1.07) | 14.6% (3.24) | −2.2% (−0.37) | 8.2% (2.11) |
| 2010s | −3.0% (−0.90) | 9.7% (2.73) | 18.2% (5.20) | −1.0% (−0.30) | 7.5% (2.57) | 8.1% (2.79) |
| 2020s | 0.8% (0.12) | 4.5% (0.77) | 8.5% (1.40) | 11.5% (2.23) | 6.0% (1.16) | 2.7% (0.67) |

Decades with fewer than 24 months are omitted. The 1980s market column starts in 1986 and the
2020s run to 2026.

Momentum has been positive in every decade since 1980, though its intervals cross zero in two
of them. The 1970s, the decade before AQR's value data begin, were flat. Value alternated:
strong in the 1980s and 2000s, negative in the 1990s and 2010s. HML recovered in the 2020s;
rank-weighted VAL did not. Intervals this wide are the reason a single decade proves little.

![Momentum works in the UK and Europe, value in Japan](../images/uk-vs-world.png)

*Figure 11. Sharpe ratios of AQR's value and momentum in four markets, 1982 to 2026, in
dollars, with 95% stationary-bootstrap intervals.*

**Table 9. Sharpe ratios across markets, 1982 to 2026 (dollars, as AQR publishes).**

| Market | Value | Momentum |
|---|---|---|
| UK | 0.22 [−0.15, 0.61] | 0.55 [0.24, 0.90] |
| US | 0.12 [−0.21, 0.46] | 0.37 [0.09, 0.68] |
| Continental Europe | 0.27 [−0.07, 0.64] | 0.57 [0.26, 0.91] |
| Japan | 0.56 [0.18, 0.97] | 0.12 [−0.17, 0.40] |
| Global average | 0.33 [−0.04, 0.74] | 0.49 [0.18, 0.82] |

The UK looks like continental Europe: strong momentum, weak value. Japan is the mirror image.
UK momentum's Sharpe ratio is half as large again as US momentum's.

## 6. Robustness

* **Two sources.** Every momentum result holds in Exeter's data, built from a different
  database with different breakpoints. Value results do not, and are reported as fragile.
* **Two constructions.** Rank-weighted (VAL, MOM) and 2×3 sorted (HML, UMD) factors agree in
  sign. Momentum is significant in both; value only in AQR's HML.
* **Currency.** Long/short conclusions are unchanged between dollars and sterling. Market
  conclusions are not, and the panel is in sterling.
* **Inference.** NW *t*-statistics, Lo standard errors and bootstrap intervals agree on which
  factors are significant. The bootstrap's measured coverage of 90% means intervals that only
  just exclude zero, such as the market's [0.02, 0.68], should be read as borderline.

## 7. Limitations

1. **AQR rebuilds history at every update.** Numbers can change between downloads. The manifest
   records the hashes, and this note's data are dated 18 October 2026.
2. **The sterling market ends in January 2026**, because FRED's UK rate does. The long/short
   factors run to July 2026.
3. **The interbank rate is not a T-bill.** It carries a small credit and liquidity premium:
   tens of basis points normally, more in 2007 to 2009. That understates sterling market excess
   returns slightly. It does not affect long/short factors.
4. **Exeter ends in June 2016**, so the two-source check covers only 1986 to 2016.
5. **The survivor sample's 39 exclusions** may include genuine extreme moves. The bias
   estimate is for the 310 clean series, not the full FTSE 350.
6. **No costs.** All returns are gross of trading costs and UK stamp duty (0.5% on purchases).
   Momentum turns over far more than value, so its net premium is smaller. Days 9 and 10
   measure this.
7. **Bootstrap coverage is 90% at a nominal 95%** in the AR(1) check. Intervals are slightly
   optimistic.
8. **Not yet validated against AMP (2013).** The plan called for reproducing AQR's published
   tables. Because AQR rebuilds its history, the current file no longer matches the 2013 paper's
   sample, so the check was replaced by the Exeter-paper reproduction. A reconstruction of
   AQR's factors from stock data waits for Day 2.

## 8. What comes next

Day 2 dissects momentum: its two legs, the twelve-month formation window, the skip month and
its dependence on market states, the setting for the crashes of Section 5.4.

## References

* Asness, C. S. and Frazzini, A. (2013). The devil in HML's details. *Journal of Portfolio
  Management* 39(4), 49–68.
* Asness, C. S., Frazzini, A. and Pedersen, L. H. (2019). Quality minus junk. *Review of
  Accounting Studies* 24(1), 34–112.
* Asness, C. S., Moskowitz, T. J. and Pedersen, L. H. (2013). Value and momentum everywhere.
  *Journal of Finance* 68(3), 929–985.
* Brown, S. J., Goetzmann, W., Ibbotson, R. G. and Ross, S. A. (1992). Survivorship bias in
  performance studies. *Review of Financial Studies* 5(4), 553–580.
* Carhart, M. M. (1997). On persistence in mutual fund performance. *Journal of Finance*
  52(1), 57–82.
* Daniel, K. and Moskowitz, T. J. (2016). Momentum crashes. *Journal of Financial Economics*
  122(2), 221–247.
* Dimson, E., Nagel, S. and Quigley, G. (2003). Capturing the value premium in the United
  Kingdom. *Financial Analysts Journal* 59(6), 35–45.
* Fama, E. F. and French, K. R. (1993). Common risk factors in the returns on stocks and bonds.
  *Journal of Financial Economics* 33(1), 3–56.
* Gregory, A., Tharyan, R. and Christidis, A. (2013). Constructing and testing alternative
  versions of the Fama-French and Carhart models in the UK. *Journal of Business Finance &
  Accounting* 40(1–2), 172–214.
* Harvey, C. R., Liu, Y. and Zhu, H. (2016). … and the cross-section of expected returns.
  *Review of Financial Studies* 29(1), 5–68.
* Jegadeesh, N. and Titman, S. (1993). Returns to buying winners and selling losers:
  implications for stock market efficiency. *Journal of Finance* 48(1), 65–91.
* Liu, W., Strong, N. and Xu, X. (1999). The profitability of momentum investing. *Journal of
  Business Finance & Accounting* 26(9–10), 1043–1091.
* Lo, A. W. (2002). The statistics of Sharpe ratios. *Financial Analysts Journal* 58(4), 36–52.
* Newey, W. K. and West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and
  autocorrelation consistent covariance matrix. *Econometrica* 55(3), 703–708.
* Newey, W. K. and West, K. D. (1994). Automatic lag selection in covariance matrix estimation.
  *Review of Economic Studies* 61(4), 631–653.
* Politis, D. N. and Romano, J. P. (1994). The stationary bootstrap. *Journal of the American
  Statistical Association* 89(428), 1303–1313.
* Rouwenhorst, K. G. (1998). International momentum strategies. *Journal of Finance* 53(1),
  267–284.

Data: AQR Capital Management, LLC, data library (accessed 18 October 2026); Exeter Xfi Centre
for Finance and Investment, UK factors (Gregory et al., 2013); Federal Reserve Bank of St.
Louis, FRED.
