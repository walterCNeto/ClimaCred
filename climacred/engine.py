"""Motor de cálculo: aplicação da ΔPD do CLIMACRED ao contrato, perda esperada e capital ASRF."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import ASRF_CONF, PD_CAP, PD_FLOOR, YEARS, cnae_to_sector, sector_id


def asrf_k(pd_, lgd, m, floor: float = PD_FLOOR, scale: float = 1.0):
    """Fator K da fórmula ASRF de Basileia (CRE31, corporativo, sem ajuste de porte)."""
    p = np.clip(np.asarray(pd_, dtype=float), floor, PD_CAP)
    e = (1 - np.exp(-50 * p)) / (1 - np.exp(-50))
    r = 0.12 * e + 0.24 * (1 - e)
    b = (0.11852 - 0.05478 * np.log(p)) ** 2
    k = (lgd * norm.cdf((norm.ppf(p) + np.sqrt(r) * norm.ppf(ASRF_CONF)) / np.sqrt(1 - r)) - p * lgd) \
        * (1 + (m - 2.5) * b) / (1 - 1.5 * b)
    return scale * np.maximum(k, 0.0)


def annualize(pd_, horizon: float):
    """PD acumulada em `horizon` anos → PD de 12 meses, com intensidade de default constante:
    PD₁ = 1 − (1 − PD_T)^(1/T). Com horizon ≤ 1 devolve a própria PD."""
    p = np.asarray(pd_, dtype=float)
    if horizon is None or horizon <= 1:
        return p
    return 1 - (1 - np.clip(p, 0, PD_CAP)) ** (1.0 / horizon)


def stress_pd(pd_base, dpd_pp, ref_pd, mode: str, floor: float = PD_FLOOR, horizon: float = 1.0):
    """PD estressada.

    mode='add': soma direta da ΔPD (p.p.), como publicada pelo NGFS.
    mode='dz' : Δz = Φ⁻¹(PD_ref + ΔPD) − Φ⁻¹(PD_ref); PD_s = Φ(Φ⁻¹(PD) + Δz).
                Com horizon = T > 1, PD_ref e PD_ref + ΔPD são antes convertidas para 12 meses por
                intensidade constante (annualize), e o Δz é medido na escala anual.
    Contratos sem ΔPD (NaN) mantêm a PD de base.
    """
    pdb = np.asarray(pd_base, dtype=float)
    d = np.asarray(dpd_pp, dtype=float) / 100.0
    has = ~np.isnan(d)
    d0 = np.where(has, d, 0.0)
    if mode == "add":
        ps = np.clip(pdb + d0, floor, PD_CAP)
    else:
        r = np.clip(np.asarray(ref_pd, dtype=float), floor, 0.9)
        r1 = np.clip(annualize(r, horizon), 1e-6, PD_CAP)
        s1 = np.clip(annualize(np.clip(r + d0, 1e-6, PD_CAP), horizon), 1e-6, PD_CAP)
        dz = norm.ppf(s1) - norm.ppf(r1)
        ps = np.clip(norm.cdf(norm.ppf(pdb) + dz), floor, PD_CAP)
    return np.where(has, ps, pdb)


@dataclass
class Params:
    mode: str = "dz"            # 'dz' ou 'add'
    year: str | int = "pico"    # 'pico' ou um ano de YEARS
    ref: str = "ngfs"           # 'ngfs' (baseline_pd do CLIMACRED), 'cart' (média da carteira por setor) ou 'fix'
    ref_fix: float = 0.0262     # PD de referência única (decimal)
    pr: float = 1800.0          # Patrimônio de Referência (R$ mi)
    fallback_country: str = "Brasil"
    pd_floor: float = PD_FLOOR  # piso de PD do IRB (Basileia II: 0,03%; Basileia III: 0,05%)
    irb_scale: float = 1.0      # fator de escala sobre K (Basileia II previa 1,06)
    horizon: float = 1.0        # horizonte (anos) da baseline_pd/ΔPD do CLIMACRED; > 1 anualiza antes do Δz


def defaulted_mask(c: pd.DataFrame) -> np.ndarray:
    """Contratos em estágio 3 (Res. CMN 4.966) ou com PD ≥ 100%: já inadimplidos, não recebem choque de PD."""
    st = pd.to_numeric(c["estagio"], errors="coerce") if "estagio" in c else pd.Series(np.nan, index=c.index)
    return ((st == 3) | (pd.to_numeric(c["pd_12m"], errors="coerce") >= 1)).to_numpy()


def capital_k(ps, c: pd.DataFrame, p: "Params"):
    """Capital ASRF por contrato (R$): fórmula IRB para adimplentes; para inadimplidos (CRE31.3)
    K·EAD = max(0, LGD·EAD − EL_best), com EL_best = provisão (ou LGD·EAD se não houver provisão)."""
    k = asrf_k(ps, c["lgd"], c["m"], p.pd_floor, p.irb_scale) * c["ead"].to_numpy(float)
    dm = c["default"].to_numpy(bool)
    return np.where(dm, c["k_def"].to_numpy(float), k)


def expected_loss(ps, c: pd.DataFrame):
    pe = np.asarray(ps, dtype=float) * c["lgd"].to_numpy(float) * c["ead"].to_numpy(float)
    return np.where(c["default"].to_numpy(bool), c["el_def"].to_numpy(float), pe)


def prepare_portfolio(df: pd.DataFrame, p: "Params | None" = None) -> pd.DataFrame:
    p = p or Params()
    c = df.copy()
    sec_override = c["setor_ngfs"].map(sector_id) if "setor_ngfs" in c else pd.Series(None, index=c.index)
    c["sec"] = sec_override.where(sec_override.notna(), c["cnae"].map(cnae_to_sector))
    c["default"] = defaulted_mask(c)
    c["estagio"] = pd.to_numeric(c["estagio"], errors="coerce").fillna(1).astype(int) if "estagio" in c else 1
    c.loc[c["default"], "estagio"] = 3
    c["pdb"] = np.where(c["default"], 1.0, np.maximum(c["pd_12m"].astype(float), p.pd_floor))
    c["m"] = np.clip(c["prazo_anos"].astype(float), 1, 5)
    lgde = (c["lgd"] * c["ead"]).astype(float)
    prov = pd.to_numeric(c["provisao"], errors="coerce").fillna(0) if "provisao" in c else pd.Series(0.0, index=c.index)
    c["el_def"] = np.where(prov > 0, np.minimum(prov, lgde), lgde)
    c["k_def"] = np.maximum(0.0, lgde - c["el_def"])
    c["capb"] = capital_k(c["pdb"], c, p)
    c["peb"] = expected_loss(c["pdb"], c)
    return c


def reference_pd(c: pd.DataFrame, p: Params, base: pd.DataFrame, scen: str) -> tuple[np.ndarray, str]:
    """PD de referência por contrato e ano (matriz n × anos) e o critério usado.

    'ngfs' usa a baseline_pd do CLIMACRED do país do contrato (ou do país padrão); contratos sem série
    recaem na média da carteira por setor.
    """
    n = len(c)
    if p.ref == "fix":
        return np.full((n, len(YEARS)), p.ref_fix), "fix"
    w = c[~c["default"]].dropna(subset=["sec"]).assign(x=lambda d: d.pdb * d.ead).groupby("sec")[["x", "ead"]].sum()
    cart = c["sec"].map(w["x"] / w["ead"]).fillna(p.ref_fix).to_numpy(float)
    out = np.repeat(cart[:, None], len(YEARS), axis=1)
    if p.ref != "ngfs" or base is None or base.empty:
        return out, "cart"
    b = base[base.cenario == scen].pivot_table(index="pais", columns="ano", values="baseline_pd_pp").reindex(columns=YEARS)
    if b.empty:
        return out, "cart"
    pais = c["pais"].where(c["pais"].isin(b.index), p.fallback_country)
    has = pais.isin(b.index).to_numpy()
    if has.any():
        out[has] = b.loc[pais[has]].to_numpy(float) / 100.0
    return out, ("ngfs" if has.all() else "ngfs+cart" if has.any() else "cart")


def dpd_matrix(c: pd.DataFrame, dpd: pd.DataFrame, scen: str, fallback: str) -> np.ndarray:
    """Matriz contratos × anos de ΔPD (p.p.); NaN quando não há série para o setor."""
    sub = dpd[dpd.cenario == scen]
    piv = sub.pivot_table(index=["pais", "setor"], columns="ano", values="delta_pd_pp", aggfunc="mean")
    piv = piv.reindex(columns=YEARS)
    countries = set(piv.index.get_level_values(0)) if len(piv) else set()
    pais = c["pais"].where(c["pais"].isin(countries), fallback)
    keys = list(zip(pais, c["sec"]))
    out = np.full((len(c), len(YEARS)), np.nan)
    lookup = {k: v for k, v in zip(piv.index, piv.values)}
    for i, k in enumerate(keys):
        if k in lookup:
            out[i] = lookup[k]
    return out


def run(portfolio: pd.DataFrame, data: dict, p: Params) -> dict:
    """data: saída de climacred.io.load_dpd (dpd, base, scenarios)."""
    dpd, scenarios, basedf = data["dpd"], data["scenarios"], data.get("base")
    c = prepare_portfolio(portfolio, p)
    ead, lgd, m, pdb = (c[k].to_numpy(float) for k in ("ead", "lgd", "m", "pdb"))
    prov = c["provisao"].fillna(0).to_numpy(float)
    dm = c["default"].to_numpy(bool)
    base = {"ead": ead.sum(), "pe": c.peb.sum(), "cap": c.capb.sum(),
            "pdw": (pdb * ead)[~dm].sum() / ead[~dm].sum(), "ead_def": ead[dm].sum(), "n_def": int(dm.sum()),
            "pe_def": c.el_def[dm].sum(), "cap_def": c.k_def[dm].sum(), "exc": np.maximum(0, c.peb - prov).sum()}
    yearly, results, skipped = [], [], []
    for sc in scenarios:
        D = dpd_matrix(c, dpd, sc["id"], p.fallback_country)
        D[c["default"].to_numpy(bool)] = np.nan   # estágio 3: sem choque de PD
        if np.isnan(D).all():
            skipped.append(sc)
            continue
        ref, ref_used = reference_pd(c, p, basedf, sc["id"])
        rows = {}
        for mode in ("add", "dz"):
            for yi, y in enumerate(YEARS):
                ps = stress_pd(pdb, D[:, yi], ref[:, yi], mode, p.pd_floor, p.horizon)
                pe = expected_loss(ps, c)
                cap = capital_k(ps, c, p)
                r = {"cenario": sc["id"], "nome": sc["nome"], "modo": mode, "ano": y,
                     "pd_media": (ps * ead)[~dm].sum() / ead[~dm].sum(), "pe": pe.sum(), "cap": cap.sum(),
                     "exc": np.maximum(0, pe - prov).sum(), "cobertura": ead[~np.isnan(D[:, yi])].sum() / base["ead"]}
                r["dpe"], r["dcap"] = r["pe"] - base["pe"], r["cap"] - base["cap"]
                r["dtot"] = r["dpe"] + r["dcap"]
                rows[(mode, yi)] = r
                yearly.append(r)
        cur = [rows[(p.mode, i)] for i in range(len(YEARS))]
        yi = int(np.argmax([r["dtot"] for r in cur])) if p.year == "pico" else YEARS.index(int(p.year))
        other = "add" if p.mode == "dz" else "dz"
        ps = stress_pd(pdb, D[:, yi], ref[:, yi], p.mode, p.pd_floor, p.horizon)
        per = pd.DataFrame({
            "cenario": sc["id"], "ano": YEARS[yi], "id_contrato": c["id_contrato"], "cliente": c["cliente"],
            "setor": c["sec"], "rating": c.get("rating", ""), "estagio": c["estagio"].to_numpy(), "ead": ead, "lgd": lgd,
            "pais": c["pais"].to_numpy(), "m": m, "delta_pd_pp": D[:, yi], "pd_ref": ref[:, yi], "pd_base": pdb, "pd_estressada": ps,
            "delta_pe": expected_loss(ps, c) - c["peb"].to_numpy(), "delta_capital": capital_k(ps, c, p) - c["capb"].to_numpy(),
        })
        results.append({"sc": sc, "yi": yi, "ref_used": ref_used, "ref_mean": float(np.average(ref[:, yi], weights=ead)), "ev": rows[(p.mode, yi)], "other": rows[(other, yi)], "per": per})
    return {"params": p, "base": base, "portfolio": c, "results": results, "yearly": pd.DataFrame(yearly),
            "skipped": skipped}
