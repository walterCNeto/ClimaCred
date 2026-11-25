"""Leitura da carteira e da ΔPD (formato largo do IIASA ou formato longo)."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd

from .config import COUNTRY_ALIASES, SCENARIOS, YEARS, sector_id

DATA = Path(__file__).resolve().parent.parent / "data"


def _num(s: pd.Series) -> pd.Series:
    """Converte números com ponto ou vírgula decimal."""
    if s.dtype.kind in "fi":
        return s.astype(float)
    t = s.astype(str).str.strip().str.replace(r"[\s%]", "", regex=True)
    both = t.str.contains(",") & t.str.contains(r"\.")
    t = t.where(~both, t.str.replace(".", "", regex=False))
    return pd.to_numeric(t.str.replace(",", ".", regex=False), errors="coerce")


def read_csv_any(src) -> pd.DataFrame:
    raw = src.read() if hasattr(src, "read") else Path(src).read_bytes()
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    first = text.splitlines()[0] if text else ""
    sep = ";" if first.count(";") > first.count(",") else ","
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def load_portfolio(src=None) -> tuple[pd.DataFrame, list[int]]:
    df = read_csv_any(src or DATA / "carteira_exemplo.csv")
    ren = {"id": "id_contrato", "pd": "pd_12m", "prazo": "prazo_anos", "prov": "provisao"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df and v not in df})
    for col in ("cliente", "setor_ngfs", "uf", "rating"):
        if col not in df:
            df[col] = ""
    if "pais" not in df:
        df["pais"] = "Brasil"
    if "id_contrato" not in df:
        df["id_contrato"] = [f"L{i + 2}" for i in range(len(df))]
    df["cnae"] = df.get("cnae", "").astype(str).str.replace(r"\D", "", regex=True).str[:2].str.zfill(2)
    for col in ("pd_12m", "lgd", "ead", "prazo_anos", "provisao"):
        df[col] = _num(df[col]) if col in df else np.nan
    df["prazo_anos"] = df["prazo_anos"].where(df["prazo_anos"] > 0, 2.5)
    df["provisao"] = df["provisao"].where(df["provisao"] >= 0, 0.0)
    df = df.fillna({"cliente": "", "setor_ngfs": "", "uf": "", "rating": "", "pais": "Brasil"})
    ok = df.pd_12m.between(0, 1, inclusive="left") & df.lgd.between(0, 1) & (df.ead >= 0)
    bad = [int(i) + 2 for i in df.index[~ok]]
    return df[ok].reset_index(drop=True), bad


def load_dpd(src=None) -> tuple[pd.DataFrame, list[dict]]:
    """Retorna ΔPD em formato longo (cenario, pais, setor, ano, delta_pd_pp) e a lista de cenários."""
    if src is None:
        df = read_csv_any(DATA / "dpd_ilustrativa.csv")
        df["delta_pd_pp"] = _num(df["delta_pd_pp"])
        df["ano"] = df["ano"].astype(int)
        return df, [dict(s) for s in SCENARIOS]
    df = read_csv_any(src)
    if "variable" in df:  # formato largo do NGFS Scenario Explorer
        df = df[df["variable"].str.contains("default", case=False, na=False)]
        ycols = [c for c in df.columns if c.strip().isdigit() and int(c) in YEARS]
        long = df.melt(id_vars=["scenario", "region", "variable", "unit"], value_vars=ycols, var_name="ano", value_name="v")
        long["v"] = _num(long["v"])
        pp = long["unit"].fillna("%").str.contains("%|pp", case=False)
        long["delta_pd_pp"] = np.where(pp, long["v"], long["v"] * 100)
        long["setor"] = long["variable"].str.split("|").str[-1]
        long = long.rename(columns={"scenario": "cenario", "region": "pais"})
    else:
        long = df.rename(columns={"scenario": "cenario", "region": "pais", "sector": "setor", "year": "ano"})
        if "pais" not in long:
            long["pais"] = "Brasil"
        long["delta_pd_pp"] = _num(long["delta_pd_pp"])
    long["setor"] = long["setor"].map(sector_id)
    long["pais"] = long["pais"].map(lambda x: COUNTRY_ALIASES.get(str(x).lower(), x))
    long["ano"] = pd.to_numeric(long["ano"], errors="coerce")
    long = long.dropna(subset=["setor", "ano", "delta_pd_pp"])
    long = long[~long["cenario"].str.contains(r"baseline|^base$", case=False, regex=True)]
    long["ano"] = long["ano"].astype(int)
    long = long.groupby(["cenario", "pais", "setor", "ano"], as_index=False)["delta_pd_pp"].mean()
    if long.empty:
        raise ValueError("nenhuma série de ΔPD reconhecida no arquivo")
    scen = []
    for s in long["cenario"].unique():
        tipo = ("Transição ordenada" if "paris" in s.lower() else "Transição abrupta" if "wake" in s.lower()
                else "Físico e transição" if "diverg" in s.lower() else "Físico" if "disaster" in s.lower() else "")
        scen.append({"id": s, "curto": s[:14], "nome": s, "tipo": tipo})
    return long, scen
