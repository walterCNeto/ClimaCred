"""CreditRisk+ (Credit Suisse First Boston, 1997) com fatores setoriais gama e recursão de Panjer.

CEA = PE + PI, em que PE é a perda esperada e PI a perda inesperada no nível de confiança escolhido
(PI = quantil da perda − PE). O mesmo modelo é calculado com as PDs de base e com as PDs estressadas.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CRParams:
    conf: float = 0.999          # nível de confiança do quantil
    vol_ratio: float = 1.0       # σ_k / μ_k: volatilidade relativa da taxa de inadimplência de cada setor
    w0: float = 0.0              # peso idiossincrático (parcela do risco de cada contrato não ligada a fator setorial)
    sectors: str = "climacred"   # 'climacred' (um fator por setor) ou 'single' (fator sistêmico único)
    bands_max: int = 200         # nº de bandas para a maior exposição (define a unidade L0)
    stress_vol: float = 1.0      # multiplicador da volatilidade relativa nos cenários de estresse
    max_grid: int = 60000        # teto do tamanho da grade de perdas (desempenho)


def _panjer_nb(f: np.ndarray, alpha: float, p: float, n: int) -> np.ndarray:
    """Distribuição composta binomial negativa por Panjer (usada nos testes como referência). f[0] = 0."""
    g = np.zeros(n)
    g[0] = (1 - p) ** alpha
    a, b = p, (alpha - 1) * p
    nz = np.nonzero(f)[0]
    fj = f[nz]
    for k in range(1, n):
        j = nz[nz <= k]
        if j.size == 0:
            continue
        g[k] = np.sum((a + b * j / k) * fj[: j.size] * g[k - j])
    return g


def _panjer_poisson(f: np.ndarray, lam: float, n: int) -> np.ndarray:
    g = np.zeros(n)
    g[0] = np.exp(-lam)
    nz = np.nonzero(f)[0]
    fj = f[nz]
    for k in range(1, n):
        j = nz[nz <= k]
        if j.size == 0:
            continue
        g[k] = lam / k * np.sum(j * fj[: j.size] * g[k - j])
    return g


def loss_unit(exposure_loss: np.ndarray, cp: CRParams) -> float:
    return float(np.max(exposure_loss)) / cp.bands_max if len(exposure_loss) else 1.0


def crplus(pd_: np.ndarray, exposure_loss: np.ndarray, sector: np.ndarray, cp: CRParams, L0: float,
           vol_mult: float = 1.0) -> dict:
    """Distribuição de perdas do CreditRisk+.

    pd_: PD de cada contrato; exposure_loss: LGD × EAD (R$ mi); sector: rótulo do fator de cada contrato.
    Retorna PE, quantil (CEA), PI e a distribuição discretizada.
    """
    pd_ = np.asarray(pd_, float)
    E = np.asarray(exposure_loss, float)
    nu = np.maximum(1, np.rint(E / L0)).astype(int)
    sec = np.where(pd.isna(sector), "Sem setor", sector) if cp.sectors == "climacred" else np.full(len(pd_), "Sistêmico")
    rel = cp.vol_ratio * vol_mult
    # média e desvio da perda (aproximação analítica) para dimensionar a grade
    el_b = np.sum(pd_ * nu)
    var_b = np.sum(pd_ * nu ** 2)
    for s in np.unique(sec):
        m = sec == s
        var_b += (rel * (1 - cp.w0) * np.sum(pd_[m] * nu[m])) ** 2
    n = int(min(np.sum(nu) + 1, np.ceil(el_b + 40 * np.sqrt(var_b) + nu.max() + 10), cp.max_grid))
    # PGF avaliada na circunferência unitária via FFT (equivalente à recursão de Panjer, muito mais rápida)
    M = 1 << int(np.ceil(np.log2(max(2 * n, 2 * (nu.max() + 1)))))
    logG = np.zeros(M // 2 + 1, dtype=complex)
    rows = []
    for s in np.unique(sec):
        m = sec == s
        mu = np.sum((1 - cp.w0) * pd_[m])
        if mu <= 0:
            continue
        f = np.bincount(nu[m], weights=(1 - cp.w0) * pd_[m]) / mu
        sig = rel * mu
        alpha, beta = (mu / sig) ** 2, sig ** 2 / mu
        p = beta / (1 + beta)
        F = np.fft.rfft(f, M)
        logG += alpha * (np.log(1 - p) - np.log(1 - p * F))
        rows.append({"fator": s, "contratos": int(m.sum()), "mu": mu, "sigma": sig, "alpha": alpha, "beta": beta,
                     "pe": float(np.sum(pd_[m] * E[m]))})
    if cp.w0 > 0:
        lam = np.sum(cp.w0 * pd_)
        f0 = np.bincount(nu, weights=cp.w0 * pd_) / lam
        logG += lam * (np.fft.rfft(f0, M) - 1)
    dist = np.clip(np.fft.irfft(np.exp(logG), M)[:n], 0, None)
    cdf = np.cumsum(dist)
    k = int(np.searchsorted(cdf, cp.conf))
    pe_band = float(np.sum(np.arange(n) * dist) * L0)
    q = k * L0
    return {"pe": float(np.sum(pd_ * E)), "pe_banda": pe_band, "quantil": q, "pi": q - pe_band, "cea": float(np.sum(pd_ * E)) + q - pe_band,
            "massa": float(cdf[-1]), "dist": dist, "L0": L0, "n": n, "fatores": pd.DataFrame(rows), "rel": rel}


def run_crplus(out: dict, cp: CRParams) -> dict:
    """CreditRisk+ para a carteira de base e para cada cenário (no ano de avaliação)."""
    c = out["portfolio"]
    ok = ~c["default"].to_numpy(bool) if "default" in c else np.ones(len(c), bool)
    E = (c["lgd"] * c["ead"]).to_numpy(float)
    D = float(E[~ok].sum())                     # estágio 3: perda já incorrida, determinística
    sec = c["sec"].to_numpy(object)[ok]
    L0 = loss_unit(E[ok], cp)
    base = _add_fixed(crplus(c["pdb"].to_numpy(float)[ok], E[ok], sec, cp, L0), D, L0)
    res = {"params": cp, "L0": L0, "base": base, "cen": {}, "perda_def": D, "n_def": int((~ok).sum())}
    for r in out["results"]:
        ps = r["per"]["pd_estressada"].to_numpy(float)[ok]
        x = _add_fixed(crplus(ps, E[ok], sec, cp, L0, vol_mult=cp.stress_vol), D, L0)
        pa = r["per"]["pd_acrescimo"].to_numpy(float)[ok] if "pd_acrescimo" in r["per"] else ps
        if np.allclose(pa, ps):
            x["cea_acr"] = x["cea"]
        else:  # acréscimo: mesmo cenário com ΔPD negativas zeradas; benefício = líquido − acréscimo
            x["cea_acr"] = _add_fixed(crplus(pa, E[ok], sec, cp, L0, vol_mult=cp.stress_vol), D, L0)["cea"]
        res["cen"][r["sc"]["id"]] = x
    return res


def _add_fixed(d: dict, D: float, L0: float) -> dict:
    """Soma à distribuição uma perda determinística D (exposições em default): desloca a
    distribuição em round(D/L0) bandas; PE e quantil aumentam em D e PI não se altera."""
    if D <= 0:
        return d
    k = int(round(D / L0))
    d = dict(d)
    d["dist"] = np.concatenate([np.zeros(k), d["dist"]])
    d["n"] = len(d["dist"])
    d["pe"] += D
    d["pe_banda"] += k * L0
    d["quantil"] += k * L0
    d["cea"] = d["pe"] + d["pi"]
    return d
