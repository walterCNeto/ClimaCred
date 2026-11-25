"""Motor de cálculo: aplicação da ΔPD do CLIMACRED ao contrato, perda esperada e capital ASRF."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import ASRF_CONF, PD_CAP, PD_FLOOR, YEARS, cnae_to_sector, sector_id


def asrf_k(pd_, lgd, m):
    """Fator K da fórmula ASRF de Basileia (CRE31, corporativo, sem ajuste de porte)."""
    p = np.clip(np.asarray(pd_, dtype=float), PD_FLOOR, PD_CAP)
    e = (1 - np.exp(-50 * p)) / (1 - np.exp(-50))
    r = 0.12 * e + 0.24 * (1 - e)
    b = (0.11852 - 0.05478 * np.log(p)) ** 2
    k = (lgd * norm.cdf((norm.ppf(p) + np.sqrt(r) * norm.ppf(ASRF_CONF)) / np.sqrt(1 - r)) - p * lgd) \
        * (1 + (m - 2.5) * b) / (1 - 1.5 * b)
    return np.maximum(k, 0.0)


def stress_pd(pd_base, dpd_pp, ref_pd, mode: str):
    """PD estressada.

    mode='add': soma direta da ΔPD (p.p.), como publicada pelo NGFS.
    mode='dz' : Δz = Φ⁻¹(PD_ref + ΔPD) − Φ⁻¹(PD_ref); PD_s = Φ(Φ⁻¹(PD) + Δz).
    Contratos sem ΔPD (NaN) mantêm a PD de base.
    """
    pdb = np.asarray(pd_base, dtype=float)
    d = np.asarray(dpd_pp, dtype=float) / 100.0
    has = ~np.isnan(d)
    d0 = np.where(has, d, 0.0)
    if mode == "add":
        ps = np.clip(pdb + d0, PD_FLOOR, PD_CAP)
    else:
        r = np.clip(np.asarray(ref_pd, dtype=float), PD_FLOOR, 0.9)
        dz = norm.ppf(np.clip(r + d0, 1e-6, PD_CAP)) - norm.ppf(r)
        ps = np.clip(norm.cdf(norm.ppf(pdb) + dz), PD_FLOOR, PD_CAP)
    return np.where(has, ps, pdb)


@dataclass
class Params:
    mode: str = "dz"            # 'dz' ou 'add'
    year: str | int = "pico"    # 'pico' ou um ano de YEARS
    ref: str = "cart"           # 'cart' (média da carteira por setor) ou 'fix'
    ref_fix: float = 0.0262     # PD de referência única (decimal)
    pr: float = 1800.0          # Patrimônio de Referência (R$ mi)
    fallback_country: str = "Brasil"


def prepare_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    c = df.copy()
    sec_override = c["setor_ngfs"].map(sector_id) if "setor_ngfs" in c else pd.Series(None, index=c.index)
    c["sec"] = sec_override.where(sec_override.notna(), c["cnae"].map(cnae_to_sector))
    c["pdb"] = np.maximum(c["pd_12m"].astype(float), PD_FLOOR)
    c["m"] = np.clip(c["prazo_anos"].astype(float), 1, 5)
    c["capb"] = asrf_k(c["pdb"], c["lgd"], c["m"]) * c["ead"]
    c["peb"] = c["pdb"] * c["lgd"] * c["ead"]
    return c


def reference_pd(c: pd.DataFrame, p: Params) -> pd.Series:
    if p.ref == "fix":
        return pd.Series(p.ref_fix, index=c.index)
    w = c.dropna(subset=["sec"]).groupby("sec").apply(lambda g: (g.pdb * g.ead).sum() / g.ead.sum())
    return c["sec"].map(w).fillna(p.ref_fix)


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


def run(portfolio: pd.DataFrame, dpd: pd.DataFrame, scenarios: list[dict], p: Params) -> dict:
    c = prepare_portfolio(portfolio)
    ref = reference_pd(c, p).to_numpy()
    ead, lgd, m, pdb = (c[k].to_numpy(float) for k in ("ead", "lgd", "m", "pdb"))
    prov = c["provisao"].fillna(0).to_numpy(float)
    base = {"ead": ead.sum(), "pe": c.peb.sum(), "cap": c.capb.sum(),
            "pdw": (pdb * ead).sum() / ead.sum(), "exc": np.maximum(0, c.peb - prov).sum()}
    yearly, results = [], []
    for sc in scenarios:
        D = dpd_matrix(c, dpd, sc["id"], p.fallback_country)
        rows = {}
        for mode in ("add", "dz"):
            for yi, y in enumerate(YEARS):
                ps = stress_pd(pdb, D[:, yi], ref, mode)
                pe = ps * lgd * ead
                cap = asrf_k(ps, lgd, m) * ead
                r = {"cenario": sc["id"], "nome": sc["nome"], "modo": mode, "ano": y,
                     "pd_media": (ps * ead).sum() / base["ead"], "pe": pe.sum(), "cap": cap.sum(),
                     "exc": np.maximum(0, pe - prov).sum(), "cobertura": ead[~np.isnan(D[:, yi])].sum() / base["ead"]}
                r["dpe"], r["dcap"] = r["pe"] - base["pe"], r["cap"] - base["cap"]
                r["dtot"] = r["dpe"] + r["dcap"]
                rows[(mode, yi)] = r
                yearly.append(r)
        cur = [rows[(p.mode, i)] for i in range(len(YEARS))]
        yi = int(np.argmax([r["dtot"] for r in cur])) if p.year == "pico" else YEARS.index(int(p.year))
        other = "add" if p.mode == "dz" else "dz"
        ps = stress_pd(pdb, D[:, yi], ref, p.mode)
        per = pd.DataFrame({
            "cenario": sc["id"], "ano": YEARS[yi], "id_contrato": c["id_contrato"], "cliente": c["cliente"],
            "setor": c["sec"], "rating": c.get("rating", ""), "ead": ead, "lgd": lgd,
            "delta_pd_pp": D[:, yi], "pd_base": pdb, "pd_estressada": ps,
            "delta_pe": (ps - pdb) * lgd * ead, "delta_capital": asrf_k(ps, lgd, m) * ead - c["capb"].to_numpy(),
        })
        results.append({"sc": sc, "yi": yi, "ev": rows[(p.mode, yi)], "other": rows[(other, yi)], "per": per})
    return {"params": p, "base": base, "portfolio": c, "results": results, "yearly": pd.DataFrame(yearly)}
