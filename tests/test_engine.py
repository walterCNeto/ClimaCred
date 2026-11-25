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
    assert cnae_to_sector("01") == "Agriculture" and cnae_to_sector("35") == "Power Supply"
    assert cnae_to_sector("47") == "Market Services" and cnae_to_sector("1931-1/00") == "Biofuels"
    assert cnae_to_sector("2441") == "Non-ferrous metals" and cnae_to_sector("24") == "Ferrous metals"
    assert sector_id("pd_adjustment|Non-ferrous metals".split("|")[-1]) == "Non-ferrous metals"
    assert sector_id("coal fired") == "Coal fired" and sector_id("agri") == "Agriculture"


def test_example_run_illustrative():
    cart, bad = load_portfolio()
    data = load_dpd()
    out = run(cart, data, Params(ref="cart"))
    assert len(cart) == 160 and not bad
    w = max(out["results"], key=lambda r: r["ev"]["dtot"])
    assert w["sc"]["id"] == "DAPS_SAM" and w["ref_used"] == "cart"
    # sem baseline_pd na série ilustrativa, o modo 'ngfs' recai na média da carteira
    out2 = run(cart, data, Params(ref="ngfs"))
    assert out2["results"][0]["ref_used"] == "cart"


def test_climacred_format_with_baseline(tmp_path):
    f = tmp_path / "CLIMACRED_teste.csv"
    f.write_text("Model,Scenario,Region,Variable,Unit,2022,2023,2024,2025,2026,2027,2028,2029,2030\n"
                 "CLIMACRED,DAPS_SAM,Brazil - BRA,pd_adjustment|Agriculture,abs. change,0,0,0,0,26.641,6.66,1.665,0.416,0.104\n"
                 "CLIMACRED,DAPS_SAM,Brazil - BRA,baseline_pd|Agriculture,value/level,32.7,40.2,45.373,43.379,41.44,39.701,38.178,36.635,35.191\n",
                 encoding="utf-8")
    data = load_dpd(f)
    assert [s["id"] for s in data["scenarios"]] == ["DAPS_SAM"]
    assert set(data["dpd"].pais) == {"Brasil"} and set(data["base"].pais) == {"Brasil"}
    cart = pd.DataFrame({"id_contrato": ["A", "B"], "cliente": ["x", "y"], "cnae": ["01", "01"], "setor_ngfs": ["", ""],
                         "pais": ["Brasil"] * 2, "uf": ["MT"] * 2, "rating": ["A", "B"], "pd_12m": [0.0262, 0.0015],
                         "lgd": [0.45] * 2, "ead": [100.0] * 2, "prazo_anos": [2.5] * 2, "provisao": [0.0] * 2})
    out = run(cart, data, Params(ref="ngfs", year=2026))
    per = out["results"][0]["per"].set_index("id_contrato")
    # Δz = Φ⁻¹(41,44% + 26,641%) − Φ⁻¹(41,44%) ≈ 0,686 -> PD 2,62% vai a ≈ 10,5%
    assert per.loc["A", "pd_estressada"] == pytest.approx(0.105, abs=2e-3)
    assert out["results"][0]["ref_used"] == "ngfs"


def test_article_pdf():
    from climacred.article import build_article
    cart, _ = load_portfolio()
    data = load_dpd()
    from climacred.creditrisk import CRParams, run_crplus
    out = run(cart, data, Params())
    out["crp"] = run_crplus(out, CRParams())
    pdf = build_article(out, data, "ex", "Autor Teste")
    assert pdf[:4] == b"%PDF" and len(pdf) > 50_000


def test_creditrisk_fft_matches_panjer():
    from climacred.creditrisk import CRParams, _panjer_nb, crplus
    rng = np.random.default_rng(1)
    pdv, E = rng.uniform(0.005, 0.05, 40), rng.uniform(1, 20, 40)
    cp = CRParams(sectors="single", vol_ratio=0.8, bands_max=20)
    L0 = E.max() / 20
    r = crplus(pdv, E, np.array(["a"] * 40), cp, L0)
    nu = np.maximum(1, np.rint(E / L0)).astype(int)
    mu, sig = pdv.sum(), 0.8 * pdv.sum()
    f = np.pad(np.bincount(nu, weights=pdv) / mu, (0, r["n"]))[: r["n"]]
    beta = sig ** 2 / mu
    g = _panjer_nb(f, (mu / sig) ** 2, beta / (1 + beta), r["n"])
    assert np.abs(g - r["dist"]).max() < 1e-12
    assert r["cea"] == pytest.approx(r["pe"] + r["pi"])


def test_creditrisk_stress_increases_cea():
    from climacred.creditrisk import CRParams, run_crplus
    cart, _ = load_portfolio()
    data = load_dpd()
    out = run(cart, data, Params())
    crp = run_crplus(out, CRParams())
    assert all(v["cea"] >= crp["base"]["cea"] - 1e-9 for v in crp["cen"].values())


def test_capital_compare_and_model_choice():
    from climacred.creditrisk import CRParams, run_crplus
    from climacred.report import capital_compare, model_delta, worst_model
    cart, _ = load_portfolio()
    data = load_dpd()
    out = run(cart, data, Params(irb_scale=1.06))
    out["crp"] = run_crplus(out, CRParams())
    cc = capital_compare(out)
    assert {"CEA ASRF (PE + K·EAD)", "CEA CreditRisk+"} <= set(cc.columns)
    base = out["base"]
    assert cc.iloc[0]["CEA ASRF (PE + K·EAD)"] == pytest.approx(base["pe"] + base["cap"])
    out["cap_model"] = "crp"
    w = worst_model(out)
    assert model_delta(out, w)["dtot"] == pytest.approx(out["crp"]["cen"][w["sc"]["id"]]["cea"] - out["crp"]["base"]["cea"])


def test_equation_assets_present():
    import json
    import os
    d = os.path.join(os.path.dirname(__file__), "..", "climacred", "assets", "eq")
    man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
    assert len(man) >= 12 and all(os.path.exists(os.path.join(d, f"{k}.png")) for k in man)


def test_horizon_adjustment_shrinks_dz():
    from climacred.engine import annualize, stress_pd
    assert annualize(0.41, 1) == pytest.approx(0.41)
    assert annualize(1 - 0.9 ** 5, 5) == pytest.approx(0.1)
    p1 = stress_pd([0.01], [2.6], [0.41], "dz", horizon=1)[0]
    p5 = stress_pd([0.01], [2.6], [0.41], "dz", horizon=5)[0]
    assert 0.01 < p5 < p1


def test_stage3_not_shocked_and_consistent():
    from climacred.creditrisk import CRParams, run_crplus
    cart, _ = load_portfolio()
    out = run(cart, load_dpd(), Params())
    c = out["portfolio"]
    dm = c["default"].to_numpy(bool)
    assert dm.sum() == 3
    tot = (c.lgd * c.ead)[dm].sum()
    assert (c.peb + c.capb)[dm].sum() == pytest.approx(tot)
    for r in out["results"]:
        per = r["per"]
        assert (per.loc[dm, "delta_pe"].abs().max(), per.loc[dm, "delta_capital"].abs().max()) == (0, 0)
    crp = run_crplus(out, CRParams())
    assert crp["perda_def"] == pytest.approx(tot)


def test_benefits_decomposition_and_toggle():
    from climacred.creditrisk import CRParams, run_crplus
    from climacred.report import model_delta
    cart, _ = load_portfolio()
    data = load_dpd()
    on = run(cart, data, Params(year=2030))
    off = run(cart, data, Params(year=2030, benefits=False))
    on["crp"], off["crp"] = run_crplus(on, CRParams()), run_crplus(off, CRParams())
    for a, b in zip(on["results"], off["results"]):
        for m in ("asrf", "crp"):
            da, db = model_delta(on, a, m), model_delta(off, b, m)
            assert da["acr"] + da["ben"] == pytest.approx(da["dtot"])
            assert da["ben"] <= 1e-9 and db["ben"] == pytest.approx(0, abs=1e-6)
            assert db["dtot"] == pytest.approx(da["acr"], rel=1e-6, abs=1e-6)
        assert (b["per"]["pd_estressada"] >= b["per"]["pd_base"] - 1e-12).all()
