# ADR 0012: Twelve industries, investment trusts separate, exact leg counts

**Status:** accepted (Day 3)

## Context

Industry momentum needs industry portfolios. The free survivor sample (ADR 0009) carries each
company's ICB sector as free text from Wikipedia. `ukfactors.sectors` maps those labels to the
eleven ICB industries.

Two features of the UK market complicate the mapping:

1. **Investment trusts.** About 65 of today's FTSE 350 are closed-end funds holding diversified
   portfolios. ICB files them under Financials, but their returns are those of other companies'
   shares. Mixing them with banks and insurers would blur both groups.
2. **Small groups.** With twelve groups, a "top three minus bottom three" strategy is a 25% share.
   That share sits exactly on a percentile-rank boundary: `rank / 12 > 1 − 0.25` is a
   floating-point comparison of 0.75 with 0.75.

## Decision

1. **Twelve groups.** The eleven ICB industries, plus investment trusts (sector labels matching
   "investment trust", "collective investment", "equity investment" or "hedge fund"). Real estate
   investment trusts are operating property companies and stay in Real Estate (tested).
2. **Equal-weighted industry returns, at least three members a month.** Telecommunications has
   three or more members only from 2014, and Technology from 2005.
3. **Exact leg counts.** `momentum.ranks` and `overlapping` take an optional `count`. When given,
   each leg holds exactly that many names by rank order, ties broken by column order. Industry
   strategies use `count = 3`.
4. **Industry-neutral momentum** ranks each stock on its formation return minus the mean formation
   return of its industry that month. Within each industry the signals sum to zero (a validation
   check).
5. **Placebo groupings** keep each stock's returns and each group's size and shuffle membership
   only, 200 times.

## Consequences

- The first Day 3 run used `share = 3/12 + 1e-9`. That put four industries in the long leg and three
  in the short leg in every month. One-month industry momentum read 4.5% a year (t = 1.6); with
  exact legs it is 5.5% (t = 2.1). The bug was caught by a test that checks leg sizes, and fixed
  before any result was published.
- Today's sector labels are applied to each company's whole history, so a company that changed
  industry is misclassified before the change.
- With twelve groups, industry momentum has few degrees of freedom. Results are reported with the
  placebo distribution, so a Sharpe ratio can be read against what random groups give.
