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

from . import analysis, stats, survivorship
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
    return pd.DataFrame([c.__dict__ for c in checks])


def to_markdown(results: pd.DataFrame) -> str:
    results = results.assign(**{c: results[c].astype(str).str.replace("|", "/") for c in ("reference", "result", "error")})
    lines = ["| Area | Check | Reference | Result | Error | Status |", "|---|---|---|---|---|---|"]
    for row in results.itertuples():
        lines.append(f"| {row.area} | {row.check} | {row.reference} | {row.result} | {row.error} | {row.status} |")
    return "\n".join(lines)
