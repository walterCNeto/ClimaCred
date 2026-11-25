"""Formatação, relatório em texto e exportação para Excel."""
from __future__ import annotations

import io

import pandas as pd

from .config import SECTOR_NAME, YEARS


def f3(x) -> str:
    """Número no padrão brasileiro com três casas decimais."""
    if x is None or pd.isna(x):
        return "–"
    x = 0.0 if abs(x) < 5e-4 else float(x)
    return f"{x:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pc(x) -> str:
    return "–" if x is None or pd.isna(x) else f3(100 * x) + "%"


def scenario_table(out: dict) -> pd.DataFrame:
    b, pr = out["base"], out["params"].pr
    rows = [{"Cenário": "Linha de base", "Ano": "–", "PD média": b["pdw"], "Perda esperada": b["pe"], "Δ PE": None,
             "Capital ASRF": b["cap"], "Δ capital": None, "Δ PE líquida de provisão": None, "Δ total % PR": None,
             "EAD com ΔPD": None}]
    for r in out["results"]:
        e = r["ev"]
        rows.append({"Cenário": r["sc"]["nome"], "Ano": str(YEARS[r["yi"]]), "PD média": e["pd_media"],
                     "Perda esperada": e["pe"], "Δ PE": e["dpe"], "Capital ASRF": e["cap"], "Δ capital": e["dcap"],
                     "Δ PE líquida de provisão": e["exc"] - b["exc"], "Δ total % PR": e["dtot"] / pr,
                     "EAD com ΔPD": e["cobertura"]})
    return pd.DataFrame(rows)


def sector_table(out: dict) -> pd.DataFrame:
    c = out["portfolio"]
    t = c.assign(setor=c["sec"].map(SECTOR_NAME).fillna("Sem mapeamento")).groupby("setor")["ead"].sum().rename("EAD").to_frame()
    for r in out["results"]:
        per = r["per"].assign(setor=r["per"]["setor"].map(SECTOR_NAME).fillna("Sem mapeamento"))
        t[r["sc"]["curto"]] = per.groupby("setor")["delta_pe"].sum()
    cols = [r["sc"]["curto"] for r in out["results"]]
    t = t.fillna(0)
    return t.loc[t[cols].max(axis=1).sort_values(ascending=False).index]


def worst(out: dict) -> dict:
    return max(out["results"], key=lambda r: r["ev"]["dtot"])


def report_text(out: dict, cart_src: str, dpd_src: str) -> str:
    p, b, R = out["params"], out["base"], out["results"]
    w, best = worst(out), min(R, key=lambda r: r["ev"]["dtot"])
    c = out["portfolio"]
    nm = c.loc[c["sec"].isna(), "ead"].sum()
    par = [
        f"Escopo. Carteira PJ com {len(c)} contratos e EAD de R$ {f3(b['ead'])} mi"
        f"{' (carteira de exemplo, fictícia)' if cart_src == 'ex' else ''}. Perda esperada base de R$ {f3(b['pe'])} mi "
        f"e capital econômico base (ASRF) de R$ {f3(b['cap'])} mi. Patrimônio de Referência considerado: R$ {f3(p.pr)} mi.",
        f"Cenários. {len(R)} cenários de curto prazo do NGFS (2025–2030), com ΔPD por setor "
        f"{'ilustrativa, ancorada em valores publicados e premissas para os demais setores' if dpd_src == 'ill' else 'carregada a partir da série informada pelo usuário'}. "
        f"A ΔPD foi aplicada {'por deslocamento Δz a partir da PD de referência do setor' if p.mode == 'dz' else 'por soma direta em pontos percentuais'}; "
        f"ano de avaliação: {'pico de cada cenário' if p.year == 'pico' else p.year}.",
        f"Resultado. O cenário mais severo é {w['sc']['nome']} ({YEARS[w['yi']]}): perda esperada +R$ {f3(w['ev']['dpe'])} mi, "
        f"capital econômico +R$ {f3(w['ev']['dcap'])} mi, total de {pc(w['ev']['dtot'] / p.pr)} do PR. O mais brando é "
        f"{best['sc']['nome']}, com {pc(best['ev']['dtot'] / p.pr)} do PR. Líquida das provisões constituídas, a perda "
        f"incremental no pior cenário é de R$ {f3(w['ev']['exc'] - b['exc'])} mi.",
        f"Sensibilidade ao método. Pela {'soma direta' if p.mode == 'dz' else 'via Δz'}, o impacto total no pior cenário seria de "
        f"{pc(w['other']['dtot'] / p.pr)} do PR, contra {pc(w['ev']['dtot'] / p.pr)} no método escolhido.",
        f"Cobertura e limites. {'R$ ' + f3(nm) + ' mi de EAD sem setor mapeado ficaram sem choque. ' if nm > 0 else ''}"
        "Balanço estático, LGD constante, sem geografia intra-país e sem mitigadores (seguro rural, Proagro, garantias públicas). "
        "O capital ASRF é tratado como capital econômico; na abordagem padronizada o RWA regulatório não reage à PD, e o efeito "
        "regulatório se dá pela perda esperada e pelas provisões.",
    ]
    tab = "| Cenário | Ano | Δ PE (R$ mi) | Δ capital (R$ mi) | Δ total % PR |\n|---|---|---:|---:|---:|\n" + "\n".join(
        f"| {r['sc']['nome']} | {YEARS[r['yi']]} | {f3(r['ev']['dpe'])} | {f3(r['ev']['dcap'])} | {pc(r['ev']['dtot'] / p.pr)} |"
        for r in R)
    return "# Relatório de impacto – estresse climático (NGFS curto prazo / CLIMACRED)\n\n" + "\n\n".join(par) + "\n\n" + tab + "\n"


def to_excel(out: dict, dpd: pd.DataFrame, report_md: str) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"Relatório": report_md.splitlines()}).to_excel(xw, sheet_name="Relatorio", index=False)
        scenario_table(out).to_excel(xw, sheet_name="Cenarios", index=False)
        out["yearly"].to_excel(xw, sheet_name="Trajetoria", index=False)
        sector_table(out).to_excel(xw, sheet_name="Setores")
        pd.concat([r["per"] for r in out["results"]]).to_excel(xw, sheet_name="Contratos", index=False)
        dpd.to_excel(xw, sheet_name="DeltaPD", index=False)
        out["portfolio"].drop(columns=["capb", "peb"]).to_excel(xw, sheet_name="Carteira", index=False)
    return buf.getvalue()
