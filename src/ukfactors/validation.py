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

from . import stats, survivorship
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

    add("Statistics", "Newey-West t against statsmodels", nw_vs_statsmodels)
    add("Statistics", "Sharpe ratio standard error (Lo 2002)", sharpe_se_monte_carlo)
    add("Statistics", "Stationary bootstrap coverage", bootstrap_coverage)
    add("Statistics", "Maximum drawdown", drawdown_brute_force)
    add("Data", "Pence/pound flips are caught, clean series kept", unit_flips)
    add("Data", "Momentum signal has no look-ahead", no_look_ahead)
    add("Data", "Exeter market reproduces the published table", exeter_market_reproduces_paper)
    add("Data", "AQR converted to sterling", sterling_conversion)
    add("Data", "Two sources agree on momentum", sources_agree_on_momentum)
    return pd.DataFrame([c.__dict__ for c in checks])


def to_markdown(results: pd.DataFrame) -> str:
    results = results.assign(**{c: results[c].astype(str).str.replace("|", "/") for c in ("reference", "result", "error")})
    lines = ["| Area | Check | Reference | Result | Error | Status |", "|---|---|---|---|---|---|"]
    for row in results.itertuples():
        lines.append(f"| {row.area} | {row.check} | {row.reference} | {row.result} | {row.error} | {row.status} |")
    return "\n".join(lines)
