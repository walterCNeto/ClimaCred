"""ClimaCred – estresse climático de carteira PJ com a ΔPD do CLIMACRED (cenários NGFS de curto prazo).

Execução local:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from climacred.config import ANCHORS, INPUT_LAYOUT, MAP_ROWS, SECTOR_NAME, YEARS
from climacred.engine import Params, run
from climacred.io import DATA, load_dpd, load_portfolio
from climacred.report import f3, pc, report_text, scenario_table, sector_table, to_excel, worst

st.set_page_config(page_title="ClimaCred – estresse climático", layout="wide")
RED, SLATE, GREY = "#e3120b", "#2e6f8e", "#8a979f"


def color(sc):
    t = sc.get("tipo", "")
    return SLATE if "Transição" in t else RED if ("Físico" in t) else GREY


# ---------------- barra lateral ----------------
with st.sidebar:
    st.header("Entradas")
    up_cart = st.file_uploader("Carteira (CSV)", type=["csv", "txt"])
    up_dpd = st.file_uploader("ΔPD por setor (CSV do IIASA ou formato longo)", type=["csv", "txt"])
    st.header("Parâmetros")
    mode = st.radio("Aplicação da ΔPD ao contrato", ["dz", "add"], format_func=lambda m: {
        "dz": "Deslocamento Δz (preserva ordenação)", "add": "Soma direta em p.p. (como no NGFS)"}[m])
    year = st.selectbox("Ano de avaliação", ["pico"] + YEARS, format_func=lambda y: "Pico de cada cenário" if y == "pico" else str(y))
    ref = st.radio("PD de referência do setor (para Δz)", ["cart", "fix"], format_func=lambda r: {
        "cart": "Média da carteira por setor (ponderada por EAD)", "fix": "Valor único informado"}[r])
    ref_fix = st.number_input("PD de referência única (%)", 0.03, 50.0, 2.62, 0.01) / 100
    pr = st.number_input("Patrimônio de Referência (R$ mi)", 1.0, value=1800.0, step=10.0)

try:
    cart, bad = load_portfolio(up_cart)
except Exception as e:  # noqa: BLE001
    st.error(f"Não foi possível ler a carteira: {e}")
    st.stop()
try:
    dpd, scenarios = load_dpd(up_dpd)
except Exception as e:  # noqa: BLE001
    st.error(f"Não foi possível ler a ΔPD: {e}")
    st.stop()
cart_src, dpd_src = ("up" if up_cart else "ex"), ("up" if up_dpd else "ill")
countries = sorted(dpd["pais"].unique())
with st.sidebar:
    fb = st.selectbox("País da ΔPD quando o contrato não tiver série", countries,
                      index=countries.index("Brasil") if "Brasil" in countries else 0)
    st.caption(("Carteira de exemplo (fictícia). " if cart_src == "ex" else f"Carteira carregada: {len(cart)} contratos. ")
               + ("ΔPD ilustrativa." if dpd_src == "ill" else f"ΔPD carregada: {len(scenarios)} cenários."))
    if bad:
        st.warning(f"{len(bad)} linhas ignoradas (ex.: {', '.join(map(str, bad[:5]))}).")

out = run(cart, dpd, scenarios, Params(mode=mode, year=year, ref=ref, ref_fix=ref_fix, pr=pr, fallback_country=fb))
B, R, W = out["base"], out["results"], worst(out)

# ---------------- cabeçalho ----------------
st.title(f"{W['sc']['nome']}: impacto de {pc(W['ev']['dtot'] / pr)} do PR em {YEARS[W['yi']]}")
st.write(f"No pior cenário, a perda esperada da carteira PJ sobe R$ {f3(W['ev']['dpe'])} mi e o capital econômico "
         f"R$ {f3(W['ev']['dcap'])} mi, com PD média ponderada de {pc(B['pdw'])} para {pc(W['ev']['pd_media'])}.")
if dpd_src == "ill":
    st.warning("ΔPD ilustrativa: carregue a série do NGFS Scenario Explorer (IIASA) para resultados de uso real.")
k = st.columns(6)
for col, (v, lab) in zip(k, [(f3(B["ead"] / 1000), "EAD (R$ bi)"), (f3(B["pe"]), "Perda esperada base"),
                             (f3(B["cap"]), "Capital ASRF base"), ("+" + f3(W["ev"]["dpe"]), "Δ PE, pior cenário"),
                             ("+" + f3(W["ev"]["dcap"]), "Δ capital, pior cenário"), (pc(W["ev"]["dtot"] / pr), "Δ total % PR")]):
    col.metric(lab, v)

c1, c2 = st.columns(2)
with c1:
    names = [f"{r['sc']['curto']} ({YEARS[r['yi']]})" for r in R]
    fig = go.Figure([go.Bar(y=names, x=[100 * r["ev"]["dpe"] / pr for r in R], name="Perda esperada", orientation="h", marker_color=RED),
                     go.Bar(y=names, x=[100 * r["ev"]["dcap"] / pr for r in R], name="Capital ASRF", orientation="h", marker_color=SLATE)])
    fig.update_layout(barmode="stack", title="Impacto incremental em % do PR", xaxis_title="% do PR", height=380, yaxis=dict(autorange="reversed"),
                      margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.2), separators=",.")
    st.plotly_chart(fig, width="stretch")
with c2:
    y = out["yearly"][out["yearly"].modo == mode]
    fig = go.Figure()
    for r in R:
        s = y[y.cenario == r["sc"]["id"]]
        fig.add_trace(go.Scatter(x=s.ano, y=s.dpe, name=r["sc"]["curto"], mode="lines+markers",
                                 line=dict(color=color(r["sc"]), dash="dash" if r["sc"]["id"] in ("SWUC", "DIRE") else "solid")))
    fig.update_layout(title="Perda esperada incremental por ano (R$ mi)", height=380, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.2), separators=",.")
    st.plotly_chart(fig, width="stretch")

# ---------------- abas ----------------
tabs = st.tabs(["Cenários", "Setores", "Contratos", "Aditivo × Δz", "Base de entrada", "Tabela ΔPD", "Metodologia", "Relatório"])
fmt_cols = {"PD média": pc, "Δ total % PR": pc, "EAD com ΔPD": pc}

with tabs[0]:
    t = scenario_table(out)
    st.dataframe(t.style.format({c: fmt_cols.get(c, f3) for c in t.columns if c not in ("Cenário", "Ano")}, na_rep="–"),
                 hide_index=True, width="stretch")
    st.caption(f"Ano de avaliação: {'pico de cada cenário (maior soma de Δ PE e Δ capital)' if year == 'pico' else year}. "
               f"Aplicação: {'Δz' if mode == 'dz' else 'soma direta'}. Valores em R$ mi.")

with tabs[1]:
    s = sector_table(out)
    st.subheader(f"{s.index[0]} concentra a maior perda incremental")
    st.dataframe(s.style.format(f3).background_gradient(cmap="Reds", subset=[c for c in s.columns if c != "EAD"]),
                 width="stretch")

with tabs[2]:
    st.subheader(f"Contratos mais afetados em {W['sc']['nome']}, {YEARS[W['yi']]}")
    top = W["per"].assign(total=W["per"].delta_pe + W["per"].delta_capital).nlargest(15, "total")
    top = top.assign(setor=top.setor.map(SECTOR_NAME))[["id_contrato", "cliente", "setor", "rating", "ead", "delta_pd_pp",
                                                        "pd_base", "pd_estressada", "delta_pe", "delta_capital"]]
    st.dataframe(top.style.format({"ead": f3, "delta_pd_pp": f3, "pd_base": pc, "pd_estressada": pc, "delta_pe": f3,
                                   "delta_capital": f3}), hide_index=True, width="stretch")

with tabs[3]:
    st.write("O CLIMACRED entrega a ΔPD da firma representativa do setor. A soma direta trata igual um rating A e um rating B; "
             "o Δz preserva a ordenação. As duas coincidem quando a PD do contrato é igual à PD de referência do setor.")
    a, d = ("other", "ev") if mode == "dz" else ("ev", "other")
    cmp = pd.DataFrame([{"Cenário": r["sc"]["nome"], "Ano": YEARS[r["yi"]], "Δ PE soma direta": r[a]["dpe"],
                         "Δ PE via Δz": r[d]["dpe"], "Δ capital soma direta": r[a]["dcap"], "Δ capital via Δz": r[d]["dcap"],
                         "Δ total soma direta % PR": r[a]["dtot"] / pr, "Δ total via Δz % PR": r[d]["dtot"] / pr} for r in R])
    st.dataframe(cmp.style.format({c: (pc if "%" in c else f3) for c in cmp.columns if c not in ("Cenário", "Ano")}),
                 hide_index=True, width="stretch")

with tabs[4]:
    l, r_ = st.columns(2)
    with l:
        st.subheader("Layout esperado")
        st.dataframe(pd.DataFrame(INPUT_LAYOUT, columns=["Coluna", "Tipo", "Descrição", "Exemplo"]), hide_index=True)
        st.caption("Separador vírgula ou ponto e vírgula; decimal com ponto ou vírgula. Taxas em decimal (0,012 = 1,200%).")
        st.download_button("Baixar carteira de exemplo (CSV)", (DATA / "carteira_exemplo.csv").read_bytes(),
                           "carteira_exemplo.csv", "text/csv")
    with r_:
        c = out["portfolio"]
        nm = c[c.sec.isna()]
        st.subheader("Resumo da carteira")
        st.write(f"{len(c)} contratos · EAD R$ {f3(B['ead'])} mi · PD média {pc(B['pdw'])} · provisão R$ {f3(c.provisao.sum())} mi."
                 + (f" **{len(nm)} contratos sem setor mapeado** (EAD R$ {f3(nm.ead.sum())} mi) ficam sem choque." if len(nm) else ""))
        st.subheader("De-para CNAE → setor GEM-E3")
        st.dataframe(pd.DataFrame([(a_, SECTOR_NAME[b_]) for a_, b_ in MAP_ROWS], columns=["Divisões CNAE", "Setor"]), hide_index=True)
    with st.expander("Primeiras linhas da carteira"):
        st.dataframe(c.head(20), hide_index=True)

with tabs[5]:
    a1, a2 = st.columns(2)
    sc_sel = a1.selectbox("Cenário", [s["id"] for s in scenarios], format_func=lambda i: next(s["nome"] for s in scenarios if s["id"] == i))
    pa_sel = a2.selectbox("País", countries, index=countries.index(fb))
    tab = dpd[(dpd.cenario == sc_sel) & (dpd.pais == pa_sel)].pivot_table(index="setor", columns="ano", values="delta_pd_pp")
    tab.index = tab.index.map(lambda x: SECTOR_NAME.get(x, x))
    st.dataframe(tab.style.format(f3), width="stretch")
    if dpd_src == "ill":
        st.caption("Valores ilustrativos (p.p. sobre a linha de base). Âncoras publicadas: "
                   + "; ".join(f"{SECTOR_NAME[s]} {y} em {c_}: {t}" for (c_, s, y), t in ANCHORS.items())
                   + ". Os demais são premissas a substituir pela série do IIASA.")
    with st.expander("Como montar o CSV a partir do NGFS Scenario Explorer"):
        st.markdown("1. Acesse o NGFS Scenario Explorer da IIASA, base **NGFS Phase 5 Short-Term** (entrada como convidado).\n"
                    "2. Filtre a região **Brazil** e as variáveis de probabilidade de default por setor, todos os cenários.\n"
                    "3. Exporte em CSV (formato largo: Model, Scenario, Region, Variable, Unit, 2024…2030) e carregue na barra lateral.\n\n"
                    "Formato longo alternativo:")
        st.code("cenario,pais,setor,ano,delta_pd_pp\nHighway to Paris,Brasil,Agriculture,2030,0.8", language="text")

with tabs[6]:
    st.markdown((DATA.parent / "docs" / "metodologia.md").read_text(encoding="utf-8"))

with tabs[7]:
    md = report_text(out, cart_src, dpd_src)
    st.markdown(md)
    d1, d2, d3 = st.columns(3)
    d1.download_button("Relatório (Markdown)", md.encode("utf-8"), "relatorio_climacred.md", "text/markdown")
    d2.download_button("Resultados completos (Excel)", to_excel(out, dpd, md), "resultados_climacred.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    d3.download_button("Resultados por contrato (CSV)", pd.concat([r["per"] for r in R]).to_csv(index=False).encode("utf-8"),
                       "resultados_contratos.csv", "text/csv")
