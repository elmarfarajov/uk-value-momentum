"""Validation suite: every statistic and every data step held to an independent method or a published number.

``ukf validate`` runs it; ``ukf validate --out docs/VALIDATION.md`` records it. Checks that need the
local raw data are reported as SKIP where it is absent (in CI), never silently dropped.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import analysis, industry, momentum, stats, survivorship
from . import tsmom as tsm
from .data import store

Result = tuple[str, str, str, bool | None]  # reference, result, error, passed (None: skipped)


@dataclass
class Check:
    area: str
    check: str
    reference: str
    result: str
    error: str
    status: str
    seconds: float


def _ar1(n: int, phi: float, mu: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    e = rng.normal(0.0, sigma, n + 200)
    x = np.empty_like(e)
    x[0] = 0.0
    for t in range(1, e.size):
        x[t] = phi * x[t - 1] + e[t]
    return np.asarray(mu + x[200:])


def run_validation(fast: bool = False) -> pd.DataFrame:
    checks: list[Check] = []

    def add(area: str, name: str, fn: Callable[[], Result]) -> None:
        start = time.perf_counter()
        reference, result, error, passed = fn()
        status = "SKIP" if passed is None else ("PASS" if passed else "FAIL")
        checks.append(Check(area, name, reference, result, error, status, time.perf_counter() - start))

    def nw_vs_statsmodels() -> Result:
        try:
            import statsmodels.api as sm
        except ImportError:  # statsmodels is a development extra, not a dependency of the wheel
            return "statsmodels OLS on a constant, HAC (Bartlett) errors", "needs statsmodels", "-", None

        rng = np.random.default_rng(1)
        worst = 0.0
        for phi in (0.0, 0.2, 0.5):
            x = _ar1(500, phi, 0.005, 0.04, rng)
            lags = stats.nw_lags(x.size)
            fit = sm.OLS(x, np.ones_like(x)).fit(cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False})
            worst = max(worst, abs(stats.nw_tstat(x, lags) - float(fit.tvalues[0])))
        return "statsmodels OLS on a constant, HAC (Bartlett) errors", "AR(1) phi = 0, 0.2, 0.5", f"{worst:.1e}", worst < 1e-8

    def sharpe_se_monte_carlo() -> Result:
        rng = np.random.default_rng(2)
        n, sims = 480, 1000 if fast else 4000
        draws = rng.normal(0.006, 0.04, (sims, n))
        estimates = np.sqrt(12) * draws.mean(axis=1) / draws.std(axis=1, ddof=1)
        empirical = float(estimates.std())
        lo = float(np.mean([stats.sharpe_se(d) for d in draws[:200]]))
        gap = abs(lo / empirical - 1)
        return (
            "Monte Carlo spread of the Sharpe ratio, i.i.d. normal",
            f"Lo SE {lo:.4f}, simulated {empirical:.4f}",
            f"{100 * gap:.1f}%",
            gap < 0.08,
        )

    def bootstrap_coverage() -> Result:
        rng = np.random.default_rng(3)
        sims, reps = (60, 200) if fast else (200, 400)
        mu, hits = 0.005, 0
        for k in range(sims):
            x = _ar1(300, 0.3, mu, 0.04, rng)
            boot = stats.stationary_bootstrap(x, lambda v: float(v.mean()), reps=reps, seed=k)
            lo, hi = np.percentile(boot, [2.5, 97.5])
            hits += lo <= mu <= hi
        rate = hits / sims
        return (
            "true mean of an AR(1), phi = 0.3",
            f"{sims} samples, nominal 95%",
            f"coverage {100 * rate:.0f}%",
            0.85 <= rate <= 0.99,
        )

    def drawdown_brute_force() -> Result:
        rng = np.random.default_rng(4)
        worst = 0.0
        for _ in range(50):
            x = rng.normal(0.004, 0.05, 240)
            w = np.concatenate([[1.0], np.cumprod(1 + x)])
            brute = max(1 - w[j] / w[: j + 1].max() for j in range(w.size))
            worst = max(worst, abs(stats.max_drawdown(x) - brute))
        return "brute force over every peak and trough", "50 random paths", f"{worst:.1e}", worst < 1e-12

    def unit_flips() -> Result:
        rng = np.random.default_rng(5)
        n = 300
        clean = pd.DataFrame(np.exp(np.cumsum(rng.normal(0.006, 0.08, (n, 40)), axis=0)) * 100.0)
        flipped = clean.copy()
        for j in range(10):
            months = rng.choice(np.arange(10, n), size=5, replace=False)
            factor = 100.0 if j % 2 else 10.0
            flipped.iloc[months, j] = flipped.iloc[months, j] / factor
        result = survivorship.clean(flipped)
        caught = set(result.excluded) == {str(j) for j in range(10)}
        false = survivorship.clean(clean).excluded
        return (
            "series with injected x10 and x100 flips",
            f"flagged {len(result.excluded)} of 10 corrupted; {len(false)} of 40 clean flagged",
            "exact" if caught and not false else "mismatch",
            caught and not false,
        )

    def no_look_ahead() -> Result:
        rng = np.random.default_rng(6)
        ret = pd.DataFrame(rng.normal(0, 0.05, (60, 5)))
        sig = survivorship.momentum_signal(ret)
        t = 30
        expected = np.expm1(np.log1p(ret.iloc[t - 12 : t - 1]).sum())
        gap = float(np.max(np.abs(sig.iloc[t] - expected)))
        later = ret.copy()
        later.iloc[t:] = 9.9  # changing returns from month t onwards must not change the signal at t
        unchanged = np.allclose(survivorship.momentum_signal(later).iloc[t], sig.iloc[t])
        return (
            "signal at t = return from t-12 to t-2",
            "synthetic returns, future perturbed",
            f"{gap:.1e}",
            gap < 1e-12 and unchanged,
        )

    def exeter_market_reproduces_paper() -> Result:
        if not store.available(["exeter_monthlyfactors.zip"]):
            return "Gregory, Tharyan and Christidis (2013), Table 1", "needs local data", "-", None
        from .gallery.foundation import PUBLISHED, exeter_moments

        ours = exeter_moments()["RMRF"]
        gaps = [abs(round(o, 2) - p) for o, p in zip(ours, PUBLISHED["RMRF"], strict=True)]
        return (
            "GTC (2013) Table 1, Oct 1980 - Dec 2010: market 0.51, 4.67, -1.00, 6.50",
            f"files: {ours[0]:.2f}, {ours[1]:.2f}, {ours[2]:.2f}, {ours[3]:.2f}",
            f"max {max(gaps):.2f} at the printed precision",
            max(gaps) <= 0.011,
        )

    def sterling_conversion() -> Result:
        if not store.available(["aqr_qmj_monthly.xlsx", "exeter_monthlyfactors.zip", "fred_gbpusd.csv", "fred_uk_rate.csv"]):
            return "Exeter's sterling market", "needs local data", "-", None
        from . import panel
        from .data import aqr, exeter, fred

        p = panel.build()
        j = p[["MKT", "EX_RMRF"]].dropna()
        converted = float(j["MKT"].corr(j["EX_RMRF"]))
        raw = pd.concat(
            [aqr.uk()["MKT"], exeter.factors()["RMRF"], fred.gbpusd().pct_change().rename("FX")], axis=1, sort=True
        ).dropna()
        slope = float(np.polyfit(raw["FX"], raw["MKT"] - raw["RMRF"], 1)[0])
        return (
            "Exeter's market in sterling; the unconverted gap loads 1:1 on GBP/USD",
            f"converted correlation {converted:.4f}; FX loading of the gap {slope:.3f}",
            f"{abs(slope - 1):.3f} from one",
            converted > 0.99 and abs(slope - 1) < 0.05,
        )

    def sources_agree_on_momentum() -> Result:
        if not store.available(["aqr_qmj_monthly.xlsx", "exeter_monthlyfactors.zip"]):
            return "Exeter UMD", "needs local data", "-", None
        from . import panel

        j = panel.build()[["UMD", "EX_UMD"]].dropna()
        c = float(j["UMD"].corr(j["EX_UMD"]))
        return (
            "Exeter's UMD, built from different data",
            f"{j.index[0]:%Y-%m} to {j.index[-1]:%Y-%m}",
            f"correlation {c:.3f}",
            c > 0.9,
        )

    def regression_vs_statsmodels() -> Result:
        try:
            import statsmodels.api as sm
        except ImportError:
            return "statsmodels OLS, HAC (Bartlett) errors", "needs statsmodels", "-", None
        rng = np.random.default_rng(7)
        x = pd.DataFrame(rng.normal(0, 0.04, (480, 3)), columns=["a", "b", "c"])
        y = pd.Series(0.004 + x @ np.array([0.3, -0.5, 0.1]) + _ar1(480, 0.3, 0.0, 0.02, rng))
        ours = analysis.regress(y, x)
        fit = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HAC", cov_kwds={"maxlags": stats.nw_lags(480), "use_correction": False})
        gap = float(max(np.max(np.abs(ours.coef - fit.params.to_numpy())), np.max(np.abs(ours.tstat - fit.tvalues.to_numpy()))))
        return "statsmodels OLS with three regressors, HAC errors", "coefficients and t-statistics", f"{gap:.1e}", gap < 1e-8

    def acf_vs_statsmodels() -> Result:
        try:
            from statsmodels.tsa.stattools import acf as sm_acf
        except ImportError:
            return "statsmodels acf", "needs statsmodels", "-", None
        x = pd.Series(_ar1(600, 0.4, 0.0, 0.03, np.random.default_rng(8)))
        gap = float(np.max(np.abs(analysis.acf(x, 24).to_numpy() - sm_acf(x, nlags=24, fft=False)[1:])))
        return "statsmodels acf, lags 1-24", "AR(1) phi = 0.4", f"{gap:.1e}", gap < 1e-12

    def tangency_vs_grid() -> Result:
        rng = np.random.default_rng(9)
        z = rng.multivariate_normal([0.003, 0.006], [[0.0016, -0.0009], [-0.0009, 0.0020]], 600)
        a, b = pd.Series(z[:, 0]), pd.Series(z[:, 1])
        w = analysis.tangency_weight(a, b)
        grid = analysis.mix_frontier(a, b, np.linspace(0, 1, 10001))
        best = float(grid.index.to_numpy()[int(np.argmax(grid["sharpe"].to_numpy()))])
        return (
            "brute-force search over 10,001 weights",
            f"closed form {w:.4f}, search {best:.4f}",
            f"{abs(w - best):.1e}",
            abs(w - best) < 2e-4,
        )

    def exeter_factors_rebuild() -> Result:
        names = ["exeter_monthlyfactors.zip", "exeter_6ports_size_bm.zip", "exeter_6ports_size_mom.zip"]
        if not store.available(names):
            return "Exeter's six 2x3 portfolios", "needs local data", "-", None
        from .data import exeter

        f = exeter.factors()
        gaps = []
        for kind, ports in (("HML", "6ports_size_bm"), ("SMB", "6ports_size_bm"), ("UMD", "6ports_size_mom")):
            rebuilt = analysis.rebuild_factor(exeter.portfolios(ports), kind)
            j = pd.concat([rebuilt, f[kind]], axis=1).dropna()
            gaps.append(float((j.iloc[:, 0] - j.iloc[:, 1]).abs().max()))
        return (
            "HML, SMB and UMD rebuilt from the six portfolios",
            f"max monthly gap HML {gaps[0]:.1e}, SMB {gaps[1]:.1e}, UMD {gaps[2]:.1e}",
            f"{max(gaps):.1e}",
            max(gaps) < 1e-6,
        )

    def jt_vs_brute_force() -> Result:
        rng = np.random.default_rng(31)
        ret = pd.DataFrame(rng.normal(0.01, 0.08, (80, 60)), index=pd.date_range("2000-01-31", periods=80, freq="ME"))
        ret.iloc[5:15, 3] = np.nan  # a stock missing for a while
        j, k, skip = 6, 3, 1
        fast_ = momentum.jt(ret, j, k, skip).wml
        r = ret.to_numpy()
        n = r.shape[0]
        sig = np.full_like(r, np.nan)
        for h in range(n):
            lo, hi = h - j - skip, h - skip  # months lo .. hi - 1
            if lo >= 0:
                window = r[lo:hi]
                ok = np.isfinite(window).all(axis=0)
                sig[h, ok] = np.prod(1 + window[:, ok], axis=0) - 1
        slow = np.full(n, np.nan)
        for m in range(n):
            spreads = []
            for c in range(m - k + 1, m + 1):
                if c < 0 or np.isfinite(sig[c]).sum() < 30:
                    break
                s_ = sig[c]
                ranks = pd.Series(s_).rank(pct=True).to_numpy()
                win = ranks > 0.9
                lose = ranks <= 0.1
                rw, rl = r[m][win], r[m][lose]
                spreads.append(np.nanmean(rw) - np.nanmean(rl))
            if len(spreads) == k:
                slow[m] = float(np.mean(spreads))
        gap = float(np.nanmax(np.abs(fast_.to_numpy() - slow)))
        same = bool(np.array_equal(np.isfinite(fast_.to_numpy()), np.isfinite(slow)))
        return (
            "a loop over cohorts and months, written separately",
            "J = 6, K = 3, 60 stocks, 80 months",
            f"{gap:.1e}",
            gap < 1e-12 and same,
        )

    def residual_vs_statsmodels() -> Result:
        try:
            import statsmodels.api as sm
        except ImportError:
            return "statsmodels OLS residuals", "needs statsmodels", "-", None
        rng = np.random.default_rng(32)
        idx = pd.date_range("2000-01-31", periods=60, freq="ME")
        fac = pd.DataFrame(rng.normal(0, 0.04, (60, 3)), index=idx, columns=["m", "s", "v"])
        ret = pd.DataFrame(fac.to_numpy() @ rng.normal(1, 0.5, (3, 5)) + rng.normal(0, 0.05, (60, 5)), index=idx)
        sig = momentum.residual_signal(ret, fac, window=36, j=11, skip=1)
        h = 50
        y = ret.iloc[h - 36 : h, 2]
        fit = sm.OLS(y.to_numpy(), sm.add_constant(fac.iloc[h - 36 : h].to_numpy())).fit()
        form = fit.resid[36 - 12 : 36 - 1]
        expected = form.sum() / form.std(ddof=1)
        gap = abs(float(sig.to_numpy()[h, 2]) - expected)
        return "statsmodels OLS on the same 36 months, residuals t-12 to t-2", "one stock, one month", f"{gap:.1e}", gap < 1e-10

    def signals_no_look_ahead() -> Result:
        rng = np.random.default_rng(33)
        idx = pd.date_range("2000-01-31", periods=60, freq="ME")
        ret = pd.DataFrame(rng.normal(0.01, 0.06, (60, 8)), index=idx)
        mkt = pd.Series(rng.normal(0.006, 0.04, 60), index=idx)
        t = 40
        later = ret.copy()
        later.iloc[t:] = 0.5
        mlater = mkt.copy()
        mlater.iloc[t:] = -0.5
        same = [
            np.allclose(momentum.formation_return(ret, 11, 1).iloc[t], momentum.formation_return(later, 11, 1).iloc[t]),
            np.allclose(momentum.high_ratio(ret).iloc[t], momentum.high_ratio(later).iloc[t]),
        ]
        past = pd.Series(np.log1p(mkt.to_numpy()), index=idx).rolling(24).sum().shift(1)
        past_l = pd.Series(np.log1p(mlater.to_numpy()), index=idx).rolling(24).sum().shift(1)
        same.append(bool(np.isclose(past.iloc[t], past_l.iloc[t])))
        return (
            "signals at t unchanged when months t onwards change",
            "12-1, 52-week high, market state",
            f"{sum(same)}/3 unchanged",
            all(same),
        )

    def event_time_identity() -> Result:
        rng = np.random.default_rng(34)
        ret = pd.DataFrame(rng.normal(0.01, 0.08, (90, 50)), index=pd.date_range("2000-01-31", periods=90, freq="ME"))
        sig = momentum.formation_return(ret, 11, 1)
        e = momentum.event_time(ret, sig, horizon=1)
        k1 = momentum.overlapping(ret, sig, 1).wml.dropna()
        gap = abs(float(e["mean"].to_numpy()[0]) - float(k1.mean()))
        return "event time, month 1 = the K = 1 strategy's mean", "50 stocks, 90 months", f"{gap:.1e}", gap < 1e-12

    def stock_returns_clean() -> Result:
        if not store.available(["yahoo_ftse350_monthly.csv"]):
            return "pooled autocorrelation of monthly stock returns", "needs local data", "-", None
        from .data import yahoo

        ret = survivorship.clean(yahoo.prices(), pd.Timestamp("2026-09-30")).returns
        rho = []
        for lag in (1, 2, 3):
            j_ = pd.concat([ret.shift(lag).stack(), ret.stack()], axis=1).dropna()
            rho.append(float(j_.corr().iloc[0, 1]))
        worst = max(abs(x) for x in rho)
        return (
            "real monthly returns are close to serially uncorrelated (Yahoo's monthly bars gave -0.14 and +0.32)",
            f"lags 1-3: {rho[0]:+.3f}, {rho[1]:+.3f}, {rho[2]:+.3f}",
            f"max {worst:.3f}",
            worst < 0.05,
        )

    def unit_flip_pairs() -> Result:
        rng = np.random.default_rng(35)
        n = 200
        prices = pd.DataFrame(np.exp(np.cumsum(rng.normal(0.006, 0.07, (n, 30)), axis=0)) * 100.0)
        for c in range(5):  # five-fold unit flips lasting a few months, then reversing
            start = int(rng.integers(20, 150))
            prices.iloc[start : start + int(rng.integers(1, 30)), c] *= 5.0
        prices.iloc[100:, 10] *= 0.25  # a genuine 75% crash that never recovers
        prices.iloc[60:, 11] *= 2.8  # a genuine near-tripling that holds
        cleaned = survivorship.clean(prices)
        caught = {str(i) for i in range(5)} <= set(cleaned.excluded)
        kept = not ({"10", "11"} & set(cleaned.excluded))
        return (
            "five-fold flips that reverse are dropped; a lasting crash and rally are kept",
            f"excluded {cleaned.excluded}",
            "exact" if caught and kept else "mismatch",
            caught and kept,
        )

    def _toy() -> tuple[pd.DataFrame, pd.Series]:
        rng = np.random.default_rng(41)
        idx = pd.date_range("2000-01-31", periods=60, freq="ME")
        ret = pd.DataFrame(rng.normal(0.01, 0.06, (60, 40)), index=idx, columns=[f"s{i}" for i in range(40)])
        ret.iloc[:10, :3] = np.nan
        grp = pd.Series([f"g{i % 5}" for i in range(40)], index=ret.columns)
        return ret, grp

    def industry_returns_brute() -> Result:
        ret, grp = _toy()
        ir, _ = industry.industry_returns(ret, grp, min_members=1)
        gap = max(
            float(np.nanmax(np.abs(ir[g].to_numpy() - ret[grp.index[grp == g]].mean(axis=1).to_numpy()))) for g in ir.columns
        )
        return "industry return = mean of its members each month", "40 stocks, 5 groups, gaps", f"{gap:.1e}", gap < 1e-14

    def neutral_sums_to_zero() -> Result:
        ret, grp = _toy()
        n = industry.neutral_signal(ret, grp)
        sums = n.T.groupby(grp.to_numpy()).sum(min_count=1).T
        gap = float(np.nanmax(np.abs(sums.to_numpy())))
        return "industry-neutral signals sum to zero within each industry", "every month and group", f"{gap:.1e}", gap < 1e-12

    def fama_macbeth_vs_ols() -> Result:
        try:
            import statsmodels.api as sm
        except ImportError:
            return "statsmodels OLS each month", "needs statsmodels", "-", None
        ret, grp = _toy()
        own = momentum.formation_return(ret, 6, 1)
        fm = industry.fama_macbeth(ret, {"own": own}, min_stocks=10)
        date = fm.coef.index[5]
        d = pd.concat([ret.loc[date].rename("y"), own.loc[date].rename("x")], axis=1).dropna()
        x = (d["x"] - d["x"].mean()) / d["x"].std(ddof=0)
        ols = float(sm.OLS(d["y"].to_numpy(), sm.add_constant(x.to_numpy())).fit().params[1])
        gap = abs(float(fm.coef.loc[date, "own"]) - ols)
        return "Fama-MacBeth monthly slope = OLS on the standardised signal", "one cross-section", f"{gap:.1e}", gap < 1e-12

    def placebo_keeps_sizes() -> Result:
        _, grp = _toy()
        same = all(
            industry.random_groups(grp, k).value_counts().sort_index().equals(grp.value_counts().sort_index()) for k in range(20)
        )
        moved = float(np.mean([(industry.random_groups(grp, k) != grp).mean() for k in range(20)]))
        return "random groupings keep every group's size", "20 draws", f"{100 * moved:.0f}% of stocks moved", same and moved > 0.5

    def gilt_against_cash_flows() -> Result:
        # with 10 + 1/12 years at purchase, 20 whole coupons remain after a month: price = explicit sum of cash flows
        y = pd.Series([0.05, 0.05, 0.062, 0.031, 0.031])
        r = tsm.gilt_returns(y, maturity=10.0 + 1.0 / 12.0)
        worst = 0.0
        for t in range(1, len(y)):
            c, h = y[t - 1] / 2.0, y[t] / 2.0
            price = sum(c * (1 + h) ** -k for k in range(1, 21)) + (1 + h) ** -20
            worst = max(worst, abs(r.iloc[t - 1] - (price - 1 + y[t - 1] / 12.0)))
        flat = abs(r.iloc[0] - 0.05 / 12.0)
        return (
            "par-bond price against the sum of its cash flows; flat yield earns y/12",
            "4 months",
            f"{max(worst, flat):.1e}",
            max(worst, flat) < 1e-12,
        )

    def vol_target_hit() -> Result:
        # assets with 10% to 40% volatility end up with equal risk; the level overshoots the 10% target a little,
        # because 1 / (a short EWMA estimate) is biased upwards (Jensen's inequality)
        rng = np.random.default_rng(31)
        idx = pd.date_range("1950-01-31", periods=900, freq="ME")
        vols = np.array([0.1, 0.2, 0.3, 0.4])
        r = pd.DataFrame(rng.normal(0.0, 1.0, (900, 4)) * vols / np.sqrt(12), index=idx)
        realised = np.sqrt(12) * tsm.tsmom(r).by_asset.iloc[24:].std().to_numpy()
        spread = float(realised.max() / realised.min())
        return (
            "scaled positions carry equal risk whatever the asset's volatility",
            f"10-40% volatility -> {100 * realised.min():.1f}-{100 * realised.max():.1f}% (target 10%)",
            f"max/min {spread:.3f}",
            spread < 1.08 and 0.09 < realised.mean() < 0.135,
        )

    def planted_trend_found() -> Result:
        rng = np.random.default_rng(32)
        idx = pd.date_range("1950-01-31", periods=900, freq="ME")
        mu = np.zeros((900, 3))
        for t in range(1, 900):
            mu[t] = 0.97 * mu[t - 1] + rng.normal(0, 0.004, 3)
        trend = pd.DataFrame(mu + rng.normal(0, 0.04, (900, 3)), index=idx)
        noise = pd.DataFrame(rng.normal(0, 0.04, (900, 3)), index=idx)
        a = tsm.summary(tsm.tsmom(trend).portfolio)["sharpe"]
        b = tsm.summary(tsm.tsmom(noise).portfolio)["sharpe"]
        return (
            "persistent expected returns give a positive Sharpe; noise does not",
            "AR(1) drift vs iid",
            f"{a:.2f} vs {b:.2f}",
            a > 0.4 and abs(b) < 0.3,
        )

    def pooled_vs_statsmodels() -> Result:
        try:
            import statsmodels.api as sm
        except ImportError:
            return "pooled slope and month-clustered t against statsmodels", "needs statsmodels", "-", None

        rng = np.random.default_rng(33)
        idx = pd.date_range("1980-01-31", periods=300, freq="ME")
        r = pd.DataFrame(rng.normal(0.005, 0.05, (300, 3)), index=idx)
        ours = tsm.predictability(r, 1).iloc[0]
        vol = tsm.ex_ante_vol(r)
        z = r / vol.shift(1)
        st = pd.concat([z.stack().rename("y"), z.shift(1).stack().rename("x")], axis=1).dropna()
        g = st.index.get_level_values(0).astype("int64")
        fit = sm.OLS(st["y"], sm.add_constant(st["x"])).fit(cov_type="cluster", cov_kwds={"groups": g})
        n, k, groups = len(st), 2, len(set(g))
        t_ours = ours["t"] / np.sqrt(groups / (groups - 1) * (n - 1) / (n - k))  # statsmodels' small-sample factor
        gap = max(abs(ours["beta"] - fit.params["x"]), abs(t_ours - fit.tvalues["x"]))
        return "pooled slope and month-clustered t against statsmodels", "3 assets, 300 months", f"{gap:.1e}", gap < 1e-8

    add("Statistics", "Newey-West t against statsmodels", nw_vs_statsmodels)
    add("Statistics", "Sharpe ratio standard error (Lo 2002)", sharpe_se_monte_carlo)
    add("Statistics", "Stationary bootstrap coverage", bootstrap_coverage)
    add("Statistics", "Maximum drawdown", drawdown_brute_force)
    add("Statistics", "Factor regressions against statsmodels", regression_vs_statsmodels)
    add("Statistics", "Autocorrelations against statsmodels", acf_vs_statsmodels)
    add("Statistics", "Maximum-Sharpe mix weight", tangency_vs_grid)
    add("Data", "Pence/pound flips are caught, clean series kept", unit_flips)
    add("Data", "Momentum signal has no look-ahead", no_look_ahead)
    add("Data", "Exeter market reproduces the published table", exeter_market_reproduces_paper)
    add("Data", "AQR converted to sterling", sterling_conversion)
    add("Data", "Two sources agree on momentum", sources_agree_on_momentum)
    add("Data", "Exeter's factors are their portfolios", exeter_factors_rebuild)
    add("Data", "Stock returns are serially clean", stock_returns_clean)
    add("Data", "Unit flips that reverse are caught", unit_flip_pairs)
    add("Momentum", "Jegadeesh-Titman portfolios against a brute-force loop", jt_vs_brute_force)
    add("Momentum", "Residual momentum against statsmodels", residual_vs_statsmodels)
    add("Momentum", "Signals use only the past", signals_no_look_ahead)
    add("Momentum", "Event time agrees with the K = 1 strategy", event_time_identity)
    add("Industry", "Industry returns are their members' mean", industry_returns_brute)
    add("Industry", "Industry-neutral signals sum to zero", neutral_sums_to_zero)
    add("Industry", "Fama-MacBeth slopes against OLS", fama_macbeth_vs_ols)
    add("Industry", "Placebo groups keep their sizes", placebo_keeps_sizes)
    add("Trend", "Gilt returns against explicit cash flows", gilt_against_cash_flows)
    add("Trend", "Volatility scaling equalises risk", vol_target_hit)
    add("Trend", "A planted trend is found, noise is not", planted_trend_found)
    add("Trend", "Pooled regression against statsmodels", pooled_vs_statsmodels)
    return pd.DataFrame([c.__dict__ for c in checks])


def to_markdown(results: pd.DataFrame) -> str:
    results = results.assign(**{c: results[c].astype(str).str.replace("|", "/") for c in ("reference", "result", "error")})
    lines = ["| Area | Check | Reference | Result | Error | Status |", "|---|---|---|---|---|---|"]
    for row in results.itertuples():
        lines.append(f"| {row.area} | {row.check} | {row.reference} | {row.result} | {row.error} | {row.status} |")
    return "\n".join(lines)
