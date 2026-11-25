import numpy as np
import pandas as pd
import pytest

from climacred.config import cnae_to_sector, sector_id
from climacred.engine import Params, asrf_k, run, stress_pd
from climacred.io import load_dpd, load_portfolio


def test_dz_equals_add_at_reference_pd():
    ps_add = stress_pd([0.0262], [25.77], [0.0262], "add")
    ps_dz = stress_pd([0.0262], [25.77], [0.0262], "dz")
    assert ps_add[0] == pytest.approx(0.2839, abs=1e-9)
    assert ps_dz[0] == pytest.approx(0.2839, abs=1e-9)


def test_dz_preserves_order_and_is_milder_for_good_ratings():
    ps = stress_pd([0.0015, 0.005, 0.08], [25.77] * 3, [0.0262] * 3, "dz")
    assert ps[0] == pytest.approx(0.054888, abs=1e-5)
    assert np.all(np.diff(ps) > 0)


def test_missing_dpd_keeps_base_pd():
    assert stress_pd([0.01], [np.nan], [0.02], "dz")[0] == 0.01


def test_asrf_known_value():
    # PD 1%, LGD 45%, M 2,5 -> RW ≈ 92,32% (tabela ilustrativa do BCBS), K = RW/12,5
    assert asrf_k(0.01, 0.45, 2.5) == pytest.approx(0.9232 / 12.5, abs=5e-5)


def test_mapping():
    assert cnae_to_sector("01") == "agri" and cnae_to_sector("35") == "power" and cnae_to_sector("47") == "mserv"
    assert sector_id("Probability of Default|Non-ferrous metals".split("|")[-1]) == "nonferrous"
    assert sector_id("Coal fired") == "power"


def test_example_run_matches_web_app():
    cart, bad = load_portfolio()
    dpd, sc = load_dpd()
    out = run(cart, dpd, sc, Params())
    assert len(cart) == 160 and not bad
    w = max(out["results"], key=lambda r: r["ev"]["dtot"])
    assert w["sc"]["id"] == "DAPS_AS"
    assert w["ev"]["dtot"] / 1800 == pytest.approx(0.57125, abs=5e-4)


def test_iiasa_wide_format(tmp_path):
    f = tmp_path / "iiasa.csv"
    f.write_text("Model,Scenario,Region,Variable,Unit,2024,2025,2026,2027,2028,2029,2030\n"
                 "GEM-E3,Highway to Paris,Brazil,Probability of Default|Agriculture,pp,0,0.1,0.2,0.3,0.4,0.5,0.6\n"
                 "GEM-E3,Baseline,Brazil,Probability of Default|Agriculture,pp,0,0,0,0,0,0,0\n", encoding="utf-8")
    dpd, sc = load_dpd(f.open("rb"))
    assert [s["id"] for s in sc] == ["Highway to Paris"]
    assert set(dpd.pais) == {"Brasil"} and dpd.query("ano == 2030").delta_pd_pp.iloc[0] == 0.6
