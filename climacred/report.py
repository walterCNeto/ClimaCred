"""Formatação, relatório em texto e exportação para Excel."""
from __future__ import annotations

import io

import pandas as pd

from .config import SECTOR_NAME, YEARS


REF_TXT = {"ngfs": "PD de linha de base do CLIMACRED", "ngfs+cart": "PD de linha de base do CLIMACRED (média da carteira onde não há série)", "cart": "PD média da carteira no setor", "fix": "PD de referência informada"}


def f3(x) -> str:
    """Número no padrão brasileiro com três casas decimais."""
    if x is None or pd.isna(x):
        return "–"
    x = 0.0 if abs(x) < 5e-4 else float(x)
    return f"{x:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


def f2(x) -> str:
    if x is None or pd.isna(x):
        return "–"
    x = 0.0 if abs(x) < 5e-3 else float(x)
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def money(x_mi) -> str:
    """Valor em R$ milhões -> 'R$ 1,23 bi' ou 'R$ 45,67 mi' (duas casas)."""
    if x_mi is None or pd.isna(x_mi):
        return "–"
    return f"R$ {f2(x_mi / 1000)} bi" if abs(x_mi) >= 1000 else f"R$ {f2(x_mi)} mi"


def unit_for(values) -> tuple[float, str, str]:
    """Escala comum para uma tabela/gráfico: (divisor, 'bilhões'/'milhões', 'bi'/'mi')."""
    v = [abs(float(x)) for x in values if x is not None and not pd.isna(x)]
    return (1000.0, "bilhões", "bi") if v and max(v) >= 1000 else (1.0, "milhões", "mi")


def pc2(x) -> str:
    return "–" if x is None or pd.isna(x) else f2(100 * x) + "%"


def has_pr(pr) -> bool:
    return pr is not None and not pd.isna(pr) and pr > 0


def impact(x_mi, pr, longo: bool = False) -> str:
    """'19,43% do PR' quando o PR foi informado; senão o valor em R$."""
    if has_pr(pr):
        return f"{pc2(x_mi / pr)} do {'Patrimônio de Referência' if longo else 'PR'}"
    return money(x_mi)


def pc(x) -> str:
    return "–" if x is None or pd.isna(x) else f3(100 * x) + "%"


def scenario_table(out: dict) -> pd.DataFrame:
    b, pr = out["base"], out["params"].pr
    nan = float("nan")
    rows = [{"Cenário": "Linha de base", "Ano": "–", "PD média": b["pdw"], "Perda esperada": b["pe"], "Δ PE": nan,
             "Capital ASRF": b["cap"], "Δ capital": nan, "Δ PE líquida de provisão": nan, "Δ total": nan, "Δ total % PR": nan,
             "EAD com ΔPD": nan}]
    for r in out["results"]:
        e = r["ev"]
        rows.append({"Cenário": r["sc"]["nome"], "Ano": str(YEARS[r["yi"]]), "PD média": e["pd_media"],
                     "Perda esperada": e["pe"], "Δ PE": e["dpe"], "Capital ASRF": e["cap"], "Δ capital": e["dcap"],
                     "Δ PE líquida de provisão": e["exc"] - b["exc"], "Δ total": e["dtot"],
                     "Δ total % PR": e["dtot"] / pr if has_pr(pr) else nan,
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


MODEL_LABEL = {"asrf": "ASRF (IRB)", "crp": "CreditRisk+"}


def cap_model(out: dict) -> str:
    m = out.get("cap_model", "asrf")
    return "crp" if m == "crp" and out.get("crp") else "asrf"


def model_delta(out: dict, r: dict, model: str | None = None) -> dict:
    """Variação de PE, PI e total (PE + PI) de um cenário pelo modelo de capital escolhido."""
    model = model or cap_model(out)
    if model == "crp":
        x, b = out["crp"]["cen"][r["sc"]["id"]], out["crp"]["base"]
        return {"dpe": x["pe"] - b["pe"], "dpi": x["pi"] - b["pi"], "dtot": x["cea"] - b["cea"], "tot": x["cea"], "pi": x["pi"]}
    e, b = r["ev"], out["base"]
    return {"dpe": e["dpe"], "dpi": e["dcap"], "dtot": e["dtot"], "tot": e["pe"] + e["cap"], "pi": e["cap"]}


def model_base(out: dict, model: str | None = None) -> dict:
    model = model or cap_model(out)
    if model == "crp":
        b = out["crp"]["base"]
        return {"pe": b["pe"], "pi": b["pi"], "tot": b["cea"]}
    b = out["base"]
    return {"pe": b["pe"], "pi": b["cap"], "tot": b["pe"] + b["cap"]}


def worst_model(out: dict, model: str | None = None) -> dict:
    return max(out["results"], key=lambda r: model_delta(out, r, model)["dtot"])


def capital_compare(out: dict) -> pd.DataFrame:
    """PE, perda inesperada e total pelos dois modelos, na base e em cada cenário (R$ mi)."""
    rows = []
    has_crp = bool(out.get("crp"))
    def row(nome, ano, a, c):  # noqa: E306
        d = {"Cenário": nome, "Ano": ano, "PE": a["pe"], "PI ASRF (K·EAD)": a["pi"], "CEA ASRF (PE + K·EAD)": a["tot"]}
        if has_crp:
            d.update({"PI CreditRisk+": c["pi"], "CEA CreditRisk+": c["tot"]})
        return d
    rows.append(row("Base", "–", model_base(out, "asrf"), model_base(out, "crp") if has_crp else None))
    for r in out["results"]:
        a = model_delta(out, r, "asrf")
        c = model_delta(out, r, "crp") if has_crp else None
        d = row(r["sc"]["nome"], str(YEARS[r["yi"]]), {"pe": r["ev"]["pe"], "pi": a["pi"], "tot": a["tot"]},
                {"pi": c["pi"], "tot": c["tot"]} if has_crp else None)
        d["Δ CEA ASRF"] = a["dtot"]
        if has_crp:
            d["Δ CEA CreditRisk+"] = c["dtot"]
        rows.append(d)
    return pd.DataFrame(rows)


def report_text(out: dict, cart_src: str, dpd_src: str) -> str:
    p, b, R = out["params"], out["base"], out["results"]
    mdl = cap_model(out)
    lab = MODEL_LABEL[mdl]
    other = "crp" if mdl == "asrf" else "asrf"
    w = worst_model(out)
    dw = model_delta(out, w)
    main = [r for r in R if r["ev"]["cobertura"] >= 0.5] or R
    best = min(main, key=lambda r: model_delta(out, r)["dtot"])
    mb = model_base(out)
    c = out["portfolio"]
    nm = c.loc[c["sec"].isna(), "ead"].sum()
    par = [
        f"Escopo. Carteira PJ com {len(c)} contratos e EAD de {money(b['ead'])}"
        f"{' (carteira de exemplo, fictícia)' if cart_src == 'ex' else ''}. "
        + (f"Patrimônio de Referência considerado: {money(p.pr)}." if has_pr(p.pr) else "Patrimônio de Referência não informado; impactos em R$."),
        f"Cenários. {len(R)} cenários de curto prazo do NGFS (2024–2030), com ΔPD por setor "
        f"{'ilustrativa, ancorada em valores publicados e premissas para os demais setores' if dpd_src == 'ill' else 'do modelo CLIMACRED (NGFS Phase 5 Short-Term, IIASA)'}. "
        f"A ΔPD foi aplicada {'por deslocamento Δz a partir da ' + REF_TXT.get(R[0].get('ref_used'), 'PD de referência') if p.mode == 'dz' else 'por soma direta em pontos percentuais'}; "
        f"ano de avaliação: {'pico de cada cenário' if p.year == 'pico' else p.year}.",
        f"Capital de referência: {lab}. Na base, CEA = PE + PI = {money(mb['pe'])} + {money(mb['pi'])} = {money(mb['tot'])}.",
        f"Resultado. O cenário mais severo é {w['sc']['nome']} ({YEARS[w['yi']]}): perda esperada +{money(dw['dpe'])}, "
        f"perda inesperada +{money(dw['dpi'])}, total de {impact(dw['dtot'], p.pr)}. O mais brando é "
        f"{best['sc']['nome']}, com {impact(model_delta(out, best)['dtot'], p.pr)}. Líquida das provisões constituídas, a perda "
        f"esperada incremental no pior cenário é de {money(w['ev']['exc'] - b['exc'])}.",
    ]
    if out.get("crp"):
        do = model_delta(out, w, other)
        par.append(f"Comparação de modelos. No mesmo cenário, pelo {MODEL_LABEL[other]} o aumento do capital total seria de "
                   f"{impact(do['dtot'], p.pr)} (perda inesperada +{money(do['dpi'])}). O ASRF mede o capital contrato a contrato "
                   "com correlação regulatória e ajuste de prazo; o CreditRisk+ mede a carteira inteira e capta concentração.")
    par += [
        f"Sensibilidade ao método de choque. Pela {'soma direta' if p.mode == 'dz' else 'via Δz'}, o impacto ASRF no pior cenário "
        f"seria de {impact(w['other']['dtot'], p.pr)}, contra {impact(w['ev']['dtot'], p.pr)} no método escolhido.",
        f"Cobertura e limites. {'R$ ' + f3(nm) + ' mi de EAD sem setor mapeado ficaram sem choque. ' if nm > 0 else ''}"
        "Balanço estático, LGD constante, sem geografia intra-país e sem mitigadores (seguro rural, Proagro, garantias públicas); "
        "o CLIMACRED não considera garantias governamentais nem programas de apoio. Na abordagem padronizada o RWA regulatório "
        "não reage à PD; o efeito regulatório se dá pela perda esperada e pelas provisões.",
    ]
    tab = f"| Cenário | Ano | Δ PE | Δ PI ({lab}) | Δ total |\n|---|---|---:|---:|---:|\n" + "\n".join(
        f"| {r['sc']['nome']} | {YEARS[r['yi']]} | {money(model_delta(out, r)['dpe'])} | {money(model_delta(out, r)['dpi'])} | "
        f"{impact(model_delta(out, r)['dtot'], p.pr)} |" for r in R)
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
        capital_compare(out).to_excel(xw, sheet_name="Capital_ASRF_x_CRplus", index=False)
        if out.get("crp"):
            crp = out["crp"]
            rows = [{"cenario": "Base", "pe": crp["base"]["pe"], "pi": crp["base"]["pi"], "cea": crp["base"]["cea"],
                     "quantil": crp["base"]["quantil"]}]
            rows += [{"cenario": k, "pe": v["pe"], "pi": v["pi"], "cea": v["cea"], "quantil": v["quantil"]} for k, v in crp["cen"].items()]
            pd.DataFrame(rows).to_excel(xw, sheet_name="CreditRiskPlus", index=False)
            crp["base"]["fatores"].to_excel(xw, sheet_name="CRPlus_fatores_base", index=False)
        out["portfolio"].drop(columns=["capb", "peb"]).to_excel(xw, sheet_name="Carteira", index=False)
    return buf.getvalue()
