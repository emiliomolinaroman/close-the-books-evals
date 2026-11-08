from __future__ import annotations

import math

import pytest

from ctb_evals import stats


def test_mean_se() -> None:
    xs = [1, 0, 1, 1, 0, 1, 1, 0]
    p = 5 / 8
    assert stats.mean(xs) == p
    assert stats.mean_se(xs) == pytest.approx(math.sqrt(p * (1 - p) * 8 / 7 / 8))


def test_clustered_se_reduces_to_clt_for_singletons() -> None:
    xs = [1, 0, 1, 1, 0, 0, 1]
    assert stats.clustered_se(xs, list(range(len(xs)))) == pytest.approx(stats.mean_se(xs))


def test_clustered_se_grows_when_clusters_are_correlated() -> None:
    xs = [1, 1, 1, 1, 0, 0, 0, 0]
    assert stats.clustered_se(xs, ["a"] * 4 + ["b"] * 4) > stats.mean_se(xs)


def test_paired_diff_is_tighter_than_unpaired_when_correlated() -> None:
    a = [0, 0, 1, 1, 1, 0, 1, 1, 0, 1]
    b = [0, 1, 1, 1, 1, 0, 1, 1, 1, 1]
    p = stats.paired_diff(a, b)
    assert p["diff"] == pytest.approx(0.2)
    assert p["se"] < math.sqrt(stats.mean_se(a) ** 2 + stats.mean_se(b) ** 2)
    assert (p["b_better"], p["a_better"]) == (2, 0)
    with pytest.raises(ValueError):
        stats.paired_diff([1], [1, 0])


def test_bootstrap_is_deterministic_and_brackets_the_mean() -> None:
    a = [0, 1] * 20
    b = [1, 1] * 20
    lo, hi = stats.bootstrap_ci(a, b, reps=2000)
    assert stats.bootstrap_ci(a, b, reps=2000) == (lo, hi)
    assert lo <= 0.5 <= hi


def test_kappa() -> None:
    assert stats.cohens_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert stats.cohens_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == pytest.approx(0.0)


def test_power() -> None:
    assert stats.mde(0.4, 100) == pytest.approx((1.959964 + 0.841621) * 0.04, rel=1e-4)
    assert stats.questions_needed(0.1, 0.4) == math.ceil((2.801585 * 4) ** 2)


def test_t_quantiles() -> None:
    assert stats.t975(4) == 2.776 and stats.t975(5) == 2.571
    assert stats.t975(22) == stats.t975(20)  # between table rows: the smaller df, which is wider
    assert stats.t975(200) == 1.96
    assert math.isnan(stats.t975(0))


def test_pooled_team_contrast() -> None:
    c = stats.pooled_team_contrast({"x": [0.8, 0.9], "y": [0.7, 0.9, 0.8]}, "x", "y")
    assert c["df"] == 3
    assert c["diff"] == pytest.approx(-0.05)
    assert c["pooled_sd"] == pytest.approx(math.sqrt((0.005 + 2 * 0.01) / 3))
    assert c["se"] == pytest.approx(c["pooled_sd"] * math.sqrt(1 / 2 + 1 / 3))
    assert c["ci95_high"] - c["diff"] == pytest.approx(3.182 * c["se"])
    one_each = stats.pooled_team_contrast({"x": [0.8], "y": [0.7]}, "x", "y")
    assert math.isnan(one_each["ci95_low"])  # no team-to-team variance to pool
