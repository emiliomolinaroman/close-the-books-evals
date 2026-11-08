"""Uncertainty for eval scores, following Miller (2024), "Adding Error Bars to Evals".

All functions take plain lists so they can be audited by hand. Conventions:
* ``mean_se``: standard error of a mean of per-question scores (CLT; sample variance with n-1).
* ``clustered_se``: questions grouped into clusters (e.g. criteria within an APEX task) are not
  independent; this adds the within-cluster covariance term (Miller eq. 4).
* ``paired_diff``: two systems scored on the same questions; the SE of the mean difference uses
  the per-question differences (Miller eq. 7), which is much tighter than comparing two
  independent SEs when scores are correlated.
* ``bootstrap_ci``: percentile bootstrap of the mean difference, kept because the article quoted it.
* ``mde``: minimum detectable effect for a paired design at the given power.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Hashable, Mapping, Sequence
from statistics import NormalDist

Z95 = 1.959963984540054


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def variance(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def mean_se(xs: Sequence[float]) -> float:
    return math.sqrt(variance(xs) / len(xs)) if xs else float("nan")


def clustered_se(xs: Sequence[float], clusters: Sequence[Hashable]) -> float:
    """Cluster-robust SE of the mean (Miller 2024, eq. 4)."""
    if len(xs) != len(clusters):
        raise ValueError("xs and clusters must have the same length")
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    base = variance(xs) / n
    groups: dict[Hashable, list[float]] = defaultdict(list)
    for x, c in zip(xs, clusters, strict=True):
        groups[c].append(x - m)
    cross = 0.0
    for devs in groups.values():
        s = sum(devs)
        cross += s * s - sum(d * d for d in devs)  # sum over i != j of d_i d_j
    return math.sqrt(max(0.0, base + cross / (n * n)))


def paired_diff(a: Sequence[float], b: Sequence[float]) -> dict[str, float]:
    """Mean of (b - a) over the same questions, with SE, 95% CI and two-sided p (normal approx.)."""
    if len(a) != len(b) or not a:
        raise ValueError("paired samples must be non-empty and the same length")
    d = [y - x for x, y in zip(a, b, strict=True)]
    md, se = mean(d), mean_se(d)
    p = 2 * (1 - NormalDist().cdf(abs(md) / se)) if se > 0 else (0.0 if md else 1.0)
    p = round(p, 12)  # erf comes from the platform libm; its last bits differ between macOS and Linux
    va, vb = variance(a), variance(b)
    cov = sum((x - mean(a)) * (y - mean(b)) for x, y in zip(a, b, strict=True)) / (len(a) - 1) if len(a) > 1 else 0.0
    corr = cov / math.sqrt(va * vb) if va > 0 and vb > 0 else float("nan")
    return {
        "n": len(d),
        "mean_a": mean(a),
        "mean_b": mean(b),
        "diff": md,
        "se": se,
        "ci95_low": md - Z95 * se,
        "ci95_high": md + Z95 * se,
        "p_two_sided": p,
        "corr": corr,
        "b_better": sum(1 for x in d if x > 0),
        "a_better": sum(1 for x in d if x < 0),
    }


def bootstrap_ci(
    a: Sequence[float], b: Sequence[float], reps: int = 5000, seed: int = 1, alpha: float = 0.05
) -> tuple[float, float]:
    """Percentile bootstrap CI for mean(b - a), resampling questions."""
    rng = random.Random(seed)
    n = len(a)
    diffs = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(b[i] - a[i] for i in idx) / n)
    diffs.sort()
    lo = diffs[int(reps * alpha / 2)]
    hi = diffs[int(reps * (1 - alpha / 2))]
    return lo, hi


def mde(sd_diff: float, n: int, power: float = 0.8, alpha: float = 0.05) -> float:
    """Smallest true mean difference a paired test with n questions detects at the given power."""
    z_a = NormalDist().inv_cdf(1 - alpha / 2)
    z_b = NormalDist().inv_cdf(power)
    return (z_a + z_b) * sd_diff / math.sqrt(n)


def questions_needed(effect: float, sd_diff: float, power: float = 0.8, alpha: float = 0.05) -> int:
    z_a = NormalDist().inv_cdf(1 - alpha / 2)
    z_b = NormalDist().inv_cdf(power)
    return math.ceil(((z_a + z_b) * sd_diff / effect) ** 2)


# Two-sided 95% quantiles of Student's t (standard table values).
_T975 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
    20: 2.086, 25: 2.060, 30: 2.042,
}  # fmt: skip


def t975(df: int) -> float:
    """Two-sided 95% t quantile. Between table rows it takes the smaller df (a wider interval); 1.96 above 30."""
    if df < 1:
        return float("nan")
    if df > 30:
        return 1.96
    return _T975[max(k for k in _T975 if k <= df)]


def pooled_team_contrast(groups: Mapping[str, Sequence[float]], a: str, b: str) -> dict[str, float]:
    """Team means of arm ``b`` minus arm ``a``, treating each team as one draw.

    The team-to-team SD is pooled over every arm in ``groups`` (one run-to-run noise level for the
    study), and the interval uses t with the pooled degrees of freedom. With two teams per arm this is
    the honest uncertainty about "would the next team do better with the scaffold?".
    """
    dof = sum(len(v) - 1 for v in groups.values())
    diff = mean(groups[b]) - mean(groups[a])
    if dof < 1:
        nan = float("nan")
        return {"diff": diff, "pooled_sd": nan, "se": nan, "df": 0, "ci95_low": nan, "ci95_high": nan}
    sd = math.sqrt(sum((len(v) - 1) * variance(v) for v in groups.values()) / dof)
    se = sd * math.sqrt(1 / len(groups[a]) + 1 / len(groups[b]))
    t = t975(dof)
    return {"diff": diff, "pooled_sd": sd, "se": se, "df": dof, "ci95_low": diff - t * se, "ci95_high": diff + t * se}


def cohens_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    """Agreement between two raters beyond chance."""
    if len(a) != len(b) or not a:
        raise ValueError("ratings must be non-empty and the same length")
    n = len(a)
    po = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    cats = set(a) | set(b)
    pe = sum((list(a).count(c) / n) * (list(b).count(c) / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def fmt(m: float, se: float, pct: bool = True) -> str:
    """'84.6% (3.0)' style used in the report: SE in parentheses, same units."""
    if pct:
        return f"{100 * m:.1f}% ({100 * se:.1f})"
    return f"{m:.3f} ({se:.3f})"
