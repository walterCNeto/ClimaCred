"""Leitura da carteira e da série do CLIMACRED (xlsx do IIASA, CSV largo do IIASA ou CSV longo)."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd

from .config import SCEN_BY_ID, SCENARIOS, YEARS, normalize_country, sector_id

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NGFS_DIR = DATA / "ngfs"  # arquivos oficiais do IIASA ficam aqui, fora do git (licença)


def _num(s: pd.Series) -> pd.Series:
    """Converte números com ponto ou vírgula decimal."""
    if s.dtype.kind in "fi":
        return s.astype(float)
    t = s.astype(str).str.strip().str.replace(r"[\s%]", "", regex=True)
    both = t.str.contains(",") & t.str.contains(r"\.")
    t = t.where(~both, t.str.replace(".", "", regex=False))
    return pd.to_numeric(t.str.replace(",", ".", regex=False), errors="coerce")


def _read_bytes(src) -> tuple[bytes, str]:
    if hasattr(src, "read"):
        return src.read(), getattr(src, "name", "")
    p = Path(src)
    return p.read_bytes(), p.name


def read_table(src) -> pd.DataFrame:
    raw, name = _read_bytes(src)
    if name.lower().endswith((".xlsx", ".xls")):
        x = pd.ExcelFile(io.BytesIO(raw))
        df = pd.read_excel(x, "data" if "data" in x.sheet_names else x.sheet_names[0])
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    text = raw.decode("utf-8-sig")
    first = text.splitlines()[0] if text else ""
    sep = ";" if first.count(";") > first.count(",") else ","
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def load_portfolio(src=None) -> tuple[pd.DataFrame, list[int]]:
    df = read_table(src or DATA / "carteira_exemplo.csv").astype(object)
    ren = {"id": "id_contrato", "pd": "pd_12m", "prazo": "prazo_anos", "prov": "provisao"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df and v not in df})
    for col in ("cliente", "setor_ngfs", "uf", "rating"):
        if col not in df:
            df[col] = ""
    if "pais" not in df:
        df["pais"] = "Brasil"
    if "id_contrato" not in df:
        df["id_contrato"] = [f"L{i + 2}" for i in range(len(df))]
    df["cnae"] = df.get("cnae", "").astype(str).str.replace(r"\.0$", "", regex=True).str.replace(r"\D", "", regex=True)
    df["cnae"] = df["cnae"].where(df["cnae"].str.len() != 1, df["cnae"].str.zfill(2))
    for col in ("pd_12m", "lgd", "ead", "prazo_anos", "provisao"):
        df[col] = _num(df[col].astype(str)) if col in df else np.nan
    df["prazo_anos"] = df["prazo_anos"].where(df["prazo_anos"] > 0, 2.5)
    df["provisao"] = df["provisao"].where(df["provisao"] >= 0, 0.0)
    for col in ("cliente", "setor_ngfs", "uf", "rating"):
        df[col] = df[col].fillna("").astype(str).replace("nan", "")
    df["pais"] = df["pais"].fillna("Brasil").astype(str)
    ok = df.pd_12m.between(0, 1, inclusive="left") & df.lgd.between(0, 1) & (df.ead >= 0)
    bad = [int(i) + 2 for i in df.index[~ok]]
    return df[ok].reset_index(drop=True), bad


def _scenario_meta(ids) -> list[dict]:
    out = []
    for s in ids:
        if s in SCEN_BY_ID:
            out.append(dict(SCEN_BY_ID[s]))
            continue
        low = s.lower()
        tipo = ("Transição ordenada" if "paris" in low or low == "hwtp" else "Transição abrupta" if "wake" in low or low == "swuc"
                else "Físico e transição" if "diverg" in low or low == "dire" else "Físico" if "daps" in low or "disaster" in low else "")
        out.append({"id": s, "curto": s[:14], "nome": s, "tipo": tipo})
    order = {s["id"]: i for i, s in enumerate(SCENARIOS)}
    return sorted(out, key=lambda s: order.get(s["id"], 99))


def load_dpd(src=None) -> dict:
    """Lê a ΔPD (e a PD baseline, se houver).

    Retorna dict com:
      dpd: DataFrame longo (cenario, pais, setor, ano, delta_pd_pp)
      base: DataFrame (cenario, pais, ano, baseline_pd_pp) ou vazio
      scenarios: metadados dos cenários
      fonte: 'ilustrativa' ou nome do arquivo
    """
    if src is None:
        df = read_table(DATA / "dpd_ilustrativa.csv")
        df["delta_pd_pp"] = _num(df["delta_pd_pp"])
        df["ano"] = df["ano"].astype(int)
        return {"dpd": df, "base": pd.DataFrame(columns=["cenario", "pais", "ano", "baseline_pd_pp"]),
                "scenarios": _scenario_meta(df["cenario"].unique()), "fonte": "ilustrativa"}
    name = _read_bytes(src)[1] if not hasattr(src, "read") else getattr(src, "name", "arquivo")
    df = read_table(src)
    if "variable" in df:  # formato IIASA (xlsx ou csv largo)
        df = df[df["variable"].astype(str).str.contains(r"pd_adjustment|baseline_pd|default", case=False, regex=True)]
        ycols = [c for c in df.columns if str(c).strip().isdigit() and int(c) in YEARS]
        long = df.melt(id_vars=["scenario", "region", "variable"], value_vars=ycols, var_name="ano", value_name="v")
        long["v"] = _num(long["v"].astype(str))
        long["kind"] = np.where(long["variable"].str.contains("baseline", case=False), "base", "delta")
        long["setor"] = long["variable"].str.split("|").str[-1].map(sector_id)
        long["pais"] = long["region"].map(normalize_country)
        long = long.rename(columns={"scenario": "cenario"})
    else:  # formato longo próprio
        long = df.rename(columns={"scenario": "cenario", "region": "pais", "sector": "setor", "year": "ano"})
        if "pais" not in long:
            long["pais"] = "Brasil"
        long["pais"] = long["pais"].map(normalize_country)
        long["setor"] = long["setor"].map(sector_id)
        long["v"] = _num(long["delta_pd_pp"].astype(str))
        long["kind"] = "delta"
    long["ano"] = pd.to_numeric(long["ano"], errors="coerce")
    long = long.dropna(subset=["ano", "v"])
    long = long[~long["cenario"].astype(str).str.contains(r"baseline|^base$", case=False, regex=True)]
    long["ano"] = long["ano"].astype(int)
    dpd = (long[(long.kind == "delta") & long.setor.notna()]
           .groupby(["cenario", "pais", "setor", "ano"], as_index=False)["v"].mean().rename(columns={"v": "delta_pd_pp"}))
    base = (long[long.kind == "base"].groupby(["cenario", "pais", "ano"], as_index=False)["v"].mean()
            .rename(columns={"v": "baseline_pd_pp"}))
    if dpd.empty:
        raise ValueError("nenhuma série de ΔPD reconhecida (esperado: variáveis pd_adjustment|<setor>)")
    return {"dpd": dpd, "base": base, "scenarios": _scenario_meta(dpd["cenario"].unique()), "fonte": name}


def find_local_ngfs() -> Path | None:
    """Arquivo oficial do CLIMACRED salvo localmente em data/ngfs/ (não versionado)."""
    if not NGFS_DIR.exists():
        return None
    files = sorted(NGFS_DIR.glob("*CLIMACRED*.xlsx")) + sorted(NGFS_DIR.glob("*CLIMACRED*.csv"))
    return files[-1] if files else None
