# ADR 0003: The free survivor sample is built to measure its bias, and corrupt series are dropped whole

**Status:** accepted (Day 1)

## Context

Free stock-level data for London covers the companies listed *today*. Yahoo Finance has
month-end adjusted closes for 349 of the current FTSE 350 (constituents from Wikipedia).
Later days need stock-level signals that factor files cannot give: industry momentum, short
interest and stamp-duty costs. The question is what that sample can be trusted for.

A first pass gave a nonsensical result: survivors *under*-performing the market by 11.6% a
year. The cause was Yahoo's units. London prices flip between pence and pounds, a factor of
100. Many investment trusts also flip by a factor of 10 (NAS.L moves between 47 and 465), and
often month after month. A repair that snapped every move to the nearest power of ten made
4,949 changes, far too many to trust. It could not tell a ×10 slip from a genuine ten-bagger
in a small company.

## Decision

1. **Any series with an impossible month is dropped whole.** That means a monthly return
   above +400% or below −80%. No months are repaired. Of 349 series, 39 are dropped and 310
   kept, and the count is reported in every chart that uses the sample. A FTSE 350 company that
   survived to today and had a genuine five-fold month or an 80% fall is rare enough to lose.
2. **The incomplete month is cut.** Yahoo's last row is the current, unfinished month
   (October 2026). Analysis stops at the last complete month, September 2026.
3. **The sample is used to measure survivorship bias, never as a substitute for AQR or
   Exeter.** Two measures: the survivors' equal-weighted average return against the UK market,
   and a 12-1 momentum strategy on the survivors against AQR's survivorship-free momentum.

## Consequences

* Survivors beat the market by **7.7% a year** from 2000 to 2026, which is the textbook
  survivorship premium (Brown, Goetzmann, Ibbotson and Ross, 1992). Part of it is a size tilt,
  because an equal-weighted FTSE 350 leans towards the FTSE 250.
* Momentum on survivors earns **6.8%** a year against AQR's **6.1%** over the same 318
  months, with a correlation of 0.77. The bias in a *long/short* strategy is small: survival
  lifts the past losers and the past winners alike, and the difference nets most of it out.
* The validation suite injects ×10 and ×100 flips into synthetic series. It requires all 10
  corrupted series to be caught and none of 40 clean ones to be flagged.
* Later days that need stock-level data must state this bias, or replace the sample.
