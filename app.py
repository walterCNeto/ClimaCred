"""ClimaCred – estresse climático de carteira PJ com a ΔPD do CLIMACRED (cenários NGFS de curto prazo).

Execução local:  streamlit run app.py
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from climacred.article import build_article
from climacred.creditrisk import CRParams, run_crplus
from climacred.figures import fig_capital
from climacred.config import ANCHORS, INPUT_LAYOUT, MAP_ROWS, SECTOR_NAME, YEARS
from climacred.engine import Params, run
from climacred.io import DATA, find_local_ngfs, load_dpd, load_portfolio
from climacred.report import (MODEL_LABEL, cap_model, capital_compare, model_base, model_delta, worst_model)
from climacred.report import f3, has_pr, impact, money, pc, report_text, scenario_table, sector_table, to_excel, worst

st.set_page_config(page_title="ClimaCred – estresse climático", layout="wide")
RED, SLATE, GREY = "#e3120b", "#2e6f8e", "#8a979f"


def color(sc):
    t = sc.get("tipo", "")
    return SLATE if "Transição" in t else RED if ("Físico" in t) else GREY


@st.cache_data(show_spinner="Lendo a série do CLIMACRED…")
def cached_dpd(raw: bytes | None, name: str) -> dict:
    if raw is None:
        return load_dpd(None)
    buf = io.BytesIO(raw)
    buf.name = name
    return load_dpd(buf)


REF_LABEL = {"ngfs": "PD de linha de base do CLIMACRED (baseline_pd)",
             "ngfs+cart": "baseline_pd do CLIMACRED (média da carteira onde não há série)", "cart": "Média da carteira por setor (ponderada por EAD)",
             "fix": "Valor único informado"}

# ---------------- barra lateral ----------------
local = find_local_ngfs()
with st.sidebar:
    st.header("Entradas")
    up_cart = st.file_uploader("Carteira (CSV ou XLSX)", type=["csv", "txt", "xlsx"])
    up_dpd = st.file_uploader("Série do CLIMACRED (xlsx do IIASA ou CSV)", type=["csv", "txt", "xlsx"])
    st.header("Parâmetros")
    mode = st.radio("Aplicação da ΔPD ao contrato", ["dz", "add"], format_func=lambda m: {
        "dz": "Deslocamento Δz (preserva ordenação)", "add": "Soma direta em p.p. (como publicada)"}[m])
    ref, ref_fix, horizon = "ngfs", 0.0262, 1.0
    if mode == "dz":
        ref = st.radio("PD de referência para o Δz", ["ngfs", "cart", "fix"], format_func=REF_LABEL.get)
        if ref == "fix":
            ref_fix = st.number_input("PD de referência única (%)", 0.03, 50.0, 2.62, 0.01,
                                      help="PD sobre a qual a ΔPD do CLIMACRED é convertida em Δz, igual para todos os setores. "
                                           "Quanto menor, maior o choque.") / 100
        if st.toggle("Ajustar o Δz ao horizonte de 12 meses", value=False,
                     help="Converte a PD de referência e a PD de referência + ΔPD para 12 meses por intensidade de default "
                          "constante, PD₁ = 1 − (1 − PD_T)^(1/T), antes de medir o Δz. Premissa: o horizonte T da baseline_pd "
                          "do CLIMACRED, que deve ser documentado."):
            horizon = st.number_input("Horizonte T da baseline_pd do CLIMACRED (anos)", 1.0, 30.0, 5.0, 0.5, format="%.1f")
    year = st.selectbox("Ano de avaliação", ["pico"] + YEARS, format_func=lambda y: "Pico de cada cenário" if y == "pico" else str(y))
    if up_cart is not None and st.session_state.get("pr_from_example"):
        st.session_state["pr_input"], st.session_state["pr_from_example"] = None, False
    pr_in = st.number_input("Patrimônio de Referência (R$ mi), opcional", min_value=1.0, value=None, step=10.0, key="pr_input",
                            placeholder="ex.: 1800",
                            help="Só serve para expressar o impacto como % do capital. Informe o PR do banco ou o capital "
                                 "alocado à carteira. Em branco, os resultados saem só em R$.")
    pr = float(pr_in) if pr_in else float("nan")
    cap_mdl = st.radio("Capital de referência (título e % do PR)", ["asrf", "crp"],
                       format_func=lambda m: {"asrf": "ASRF – IRB (Basileia/BCB)", "crp": "CreditRisk+"}[m],
                       help="Os dois capitais são sempre calculados; esta escolha define qual alimenta o título, os indicadores "
                            "e o resumo do relatório.")
    with st.expander("ASRF / IRB (calibragem)"):
        irb_floor = st.number_input("Piso de PD (%)", 0.01, 1.0, 0.03, 0.01, format="%.2f",
                                    help="Basileia II: 0,03%; Basileia III (revisão final): 0,05%.") / 100
        irb_scale = st.number_input("Fator de escala sobre K", 1.00, 1.20, 1.00, 0.01, format="%.2f",
                                    help="Basileia II previa 1,06 para o IRB; 1,00 mantém K sem escala.")
    with st.expander("CreditRisk+ (calibragem)"):
        cr_conf = st.selectbox("Nível de confiança", [0.99, 0.995, 0.999, 0.9995], index=2, format_func=lambda x: f"{100 * x:.2f}%".replace(".", ","))
        cr_vol = st.slider("Volatilidade relativa da taxa de default (σ/μ)", 0.10, 3.00, 1.00, 0.05,
                           help="Desvio-padrão da taxa de inadimplência de cada fator dividido pela média. Quanto maior, mais "
                                "pesada a cauda e maior a perda inesperada.")
        cr_w0 = st.slider("Peso idiossincrático (w₀)", 0.00, 1.00, 0.00, 0.05,
                          help="Parcela do risco de cada contrato sem ligação com fator setorial (Poisson puro).")
        cr_sec = st.radio("Fatores de risco", ["climacred", "single"], format_func=lambda x: {
            "climacred": "Um fator por setor CLIMACRED", "single": "Fator sistêmico único"}[x])
        cr_svol = st.number_input("Multiplicador de σ/μ no estresse", 0.5, 3.0, 1.0, 0.1,
                                  help="1,0 mantém a mesma volatilidade relativa no estresse; acima de 1 assume cauda mais pesada.")
        cr_bands = st.number_input("Bandas para a maior exposição", 20, 1000, 200, 20,
                                   help="Define a unidade de perda L₀ = maior LGD×EAD ÷ nº de bandas. Mais bandas, mais precisão.")

# ---------------- carteira: upload ou exemplo sob demanda ----------------
def _use_example():
    st.session_state["cart_mode"] = "ex"
    if not st.session_state.get("pr_input"):
        st.session_state["pr_input"], st.session_state["pr_from_example"] = 1800.0, True


def _drop_example():
    st.session_state["cart_mode"] = None
    if st.session_state.get("pr_from_example"):
        st.session_state["pr_input"], st.session_state["pr_from_example"] = None, False


cart_mode = "up" if up_cart is not None else st.session_state.get("cart_mode")
cart, bad = None, []
if cart_mode:
    try:
        cart, bad = load_portfolio(up_cart if cart_mode == "up" else None)
    except Exception as e:  # noqa: BLE001
        st.error(f"Não foi possível ler a carteira: {e}")
        st.stop()
try:
    if up_dpd is not None:
        data = cached_dpd(up_dpd.getvalue(), up_dpd.name)
    elif local is not None:
        data = cached_dpd(local.read_bytes(), local.name)
    else:
        data = cached_dpd(None, "")
except Exception as e:  # noqa: BLE001
    st.error(f"Não foi possível ler a série de ΔPD: {e}")
    st.stop()
dpd, scenarios = data["dpd"], data["scenarios"]
cart_src, dpd_src = (cart_mode or "none"), ("ill" if data["fonte"] == "ilustrativa" else "up")
countries = sorted(dpd["pais"].unique())
bra = [s for s in scenarios if s["id"] in set(dpd.loc[dpd.pais == "Brasil", "cenario"])]
with st.sidebar:
    fb = st.selectbox("País da série quando o contrato não tiver a sua", countries,
                      index=countries.index("Brasil") if "Brasil" in countries else 0)
    if bad:
        st.warning(f"{len(bad)} linhas ignoradas (ex.: {', '.join(map(str, bad[:5]))}).")
    if ref == "ngfs" and data["base"].empty:
        st.info("A série carregada não traz baseline_pd; o Δz usa a média da carteira por setor.")

# ---------------- execução sob demanda ----------------
def _sig(f):
    return None if f is None else (f.name, f.size)


run_key = (cart_mode, _sig(up_cart), _sig(up_dpd), local.name if local else None, mode, ref, round(ref_fix, 6), year, pr_in, fb,
           cr_conf, cr_vol, cr_w0, cr_sec, cr_svol, cr_bands, cap_mdl, irb_floor, irb_scale, horizon)
with st.sidebar:
    st.divider()
    clicked = st.button("▶ Executar", type="primary", width="stretch", disabled=cart is None) \
        or bool(st.session_state.get("run_main"))
    if cart is None:
        st.caption("Carregue uma carteira ou use a de exemplo para executar.")
    elif st.session_state.get("run_key") not in (None, run_key):
        st.caption("Entradas ou parâmetros mudaram desde a última execução.")

if clicked and cart is not None:
    with st.spinner("Calculando perdas e capital em todos os cenários…"):
        _o = run(cart, data, Params(mode=mode, year=year, ref=ref, ref_fix=ref_fix, pr=pr, fallback_country=fb,
                                    pd_floor=irb_floor, irb_scale=irb_scale, horizon=horizon))
        _o["crp"] = run_crplus(_o, CRParams(conf=cr_conf, vol_ratio=cr_vol, w0=cr_w0, sectors=cr_sec, stress_vol=cr_svol,
                                            bands_max=int(cr_bands)))
        _o["cap_model"] = cap_mdl
        st.session_state["out"] = _o
        st.session_state["run_key"] = run_key
        st.session_state.pop("artigo_pdf", None)

if cart is None or st.session_state.get("run_key") != run_key:
    st.title("ClimaCred – estresse climático da carteira PJ")
    st.markdown(
        "Aplica a variação de PD por setor do modelo **CLIMACRED** (cenários de curto prazo do NGFS) à carteira e mede o impacto "
        "em **perda esperada** e **capital econômico**.")
    if cart is not None and st.session_state.get("run_key") is not None:
        st.info("As entradas ou os parâmetros mudaram desde a última execução. Clique em **▶ Executar** para atualizar os resultados.")

    with st.container(border=True):
        st.markdown("**1. Carteira de crédito**")
        if cart is None:
            st.write("Nenhuma carteira carregada. Envie um CSV ou XLSX na barra lateral ou use a carteira de exemplo.")
            st.button("Usar carteira de exemplo (fictícia)", on_click=_use_example)
        else:
            orig = up_cart.name if cart_mode == "up" else "carteira de exemplo, fictícia"
            n = f"{len(cart):,}".replace(",", ".")
            st.write(f"✓ {orig}: {n} contratos, EAD de {money(cart['ead'].sum())}.")
            if cart_mode == "ex":
                st.button("Remover carteira de exemplo", on_click=_drop_example)
    with st.container(border=True):
        st.markdown("**2. Série de ΔPD por setor**")
        if dpd_src == "ill":
            st.write("⚠ Série ilustrativa, só para demonstração. Para resultados reais, envie o arquivo CLIMACRED na barra lateral "
                     "ou salve-o em `data/ngfs/`.")
        else:
            origem = "enviado na barra lateral" if up_dpd is not None else "lido automaticamente de data/ngfs/"
            st.write(f"✓ Série oficial do CLIMACRED (NGFS Phase 5 Short-Term, IIASA): arquivo {data['fonte']}, {origem}.")
        st.caption(f"{len(bra)} cenários com série para o Brasil: " + ", ".join(s["nome"] for s in bra) + ". "
                   + ("Os demais cenários do arquivo cobrem outras regiões e só afetam exposições nesses países."
                      if len(scenarios) > len(bra) else ""))
    with st.container(border=True):
        st.markdown("**3. Parâmetros e execução**")
        st.write("Ajuste na barra lateral a forma de aplicar a ΔPD, a PD de referência e o ano de avaliação. O Patrimônio de "
                 "Referência é opcional: informe-o para ver o impacto em % do capital. Depois, clique em Executar.")
        st.button("▶ Executar", type="primary", key="run_main", disabled=cart is None)
    st.stop()

out = st.session_state["out"]
B, R = out["base"], out["results"]
MDL = cap_model(out)
MLAB = MODEL_LABEL[MDL]
W = worst_model(out)
DW, MB = model_delta(out, W), model_base(out)

# ---------------- cabeçalho ----------------
st.title(f"{W['sc']['nome']}: impacto de {impact(DW['dtot'], pr)} em {YEARS[W['yi']]}")
st.write(f"Capital de referência: **{MLAB}**. No pior cenário, a perda esperada da carteira PJ sobe {money(DW['dpe'])} e a "
         f"perda inesperada {money(DW['dpi'])}, com PD média ponderada de {pc(B['pdw'])} para {pc(W['ev']['pd_media'])}.")
if dpd_src == "ill":
    st.warning("ΔPD ilustrativa: carregue o arquivo CLIMACRED do NGFS Scenario Explorer (IIASA) ou salve-o em data/ngfs/.")
ru = {r["ref_used"] for r in R}
st.caption(f"Série: {data['fonte']} · aplicação: {'Δz' if mode == 'dz' else 'soma direta'}"
           + (f" · referência do Δz: {', '.join(REF_LABEL[x] for x in ru)}" if mode == "dz" else "")
           + (f" · Δz anualizado (T = {horizon:.1f} anos)".replace(".", ",") if mode == "dz" and horizon > 1 else "")
           + (f" · {B['n_def']} contratos em estágio 3 ({money(B['ead_def'])} de EAD) sem choque de PD" if B.get("n_def") else "")
           + (f" · cenários sem série para os países da carteira: {', '.join(s['id'] for s in out['skipped'])}" if out["skipped"] else ""))
k = st.columns(6)
for col, (v, lab) in zip(k, [(f3(B["ead"] / 1000), "EAD (R$ bi)"), (f3(MB["pe"]), "PE base"),
                             (f3(MB["pi"]), f"PI base ({MLAB})"), ("+" + f3(DW["dpe"]), "Δ PE, pior cenário"),
                             ("+" + f3(DW["dpi"]), "Δ PI, pior cenário"),
                             ((pc(DW["dtot"] / pr), "Δ CEA % PR") if has_pr(pr) else ("+" + f3(DW["dtot"]), "Δ CEA (PE + PI)"))]):
    col.metric(lab, v)

c1, c2 = st.columns(2)
with c1:
    names = [f"{r['sc']['curto']} ({YEARS[r['yi']]})" for r in R]
    dv, xt = (pr / 100, "% do PR") if has_pr(pr) else (1.0, "R$ mi")
    fig = go.Figure([go.Bar(y=names, x=[model_delta(out, r)["dpe"] / dv for r in R], name="Δ perda esperada", orientation="h",
                            marker_color=RED),
                     go.Bar(y=names, x=[model_delta(out, r)["dpi"] / dv for r in R], name=f"Δ perda inesperada ({MLAB})",
                            orientation="h", marker_color=SLATE)])
    fig.update_layout(barmode="stack", title=f"Δ CEA por cenário – {MLAB} ({xt})", xaxis_title=xt, height=380,
                      yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.2),
                      separators=",.")
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
tabs = st.tabs(["Cenários", "CreditRisk+", "Setores", "Contratos", "Aditivo × Δz", "Base de entrada", "Tabela ΔPD", "Metodologia", "Relatório"])
fmt_cols = {"PD média": pc, "Δ total % PR": pc, "EAD com ΔPD": pc}

with tabs[0]:
    st.subheader("Capital econômico: ASRF (IRB) × CreditRisk+")
    cc = capital_compare(out)
    st.dataframe(cc.style.format({c_: f3 for c_ in cc.columns if c_ not in ("Cenário", "Ano")}, na_rep="–"),
                 hide_index=True, width="stretch")
    st.caption("CEA = PE + PI. No ASRF, PI = K·EAD (fórmula IRB de Basileia, adotada pelo BCB na Resolução BCB nº 303/2023), "
               "somado contrato a contrato; no CreditRisk+, PI = quantil − média da distribuição de perdas da carteira. "
               f"O capital de referência ({MLAB}) é escolhido na barra lateral. Valores em R$ mi.")
    st.subheader("Perdas e capital ASRF por cenário")
    t = scenario_table(out)
    if not has_pr(pr):
        t = t.drop(columns=["Δ total % PR"])
    st.dataframe(t.style.format({c: fmt_cols.get(c, f3) for c in t.columns if c not in ("Cenário", "Ano")}, na_rep="–"),
                 hide_index=True, width="stretch")
    st.caption(f"Ano de avaliação: {'pico de cada cenário (maior soma de Δ PE e Δ capital)' if year == 'pico' else year}. "
               f"Aplicação: {'Δz' if mode == 'dz' else 'soma direta'}. Valores em R$ mi.")

with tabs[1]:
    crp = out["crp"]
    cb, cpar = crp["base"], crp["params"]
    st.subheader("Capital econômico pelo CreditRisk+: CEA = PE + PI")
    st.caption(f"Confiança {100 * cpar.conf:.2f}%".replace(".", ",") + f" · σ/μ = {f3(cpar.vol_ratio)} · w₀ = {f3(cpar.w0)} · "
               + ("um fator por setor CLIMACRED" if cpar.sectors == "climacred" else "fator sistêmico único")
               + f" · multiplicador de σ/μ no estresse = {f3(cpar.stress_vol)} · unidade de perda L₀ = R$ {f3(crp['L0'])} mi")
    m_ = st.columns(3)
    m_[0].metric("PE base", money(cb["pe"]))
    m_[1].metric("PI base", money(cb["pi"]))
    m_[2].metric("CEA base", money(cb["cea"]))
    rows = []
    for r in R:
        x = crp["cen"][r["sc"]["id"]]
        rows.append({"Cenário": r["sc"]["nome"], "Ano": str(YEARS[r["yi"]]), "PE stress": x["pe"], "PI stress": x["pi"],
                     "CEA stress": x["cea"], "Δ PE": x["pe"] - cb["pe"], "Δ PI": x["pi"] - cb["pi"], "Δ CEA": x["cea"] - cb["cea"],
                     "Δ CEA % PR": (x["cea"] - cb["cea"]) / pr if has_pr(pr) else float("nan")})
    tcr = pd.DataFrame(rows)
    if not has_pr(pr):
        tcr = tcr.drop(columns=["Δ CEA % PR"])
    st.dataframe(tcr.style.format({c: (pc if "%" in c else f3) for c in tcr.columns if c not in ("Cenário", "Ano")}),
                 hide_index=True, width="stretch")
    st.markdown("**Simulação de capital: base × estresse**")
    ids = [r["sc"]["id"] for r in R]
    rmap = {r["sc"]["id"]: r for r in R}
    dflt = max(ids, key=lambda i: crp["cen"][i]["cea"] - cb["cea"])
    sel = st.selectbox("Cenário de estresse", ids, index=ids.index(dflt), key="cr_fig_sc",
                       format_func=lambda i: f"{rmap[i]['sc']['nome']} ({YEARS[rmap[i]['yi']]})")
    nome_sel = f"{rmap[sel]['sc']['nome']} ({YEARS[rmap[sel]['yi']]})"
    figc = fig_capital(crp, sel, nome_sel, mono=False)
    st.pyplot(figc, width="stretch")
    bufc, bufm = io.BytesIO(), io.BytesIO()
    figc.savefig(bufc, format="png", dpi=220, bbox_inches="tight")
    fig_capital(crp, sel, nome_sel, mono=True).savefig(bufm, format="png", dpi=300, bbox_inches="tight")
    g1, g2, _ = st.columns([1, 1, 2])
    g1.download_button("Baixar figura (PNG, cor)", bufc.getvalue(), f"capital_{sel}.png", "image/png", width="stretch")
    g2.download_button("Baixar figura (PNG, P&B)", bufm.getvalue(), f"capital_{sel}_pb.png", "image/png", width="stretch")
    wid = max(R, key=lambda r: crp["cen"][r["sc"]["id"]]["cea"])["sc"]
    xw = crp["cen"][wid["id"]]
    fig = go.Figure()
    for nm_, d_, col, dash in [("Base", cb, GREY, "solid"), (wid["curto"], xw, RED, "solid")]:
        L = np.arange(len(d_["dist"])) * crp["L0"]
        fig.add_trace(go.Scatter(x=L, y=np.cumsum(d_["dist"]), name=f"{nm_}: distribuição acumulada", line=dict(color=col, dash=dash)))
        fig.add_vline(x=d_["quantil"], line=dict(color=col, dash="dot"))
    fig.update_layout(title=f"Distribuição acumulada da perda – base × {wid['curto']} (linhas pontilhadas: quantil de "
                            f"{100 * cpar.conf:.2f}%)".replace(".", ","), xaxis_title="Perda (R$ mi)", yaxis_title="Probabilidade acumulada",
                      yaxis=dict(range=[0.9, 1.0005]), height=380, margin=dict(l=10, r=10, t=50, b=10), separators=",.",
                      legend=dict(orientation="h", y=-0.25))
    with st.expander("Distribuição acumulada (interativa)"):
        st.plotly_chart(fig, width="stretch")
    with st.expander("Fatores setoriais da carteira de base (μ, σ, α, β)"):
        ft = cb["fatores"].assign(fator=lambda d: d.fator.map(lambda x: SECTOR_NAME.get(x, x))).sort_values("mu", ascending=False)
        st.dataframe(ft.rename(columns={"fator": "Fator", "contratos": "Contratos", "mu": "μ (nº esperado de defaults)",
                                        "sigma": "σ", "alpha": "α = μ²/σ²", "beta": "β = σ²/μ", "pe": "PE (R$ mi)"})
                     .style.format(f3, subset=["μ (nº esperado de defaults)", "σ", "α = μ²/σ²", "β = σ²/μ", "PE (R$ mi)"]),
                     hide_index=True, width="stretch")
    st.caption("O ASRF (aba Cenários) mede o capital contrato a contrato, supondo carteira infinitamente granular. O CreditRisk+ mede "
               "a carteira inteira, captando concentração em nomes e setores; os dois são complementares.")

with tabs[2]:
    s = sector_table(out)
    st.subheader(f"{s.index[0]} concentra a maior perda incremental")
    st.dataframe(s.style.format(f3).background_gradient(cmap="Reds", subset=[c for c in s.columns if c != "EAD"]),
                 width="stretch")

with tabs[3]:
    st.subheader(f"Contratos mais afetados em {W['sc']['nome']}, {YEARS[W['yi']]}")
    top = W["per"].assign(total=W["per"].delta_pe + W["per"].delta_capital).nlargest(15, "total")
    top = top.assign(setor=top.setor.map(SECTOR_NAME))[["id_contrato", "cliente", "setor", "rating", "ead", "delta_pd_pp",
                                                        "pd_base", "pd_estressada", "delta_pe", "delta_capital"]]
    st.dataframe(top.style.format({"ead": f3, "delta_pd_pp": f3, "pd_base": pc, "pd_estressada": pc, "delta_pe": f3,
                                   "delta_capital": f3}), hide_index=True, width="stretch")

with tabs[4]:
    st.write("O CLIMACRED entrega a ΔPD da firma representativa do setor. A soma direta trata igual um rating A e um rating B; "
             "o Δz preserva a ordenação. As duas coincidem quando a PD do contrato é igual à PD de referência do setor.")
    a, d = ("other", "ev") if mode == "dz" else ("ev", "other")
    cmp = pd.DataFrame([{"Cenário": r["sc"]["nome"], "Ano": YEARS[r["yi"]], "Δ PE soma direta": r[a]["dpe"],
                         "Δ PE via Δz": r[d]["dpe"], "Δ capital soma direta": r[a]["dcap"], "Δ capital via Δz": r[d]["dcap"],
                         "Δ total soma direta": r[a]["dtot"], "Δ total via Δz": r[d]["dtot"],
                         "Δ total soma direta % PR": r[a]["dtot"] / pr, "Δ total via Δz % PR": r[d]["dtot"] / pr} for r in R])
    if not has_pr(pr):
        cmp = cmp.drop(columns=["Δ total soma direta % PR", "Δ total via Δz % PR"])
    st.dataframe(cmp.style.format({c: (pc if "%" in c else f3) for c in cmp.columns if c not in ("Cenário", "Ano")}),
                 hide_index=True, width="stretch")

with tabs[5]:
    c = out["portfolio"]
    nm = c[c.sec.isna()]
    H = lambda n: 38 + 35 * n  # altura que mostra a tabela inteira, sem rolagem interna

    # 1. A carteira carregada, em números
    st.subheader("Carteira carregada" + (" (exemplo fictício)" if cart_src == "ex" else ""))
    m = st.columns(5)
    m[0].metric("Contratos", f"{len(c):,}".replace(",", "."))
    m[1].metric("EAD (R$ mi)", f3(B["ead"]))
    m[2].metric("PD média (pond. EAD)", pc(B["pdw"]))
    m[3].metric("Provisão (R$ mi)", f3(c.provisao.sum()))
    m[4].metric("EAD com setor mapeado", pc(1 - nm.ead.sum() / B["ead"]))
    if len(nm):
        st.warning(f"{len(nm)} contratos sem setor mapeado (EAD R$ {f3(nm.ead.sum())} mi) ficam sem choque. "
                   "Corrija o CNAE ou preencha a coluna setor_ngfs.")
        st.dataframe(nm[["id_contrato", "cliente", "cnae", "setor_ngfs", "ead"]], hide_index=True, width="stretch")

    # 2. Composição por setor
    comp = (c.assign(setor=c.sec.map(SECTOR_NAME).fillna("Sem mapeamento"))
            .groupby("setor").agg(contratos=("id_contrato", "size"), ead=("ead", "sum"),
                                  pd_media=("pdb", lambda s: (s * c.loc[s.index, "ead"]).sum() / c.loc[s.index, "ead"].sum()))
            .sort_values("ead"))
    fig = go.Figure(go.Bar(x=comp.ead, y=comp.index, orientation="h", marker_color=SLATE,
                           text=[f3(v) for v in comp.ead], textposition="outside", cliponaxis=False,
                           customdata=comp[["contratos", "pd_media"]].to_numpy(),
                           hovertemplate="%{y}<br>EAD R$ %{x:,.3f} mi<br>%{customdata[0]} contratos<br>PD média %{customdata[1]:.3%}<extra></extra>"))
    fig.update_layout(title="EAD por setor CLIMACRED (R$ mi)", height=max(320, 28 * len(comp) + 80),
                      margin=dict(l=10, r=60, t=50, b=10), separators=",.", xaxis=dict(showgrid=False, showticklabels=False))
    st.plotly_chart(fig, width="stretch")

    # 3. Layout do arquivo de entrada
    st.subheader("Como montar o arquivo da carteira")
    st.markdown("Um contrato por linha, em **CSV** (vírgula ou ponto e vírgula) ou **XLSX**. Decimal com ponto ou vírgula; "
                "taxas em decimal (0,012 = 1,200%). ● obrigatória · ○ opcional.")
    lay = pd.DataFrame(INPUT_LAYOUT, columns=["Coluna", "Tipo", "Descrição", "Exemplo"])
    lay["Coluna"] = [("**" if "opcional" not in t else "") + col for col, t in zip(lay.Coluna, lay.Tipo)]
    lay["Coluna"] = lay["Coluna"].str.replace("**", "● ", regex=False).str.replace(r"^(?!●)", "○ ", regex=True)
    st.dataframe(lay, hide_index=True, width="stretch", height=H(len(lay)), column_config={
        "Coluna": st.column_config.TextColumn(width="small", help="● obrigatória · ○ opcional"),
        "Tipo": st.column_config.TextColumn(width="small"),
        "Descrição": st.column_config.TextColumn(width="large"),
        "Exemplo": st.column_config.TextColumn(width="medium")})
    modelo = ",".join(col for col, *_ in INPUT_LAYOUT) + "\n" + ",".join(ex for *_, ex in INPUT_LAYOUT) + "\n"
    b1, b2, _ = st.columns([1, 1, 2])
    b1.download_button("Baixar modelo em branco (CSV)", modelo.encode("utf-8"), "modelo_carteira.csv", "text/csv", width="stretch")
    b2.download_button("Baixar carteira de exemplo (CSV)", (DATA / "carteira_exemplo.csv").read_bytes(),
                       "carteira_exemplo.csv", "text/csv", width="stretch")

    # 4. De-para e prévia, recolhidos
    with st.expander("De-para CNAE → setor CLIMACRED"):
        st.caption("A classe de 4 dígitos tem precedência sobre a divisão. A coluna setor_ngfs, se preenchida, prevalece sobre o CNAE "
                   "— use-a para geradoras (Hydro electric, Wind, PV, Gas Fired) e usinas de etanol (Biofuels).")
        mp = pd.DataFrame([(a_, b_, SECTOR_NAME[b_]) for a_, b_ in MAP_ROWS], columns=["CNAE", "Setor CLIMACRED", "Descrição"])
        st.dataframe(mp, hide_index=True, width="stretch", height=H(len(mp)),
                     column_config={"CNAE": st.column_config.TextColumn(width="medium")})
    with st.expander("Prévia da carteira (primeiras 20 linhas)"):
        pv = c.head(20).assign(setor=lambda d: d.sec.map(SECTOR_NAME))[
            ["id_contrato", "cliente", "cnae", "setor", "pais", "uf", "rating", "pd_12m", "lgd", "ead", "prazo_anos", "provisao"]]
        st.dataframe(pv, hide_index=True, width="stretch", height=H(len(pv)), column_config={
            "pd_12m": st.column_config.NumberColumn("PD 12m", format="percent"),
            "lgd": st.column_config.NumberColumn("LGD", format="percent"),
            "ead": st.column_config.NumberColumn("EAD (R$ mi)", format="%.3f"),
            "prazo_anos": st.column_config.NumberColumn("Prazo (anos)", format="%.1f"),
            "provisao": st.column_config.NumberColumn("Provisão (R$ mi)", format="%.3f")})

with tabs[6]:
    a1, a2 = st.columns(2)
    sc_sel = a1.selectbox("Cenário", [s["id"] for s in scenarios], format_func=lambda i: next(s["nome"] for s in scenarios if s["id"] == i))
    pa_opts = sorted(dpd[dpd.cenario == sc_sel].pais.unique())
    pa_sel = a2.selectbox("País/região", pa_opts, index=pa_opts.index(fb) if fb in pa_opts else 0)
    tab = dpd[(dpd.cenario == sc_sel) & (dpd.pais == pa_sel)].pivot_table(index="setor", columns="ano", values="delta_pd_pp")
    tab.index = tab.index.map(lambda x: f"{SECTOR_NAME.get(x, x)} ({x})")
    bl = data["base"][(data["base"].cenario == sc_sel) & (data["base"].pais == pa_sel)].set_index("ano")["baseline_pd_pp"]
    if len(bl):
        st.caption("PD de linha de base do CLIMACRED (p.p.), igual para todos os setores: "
                   + "; ".join(f"{a}: {f3(v)}" for a, v in bl.items()))
    st.dataframe(tab.style.format(f3), width="stretch")
    if dpd_src == "ill":
        st.caption("Valores ilustrativos (p.p. sobre a linha de base). Âncoras publicadas: "
                   + "; ".join(f"{SECTOR_NAME[s]} {y} em {c_}: {t}" for (c_, s, y), t in ANCHORS.items())
                   + ". Os demais são premissas a substituir pela série do IIASA.")
    with st.expander("Como montar o CSV a partir do NGFS Scenario Explorer"):
        st.markdown("1. Acesse https://data.ece.iiasa.ac.at/ngfs-phase-5-short-term/#/downloads e entre como convidado (*Guest login*).\n"
                    "2. Baixe o pacote de dados no fim da página e extraia `CLIMACRED_IIASA_<data>.xlsx`.\n"
                    "3. Salve o arquivo em `data/ngfs/` (carregado automaticamente e fora do git) ou envie pela barra lateral.\n\n"
                    "Variáveis usadas: `pd_adjustment|<setor>` (ΔPD em p.p.) e `baseline_pd|<setor>` (PD de linha de base). "
                    "Formato longo alternativo:")
        st.code("cenario,pais,setor,ano,delta_pd_pp\nHWTP,Brasil,Agriculture,2030,1.536", language="text")

with tabs[7]:
    st.markdown((DATA.parent / "docs" / "metodologia.md").read_text(encoding="utf-8"))

with tabs[8]:
    md = report_text(out, cart_src, dpd_src)
    st.subheader("Artigo em PDF")
    st.caption("Relatório no formato de artigo: introdução, referencial teórico (Merton, Vasicek, CLIMACRED, cenários do NGFS), "
               "metodologia, dados, resultados com tabelas e figuras, discussão para o ICAAP e referências bibliográficas.")
    k1, k2 = st.columns(2)
    autor = k1.text_input("Autor", "Walter C. Neto")
    inst = k2.text_input("Instituição (opcional)", "")
    if st.button("Gerar artigo (PDF)", type="primary"):
        with st.spinner("Montando o artigo…"):
            try:
                st.session_state["artigo_pdf"] = build_article(out, data, cart_src, autor, inst)
            except Exception as e:  # noqa: BLE001
                st.error(f"Não foi possível gerar o PDF: {e}")
    if st.session_state.get("artigo_pdf"):
        st.download_button("Baixar artigo (PDF)", st.session_state["artigo_pdf"], "artigo_climacred.pdf", "application/pdf")
        st.caption("O PDF reflete os parâmetros do momento em que foi gerado; gere de novo após mudar entradas ou parâmetros.")
    st.divider()
    st.subheader("Resumo e exportações")
    st.markdown(md)
    d1, d2, d3 = st.columns(3)
    d1.download_button("Relatório (Markdown)", md.encode("utf-8"), "relatorio_climacred.md", "text/markdown")
    d2.download_button("Resultados completos (Excel)", to_excel(out, dpd, md), "resultados_climacred.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    d3.download_button("Resultados por contrato (CSV)", pd.concat([r["per"] for r in R]).to_csv(index=False).encode("utf-8"),
                       "resultados_contratos.csv", "text/csv")
