"""Industry momentum: is UK momentum a bet on industries, on stocks within them, or both?

Moskowitz and Grinblatt (1999) found that US industries that did well over the past year keep
doing well, and that much of stock momentum disappears once stocks are measured against their
industry. This module builds the tools to ask the same of the UK:

* **industry portfolios**: equal-weighted monthly returns of twelve groups - the eleven ICB
  industries, with investment trusts (funds, not operating companies) split from Financials;
* **industry momentum**: rank industries on their own past return, buy the top three, sell the
  bottom three, with any formation and holding period (the Jegadeesh-Titman machinery of
  :mod:`ukfactors.momentum`);
* **decomposition**: a stock's formation return is its industry's plus its own, so stock momentum
  splits into an industry-momentum strategy (stocks ranked on their industry's return) and an
  industry-neutral one (stocks ranked on their return minus their industry's);
* **Fama-MacBeth regressions** of next month's stock return on both pieces at once;
* **lead-lag**: does one industry's return predict another's next month (Hou, 2007;
  Menzly and Ozbas, 2010);
* **placebo groups**: the same stocks in random groups of the same sizes, which tells whether
  industries matter or any grouping would do.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from . import analysis, sectors, stats
from . import momentum as M

Array = NDArray[np.float64]
TRUSTS = r"investment trusts?$|collective invest|equity invest|hedge fund"


def groups(constituents: pd.DataFrame) -> pd.Series:
    """Twelve groups by Yahoo ticker: the ICB industry, with investment trusts split from Financials.

    Real estate investment trusts are operating property companies and stay in Real Estate.
    """
    ind = sectors.by_ticker(constituents)
    sector = constituents.set_index("yahoo")["sector"].astype(str).str.lower().str.strip()
    trust = sector.str.contains(TRUSTS, regex=True) & ~sector.str.contains("real estate")
    out = ind.copy()
    out[trust.reindex(out.index).fillna(False).to_numpy()] = "Investment Trusts"
    return out.rename("group")


def industry_returns(returns: pd.DataFrame, group: pd.Series, min_members: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Equal-weighted monthly return of each group (NaN with fewer than ``min_members`` stocks), and member counts."""
    g = group.reindex(returns.columns)
    keep = g.notna().to_numpy()
    r = returns.loc[:, keep]
    labels = g[keep].to_numpy()
    means = r.T.groupby(labels).mean().T
    counts = r.notna().T.groupby(labels).sum().T
    return means.where(counts >= min_members), counts


def industry_momentum(ind_ret: pd.DataFrame, j: int = 11, k: int = 1, skip: int = 1, top: int = 3) -> M.Strategy:
    """Buy the ``top`` industries with the best formation return, sell the ``top`` worst, overlapping cohorts of ``k`` months."""
    n = ind_ret.shape[1]
    sig = M.formation_return(ind_ret, j, skip)
    return M.overlapping(ind_ret, sig, k, min_stocks=max(2 * top, n - 4), count=top)


def industry_signal(returns: pd.DataFrame, group: pd.Series, ind_ret: pd.DataFrame, j: int = 11, skip: int = 1) -> pd.DataFrame:
    """Each stock's signal is its industry's formation return (Moskowitz-Grinblatt's stock-level industry momentum)."""
    ind_sig = M.formation_return(ind_ret, j, skip)
    g = group.reindex(returns.columns)
    out = pd.DataFrame(np.nan, index=returns.index, columns=returns.columns)
    for name in ind_sig.columns:
        cols = g.index[g == name]
        out[cols] = np.repeat(ind_sig[[name]].to_numpy(), len(cols), axis=1)
    own = M.formation_return(returns, j, skip)
    return out.where(own.notna())


def neutral_signal(returns: pd.DataFrame, group: pd.Series, j: int = 11, skip: int = 1) -> pd.DataFrame:
    """Industry-neutral momentum: the stock's formation return minus the mean of its industry's members that month."""
    own = M.formation_return(returns, j, skip)
    g = group.reindex(returns.columns)
    keep = g.notna().to_numpy()
    o = own.loc[:, keep]
    labels = g[keep].to_numpy()
    mean = o.T.groupby(labels).transform("mean").T
    out = pd.DataFrame(np.nan, index=returns.index, columns=returns.columns)
    out.loc[:, o.columns] = (o - mean).to_numpy()
    return out


@dataclass(frozen=True)
class FamaMacBeth:
    names: list[str]
    coef: pd.DataFrame  # monthly slopes
    mean: Array  # mean slope, % a month per cross-sectional standard deviation
    tstat: Array  # Newey-West

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame({"mean": self.mean, "t_nw": self.tstat, "months": len(self.coef)}, index=self.names)


def fama_macbeth(returns: pd.DataFrame, predictors: dict[str, pd.DataFrame], min_stocks: int = 30) -> FamaMacBeth:
    """Each month, regress returns on cross-sectionally standardised predictors; average the slopes (Fama and MacBeth, 1973)."""
    names = list(predictors)
    rows = {}
    for date in returns.index:
        y = returns.loc[date]
        x = pd.DataFrame({n: predictors[n].loc[date] if date in predictors[n].index else np.nan for n in names})
        d = pd.concat([y.rename("__y__"), x], axis=1).dropna()
        if len(d) < min_stocks:
            continue
        xs = (d[names] - d[names].mean()) / d[names].std(ddof=0)
        if not np.isfinite(xs.to_numpy()).all():
            continue
        xv = np.column_stack([np.ones(len(d)), xs.to_numpy()])
        beta, *_ = np.linalg.lstsq(xv, d["__y__"].to_numpy(), rcond=None)
        rows[date] = beta[1:]
    coef = pd.DataFrame(rows, index=names).T
    means = coef.mean().to_numpy()
    ts = np.array([stats.nw_tstat(coef[n].to_numpy()) for n in names])
    return FamaMacBeth(names, coef, means, ts)


def cross_autocorrelation(ind_ret: pd.DataFrame, lag: int = 1) -> pd.DataFrame:
    """Correlation of each industry's return (rows) with each industry's return ``lag`` months later (columns), pairwise."""
    out = pd.DataFrame(np.nan, index=ind_ret.columns, columns=ind_ret.columns)
    for a in ind_ret.columns:
        lead = ind_ret[a].shift(lag)
        for b in ind_ret.columns:
            out.loc[a, b] = lead.corr(ind_ret[b])
    return out


def pair_months(ind_ret: pd.DataFrame, lag: int = 1) -> pd.DataFrame:
    """Number of months behind each pairwise lagged correlation."""
    ok = ind_ret.notna()
    return pd.DataFrame(
        {b: [int((ok[a].shift(lag, fill_value=False) & ok[b]).sum()) for a in ind_ret.columns] for b in ind_ret.columns},
        index=ind_ret.columns,
    )


def random_groups(group: pd.Series, seed: int) -> pd.Series:
    """The same stocks reassigned to groups of the same sizes at random."""
    rng = np.random.default_rng(seed)
    g = group.dropna()
    return pd.Series(rng.permutation(g.to_numpy()), index=g.index, name="group")


def placebo(
    returns: pd.DataFrame, group: pd.Series, draws: int = 200, j: int = 11, start: str | None = None, seed: int = 0
) -> pd.DataFrame:
    """Industry-momentum statistics for ``draws`` random groupings with the real group sizes."""
    rows = []
    for k in range(draws):
        rg = random_groups(group, seed + k)
        ir, _ = industry_returns(returns, rg)
        s = industry_momentum(ir, j).wml
        if start is not None:
            s = s.loc[start:]
        v = s.dropna().to_numpy()
        rows.append(
            {"draw": k, "mean": 12 * v.mean(), "sharpe": stats.annual_sharpe(v), "dispersion": float(ir.std(axis=1).mean())}
        )
    return pd.DataFrame(rows)


def dispersion(ind_ret: pd.DataFrame) -> pd.Series:
    """Cross-sectional standard deviation of industry returns each month."""
    return ind_ret.std(axis=1).rename("dispersion")


def spanning(y: pd.Series, x: pd.DataFrame) -> analysis.Regression:
    """Alpha of ``y`` on ``x``: whether a strategy earns anything the others do not explain."""
    return analysis.regress(y, x)


def winners_by_year(strategy: M.Strategy) -> pd.DataFrame:
    """Share of months in each calendar year that each industry spent in the long leg (+) or short leg (-)."""
    win = strategy.long.astype(float)
    lose = strategy.short.astype(float)
    net = win - lose
    valid = (strategy.long.any(axis=1)).to_numpy()
    net = net[valid]
    return net.groupby(pd.DatetimeIndex(net.index).year).mean()


def relative_returns(ind_ret: pd.DataFrame) -> pd.DataFrame:
    """Industry returns minus the cross-sectional mean of industries that month: the part an industry bet earns."""
    return ind_ret.sub(ind_ret.mean(axis=1), axis=0)


def own_autocorrelation(ind_ret: pd.DataFrame, lag: int = 1) -> pd.Series:
    """First-order autocorrelation of each industry's relative return."""
    rel = relative_returns(ind_ret)
    return pd.Series({c: rel[c].autocorr(lag) for c in rel.columns}, name=f"rho{lag}")


def within(
    returns: pd.DataFrame, group: pd.Series, name: str | None, j: int = 11, share: float = 0.2, exclude: bool = False
) -> M.Strategy:
    """Stock momentum among the members of one group (``exclude=True``: among everyone else), quintile legs, 15 stocks needed."""
    g = group.reindex(returns.columns)
    cols = g.index[(g != name) if exclude else (g == name)]
    sub = returns[cols]
    return M.overlapping(sub, M.formation_return(sub, j, 1), 1, share=share, min_stocks=min(15, len(cols)))
