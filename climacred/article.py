"""Relatório em PDF no formato de artigo: teoria, método, resultados e referências.

Tipografia Times (STIX, distribuída com o matplotlib), monocromática, sem listagens de código.
"""
from __future__ import annotations

import datetime as dt
import io
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

from .config import SECTOR_NAME, YEARS  # noqa: E402
from .figures import fig_capital
from .report import (MODEL_LABEL, cap_model, capital_compare, f2, f3, has_pr, impact, model_base, model_delta, money, unit_for,
                     worst, worst_model)
from .report import pc2 as pc  # noqa: E402

# ---------------- tipografia ----------------
_FONT_DIR = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
_REG = False


def _fonts():
    global _REG
    if _REG:
        return
    for name, file in [("Serif", "STIXGeneral.ttf"), ("Serif-Bold", "STIXGeneralBol.ttf"),
                       ("Serif-Italic", "STIXGeneralItalic.ttf"), ("Serif-BoldItalic", "STIXGeneralBolIta.ttf")]:
        pdfmetrics.registerFont(TTFont(name, os.path.join(_FONT_DIR, file)))
    pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-Bold", italic="Serif-Italic", boldItalic="Serif-BoldItalic")
    _REG = True


def _styles():
    base = dict(fontName="Serif", fontSize=10.5, leading=14.2)
    return {
        "title": ParagraphStyle("title", fontName="Serif-Bold", fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=8),
        "author": ParagraphStyle("author", fontName="Serif", fontSize=11, leading=14, alignment=TA_CENTER),
        "meta": ParagraphStyle("meta", fontName="Serif-Italic", fontSize=9.5, leading=12, alignment=TA_CENTER, spaceAfter=14),
        "abs_h": ParagraphStyle("abs_h", fontName="Serif-Bold", fontSize=10, leading=13, alignment=TA_CENTER, spaceAfter=4),
        "abs": ParagraphStyle("abs", fontName="Serif", fontSize=9.8, leading=13, alignment=TA_JUSTIFY, leftIndent=1.2 * cm,
                              rightIndent=1.2 * cm, spaceAfter=6),
        "kw": ParagraphStyle("kw", fontName="Serif", fontSize=9.5, leading=12.5, leftIndent=1.2 * cm, rightIndent=1.2 * cm,
                             spaceAfter=16),
        "h1": ParagraphStyle("h1", fontName="Serif-Bold", fontSize=12, leading=15, spaceBefore=12, spaceAfter=6, keepWithNext=1),
        "h2": ParagraphStyle("h2", fontName="Serif-BoldItalic", fontSize=10.8, leading=14, spaceBefore=8, spaceAfter=4, keepWithNext=1),
        "body": ParagraphStyle("body", alignment=TA_JUSTIFY, firstLineIndent=0.6 * cm, spaceAfter=5, **base),
        "body0": ParagraphStyle("body0", alignment=TA_JUSTIFY, spaceAfter=5, **base),
        "cap": ParagraphStyle("cap", fontName="Serif", fontSize=9.3, leading=11.8, alignment=TA_JUSTIFY, spaceBefore=3, spaceAfter=10),
        "cell": ParagraphStyle("cell", fontName="Serif", fontSize=8.8, leading=10.6),
        "cellr": ParagraphStyle("cellr", fontName="Serif", fontSize=8.8, leading=10.6, alignment=2),
        "ref": ParagraphStyle("ref", fontName="Serif", fontSize=9.6, leading=12.4, leftIndent=0.6 * cm, firstLineIndent=-0.6 * cm,
                              spaceAfter=4, alignment=TA_JUSTIFY),
        "note": ParagraphStyle("note", fontName="Serif-Italic", fontSize=8.8, leading=11, spaceAfter=8),
    }


# ---------------- equações e figuras (matplotlib, monocromático) ----------------
plt.rcParams.update({"mathtext.fontset": "stix", "font.family": "STIXGeneral", "font.size": 10,
                     "axes.edgecolor": "black", "axes.linewidth": 0.6, "savefig.dpi": 300})


_EQ_DIR = os.path.join(os.path.dirname(__file__), "assets", "eq")
try:
    import json as _json
    _EQ_MAN = _json.load(open(os.path.join(_EQ_DIR, "manifest.json"), encoding="utf-8"))
except Exception:  # noqa: BLE001
    _EQ_MAN = {}


def _eq(tex: str = "", width_cm: float = 13.0, height_cm: float = 0.95, number: int | None = None, key: str | None = None,
        max_w: float = 14.3) -> Table:
    """Equação numerada. Usa a imagem pré-renderizada em LaTeX (assets/eq) quando existe; senão, mathtext."""
    num = Paragraph(f"({number})" if number else "", ParagraphStyle("n", fontName="Serif", fontSize=10.5, alignment=2))
    if key and key in _EQ_MAN and os.path.exists(os.path.join(_EQ_DIR, f"{key}.png")):
        w, h = _EQ_MAN[key]["w_cm"], _EQ_MAN[key]["h_cm"]
        f = min(1.0, max_w / w) * 0.92
        img = Image(os.path.join(_EQ_DIR, f"{key}.png"), width=w * f * cm, height=h * f * cm)
    else:
        fig = plt.figure(figsize=(width_cm / 2.54, height_cm / 2.54))
        fig.text(0.5, 0.5, f"${tex}$", ha="center", va="center", fontsize=11.5)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True)
        plt.close(fig)
        buf.seek(0)
        img = Image(buf, width=width_cm * cm, height=height_cm * cm)
    t = Table([[img, num]], colWidths=[14.6 * cm, 1.4 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "CENTER"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def _fig_to_image(fig, width_cm: float) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    w, h = fig.get_size_inches()
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width_cm * cm, height=width_cm * cm * h / w)


def _br(ax):
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f2(v)))


_STYLES = ["-", "--", "-.", ":", (0, (5, 1, 1, 1, 1, 1))]
_MARK = ["o", "s", "^", "D", "v"]


def _fig_trajectory(out):
    y = out["yearly"][out["yearly"].modo == out["params"].mode]
    dv, un, _ = unit_for(y.dpe)
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for i, r in enumerate(out["results"]):
        s = y[y.cenario == r["sc"]["id"]]
        ax.plot(s.ano, s.dpe / dv, color="black", ls=_STYLES[i % 5], marker=_MARK[i % 5], ms=3.5, lw=1.1, label=r["sc"]["curto"])
    ax.set_ylabel(f"Δ perda esperada (R$ {un})")
    ax.set_xticks(YEARS)
    ax.grid(axis="y", color="0.85", lw=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    _br(ax)
    ax.legend(frameon=False, ncol=min(5, len(out["results"])), loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=9)
    return fig


def _fig_bars(out):
    R, pr = out["results"], out["params"].pr
    lab = [f"{r['sc']['curto']} ({YEARS[r['yi']]})" for r in R][::-1]
    if has_pr(pr):
        dv, suf, xl = pr / 100, "%", "% do Patrimônio de Referência"
    else:
        dv, un, _ = unit_for([r["ev"]["dtot"] for r in R])
        suf, xl = (" bi" if dv > 1 else " mi"), f"R$ {un}"
    pe = [r["ev"]["dpe"] / dv for r in R][::-1]
    cap = [r["ev"]["dcap"] / dv for r in R][::-1]
    fig, ax = plt.subplots(figsize=(6.4, 0.45 * len(R) + 1.0))
    ax.barh(lab, pe, color="0.25", label="Perda esperada")
    ax.barh(lab, cap, left=pe, color="white", edgecolor="black", hatch="////", lw=0.6, label="Capital econômico (ASRF)")
    for i, (a, b) in enumerate(zip(pe, cap)):
        ax.text(a + b + 0.01 * max(np.add(pe, cap)), i, f"{f2(a + b)}{suf}", va="center", fontsize=9)
    ax.set_xlabel(xl)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    ax.set_xlim(0, max(1e-6, max(np.add(pe, cap))) * 1.18)
    return fig


def _fig_sectors(out):
    c = out["portfolio"]
    short = {k: v.split(" (")[0] for k, v in SECTOR_NAME.items()}
    s = c.assign(setor=c.sec.map(short).fillna("Sem mapeamento")).groupby("setor")["ead"].sum().sort_values()
    s = s.tail(15)
    dv, un, _ = unit_for(s.values)
    s = s / dv
    fig, ax = plt.subplots(figsize=(6.4, 0.3 * len(s) + 0.8))
    ax.barh(s.index, s.values, color="0.45")
    ax.set_xlabel(f"EAD (R$ {un})")
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f2(v)))
    ax.tick_params(axis="y", labelsize=9.5)
    return fig


def _ann(pd_, p):
    """PD de referência no horizonte do Δz (anualizada se p.horizon > 1), limitada a (1e-6, 0,9999)."""
    from .engine import annualize
    return float(min(max(annualize(min(max(pd_, 1e-6), 0.9999), getattr(p, "horizon", 1.0)), 1e-6), 0.9999))


def _asrf_parts(pd_, lgd, m, floor=0.0003, scale=1.0):
    from scipy.stats import norm
    p = min(max(pd_, floor), 0.9999)
    e = (1 - np.exp(-50 * p)) / (1 - np.exp(-50))
    R = 0.12 * e + 0.24 * (1 - e)
    b = (0.11852 - 0.05478 * np.log(p)) ** 2
    K = max(0.0, (lgd * norm.cdf((norm.ppf(p) + np.sqrt(R) * norm.ppf(0.999)) / np.sqrt(1 - R)) - p * lgd)
            * (1 + (m - 2.5) * b) / (1 - 1.5 * b)) * scale
    return R, b, K


def _fig_crplus(crp, wid, wname):
    cb, xw, L0 = crp["base"], crp["cen"][wid], crp["L0"]
    qmax = max(cb["quantil"], xw["quantil"]) * 1.25
    dv, un, _ = unit_for([qmax])
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    edges = np.linspace(0, qmax, 81)
    for d, ls, lab in [(cb, "-", "Base"), (xw, "--", wname)]:
        x = np.arange(len(d["dist"])) * L0
        h, _ = np.histogram(x, bins=edges, weights=d["dist"])
        ax.step(edges[:-1] / dv, h / np.diff(edges), where="post", color="black", ls=ls, lw=1.1, label=lab)
        ax.axvline(d["quantil"] / dv, color="black", ls=":", lw=0.8)
    ax.set_xlabel(f"Perda (R$ {un})")
    ax.set_ylabel("Densidade")
    ax.set_yticks([])
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f2(v)))
    ax.legend(frameon=False, fontsize=9)
    return fig


# ---------------- tabelas ----------------
def _mb(x_mi) -> str:
    """Valor em R$ milhões -> '1,07 bi' ou '95,09 mi'."""
    if x_mi is None or pd.isna(x_mi):
        return "–"
    return f"{f2(x_mi / 1000)} bi" if abs(x_mi) >= 1000 else f"{f2(x_mi)} mi"


def _table(rows, header, widths, st, align_right_from=1, font=8.8):
    data = [[Paragraph(f"<b>{h}</b>", st["cell"] if i < align_right_from else st["cellr"]) for i, h in enumerate(header)]]
    for r in rows:
        data.append([Paragraph(str(v), st["cell"] if i < align_right_from else st["cellr"]) for i, v in enumerate(r)])
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _caption(st, txt):
    return Paragraph(txt, st["cap"])


# ---------------- referências ----------------
REFERENCES = [
    "BANCO CENTRAL DO BRASIL. <i>Relatório de Estabilidade Financeira</i>. Brasília: BCB, out. 2022 (risco climático de transição; seca extrema), abr. 2023 (chuvas intensas), out. 2024 (enchentes no Rio Grande do Sul; risco de transição) e nov. 2025 (El Niño).",
    "BARÓN, A.; DASSATTI, C.; LAVAGNA, G.; MONTAÑEZ-ENRÍQUEZ, R. Assessing climate risks in Uruguay’s banks using NGFS short-term scenarios. <i>Latin American Journal of Central Banking</i>, v. 7, 100198, 2026.",
    "BASEL COMMITTEE ON BANKING SUPERVISION. <i>CRE31 – IRB approach: risk weight functions</i>. Basel Framework. Basileia: BIS.",
    "BATTISTON, S.; MANDEL, A.; MONASTEROLO, I.; SCHÜTZE, F.; VISENTIN, G. A climate stress-test of the financial system. <i>Nature Climate Change</i>, v. 7, p. 283–288, 2017.",
    "BATTISTON, S.; MANDEL, A.; MONASTEROLO, I.; RONCORONI, A. <i>Climate credit risk and corporate valuation</i>. CEPR Discussion Paper DP20239, 2023.",
    "BATTISTON, S. et al. <i>NGFS Phase 5 Short Term Scenarios</i>, versão 1.1. Zenodo, 2025. DOI 10.5281/zenodo.15790097. Dados: NGFS Scenario Explorer, IIASA.",
    "BOLTON, P.; DESPRES, M.; PEREIRA DA SILVA, L. A.; SAMAMA, F.; SVARTZMAN, R. <i>The green swan: central banking and financial stability in the age of climate change</i>. Basileia: BIS; Paris: Banque de France, 2020.",
    "CARNEY, M. <i>Breaking the tragedy of the horizon – climate change and financial stability</i>. Discurso, Lloyd’s of London, 29 set. 2015.",
    "CREDIT SUISSE FIRST BOSTON. <i>CreditRisk+: a credit risk management framework</i>. Londres: CSFB, 1997.",
    "CONSELHO MONETÁRIO NACIONAL. <i>Resolução n. 4.557, de 23 de fevereiro de 2017</i>, com a redação dada pela <i>Resolução CMN n. 4.943, de 15 de setembro de 2021</i>.",
    "BANCO CENTRAL DO BRASIL. <i>Resolução BCB n. 303, de 16 de março de 2023</i>. Procedimentos para o cálculo da parcela RWA<sub>CIRB</sub> mediante abordagens IRB.",
    "CONSELHO MONETÁRIO NACIONAL. <i>Resolução CMN n. 4.966, de 25 de novembro de 2021</i>.",
    "GORDY, M. B. A risk-factor model foundation for ratings-based bank capital rules. <i>Journal of Financial Intermediation</i>, v. 12, n. 3, p. 199–232, 2003.",
    "MANDEL, A.; BATTISTON, S.; MONASTEROLO, I. Mapping global financial risks under climate change. <i>Nature Climate Change</i>, v. 15, p. 329–334, 2025.",
    "MERTON, R. C. On the pricing of corporate debt: the risk structure of interest rates. <i>Journal of Finance</i>, v. 29, n. 2, p. 449–470, 1974.",
    "NETWORK FOR GREENING THE FINANCIAL SYSTEM (NGFS). <i>NGFS Short-Term Scenarios for central banks and supervisors</i>. Paris: NGFS, maio 2025.",
    "NETWORK FOR GREENING THE FINANCIAL SYSTEM (NGFS). <i>NGFS long-term scenarios for central banks and supervisors – Phase V</i>. Paris: NGFS, nov. 2024.",
    "VASICEK, O. The distribution of loan portfolio value. <i>Risk</i>, v. 15, n. 12, p. 160–162, 2002.",
]

REF_TXT = {"ngfs": "a PD de linha de base do próprio CLIMACRED (<i>baseline_pd</i>)",
           "ngfs+cart": "a PD de linha de base do CLIMACRED, com a média da carteira onde não há série",
           "cart": "a PD média da carteira no setor, ponderada pela EAD", "fix": "uma PD de referência única informada"}


# ---------------- documento ----------------
def build_article(out: dict, data: dict, cart_src: str, author: str = "", institution: str = "") -> bytes:
    _fonts()
    st = _styles()
    p, B, R = out["params"], out["base"], out["results"]
    if not R:
        raise ValueError("nenhum cenário com série para os países da carteira")
    W = worst(out)
    main = [r for r in R if r["ev"]["cobertura"] >= 0.5] or R
    best = min(main, key=lambda r: r["ev"]["dtot"])
    crp0 = out.get("crp")
    MDL = cap_model(out)
    MLAB, OTH = MODEL_LABEL[MDL], ("crp" if MDL == "asrf" else "asrf")
    WM = worst_model(out)
    DWM = model_delta(out, WM)
    bestm = min(main, key=lambda r: model_delta(out, r)["dtot"])
    c = out["portfolio"]
    pr = p.pr
    ill = data.get("fonte") == "ilustrativa"
    ref_used = R[0].get("ref_used", "cart")
    today = dt.date.today().strftime("%d/%m/%Y")
    metodo = (f"deslocamento da variável latente (Δz), tendo como referência {REF_TXT.get(ref_used, 'uma PD de referência')}"
              if p.mode == "dz" else "soma direta da ΔPD, em pontos percentuais, à PD de cada contrato")
    base_bra = data.get("base", pd.DataFrame())
    base_bra = base_bra[(base_bra.pais == p.fallback_country)] if len(base_bra) else base_bra
    bl_txt = ""
    if len(base_bra):
        b = base_bra.groupby("ano")["baseline_pd_pp"].mean()
        bl_txt = (f" Na série utilizada, a PD de linha de base do CLIMACRED para {p.fallback_country} é a mesma para todos os setores "
                  f"e varia entre {f3(b.min())}% e {f3(b.max())}% no período 2024–2030.")

    story = []
    A = story.append
    A(Paragraph("Estresse climático em carteiras de crédito corporativo com os cenários de curto prazo do NGFS: "
                "aplicação da ΔPD do modelo CLIMACRED", st["title"]))
    if author:
        A(Paragraph(author, st["author"]))
    if institution:
        A(Paragraph(institution, st["author"]))
    A(Paragraph(f"Relatório técnico gerado pelo ClimaCred em {today}"
                + (" · carteira de exemplo, fictícia" if cart_src == "ex" else "")
                + (" · ΔPD ilustrativa" if ill else f" · série {data.get('fonte', '')}"), st["meta"]))

    A(Paragraph("Resumo", st["abs_h"]))
    A(Paragraph(
        f"Este relatório avalia o efeito de cenários climáticos de curto prazo sobre a perda esperada e o capital de uma carteira de "
        f"crédito a pessoas jurídicas com {len(c)} contratos e exposição de {money(B['ead'])}. A variação da probabilidade de "
        f"inadimplência por setor (ΔPD) vem do modelo estrutural de crédito CLIMACRED, componente dos cenários de curto prazo do "
        f"<i>Network for Greening the Financial System</i> (NGFS) publicados em 2025, e é transferida a cada contrato por {metodo}. "
        + ("O capital econômico é calculado por dois modelos: a fórmula ASRF do IRB, adotada pelo Banco Central do Brasil, e o "
           "CreditRisk+, com calibragem parametrizável; em ambos, CEA = PE + PI. " if crp0 else "O capital é medido pela fórmula ASRF do IRB. ")
        + f"Pelo {MLAB}, no cenário mais severo, {WM['sc']['nome']} ({YEARS[WM['yi']]}), a perda esperada aumenta {money(DWM['dpe'])} "
        f"e a perda inesperada {money(DWM['dpi'])}, "
        + (f"o equivalente a {impact(DWM['dtot'], pr, True)} considerado. " if has_pr(pr) else f"num total de {money(DWM['dtot'])}. ")
        + (f"Pelo {MODEL_LABEL[OTH]}, o aumento do CEA no mesmo cenário é de {impact(model_delta(out, WM, OTH)['dtot'], pr)}. "
           if crp0 else "")
        + f"O cenário mais brando, {bestm['sc']['nome']}, resulta em {impact(model_delta(out, bestm)['dtot'], pr)}. "
        "Os resultados são sensíveis à forma de transferir a ΔPD setorial ao contrato e à calibragem do modelo de capital, pontos discutidos "
        f"em detalhe, e o procedimento é proposto como insumo ao programa de testes de estresse e ao ICAAP.", st["abs"]))
    A(Paragraph("<b>Palavras-chave:</b> risco climático; probabilidade de inadimplência; teste de estresse; NGFS; CLIMACRED; ICAAP.",
                st["kw"]))

    # 1 Introdução
    A(Paragraph("1. Introdução", st["h1"]))
    A(Paragraph(
        "A mudança climática afeta o sistema financeiro por dois canais: o risco físico, associado a eventos extremos e a alterações "
        "graduais do clima, e o risco de transição, associado a mudanças de política, tecnologia e preferências rumo a uma economia de "
        "baixo carbono (CARNEY, 2015; BOLTON et al., 2020). Ambos se manifestam no crédito pela deterioração da capacidade de pagamento "
        "dos tomadores e pela perda de valor de seus ativos.", st["body"]))
    A(Paragraph(
        "No Brasil, a Resolução CMN n. 4.943/2021 alterou a Resolução CMN n. 4.557/2017 e incluiu o risco climático na estrutura de "
        "gerenciamento de riscos; para instituições dos segmentos S1 e S2, o programa de testes de estresse passou a considerar hipóteses "
        "de mudanças em padrões climáticos e de transição para uma economia de baixo carbono. O Banco Central tem publicado exercícios "
        "próprios de estresse climático em seus Relatórios de Estabilidade Financeira, cobrindo seca extrema, chuvas intensas, as "
        "enchentes do Rio Grande do Sul e o El Niño (BANCO CENTRAL DO BRASIL, 2022–2025).", st["body"]))
    A(Paragraph(
        "A lacuna prática é a passagem das variáveis de cenário para os parâmetros de risco de crédito. Os cenários de longo prazo do "
        "NGFS entregam trajetórias de PIB, preço de carbono e emissões, mas não probabilidades de inadimplência. Os cenários de curto "
        "prazo, publicados em maio de 2025, avançam nesse ponto: incorporam o modelo CLIMACRED, que entrega diretamente a ΔPD por setor, "
        "país e ano (NGFS, 2025; BATTISTON et al., 2025). Este relatório descreve como essa ΔPD é aplicada a uma carteira corporativa "
        "e apresenta o impacto resultante em perdas e capital.", st["body"]))

    # 2 Referencial teórico
    A(Paragraph("2. Referencial teórico", st["h1"]))
    A(Paragraph("2.1 Modelos estruturais de crédito", st["h2"]))
    A(Paragraph(
        "Em Merton (1974), a firma entra em inadimplência quando o valor de seus ativos fica abaixo do valor da dívida no vencimento. "
        "Com ativos log-normais, a probabilidade de inadimplência é a probabilidade de uma variável latente normal padrão ficar abaixo de "
        "um limiar. Vasicek (2002) estende a ideia a uma carteira com um fator sistêmico comum, e Gordy (2003) mostra que, numa carteira "
        "granular, o capital para perdas inesperadas depende apenas da PD, da LGD e da correlação com esse fator, o que fundamenta a "
        "fórmula ASRF de Basileia. Para um contrato com PD de base PD<sub>0</sub>, um choque que aproxima a firma do limiar em Δz "
        "desvios-padrão produz", st["body0"]))
    A(_eq(key="pd_shift", number=1))
    A(Paragraph(
        "em que Φ é a distribuição normal padrão acumulada. A forma (1) mantém a PD entre zero e um, preserva a ordenação de risco entre "
        "contratos e permite somar choques de origens diferentes na mesma unidade.", st["body0"]))

    A(Paragraph("2.2 O modelo CLIMACRED", st["h2"]))
    A(Paragraph(
        "O CLIMACRED é um modelo de risco de crédito micro-fundamentado que avalia títulos de dívida e ações de firmas e o custo de "
        "capital condicionalmente a cenários climáticos (BATTISTON et al., 2023; MANDEL; BATTISTON; MONASTEROLO, 2025). Ele descende "
        "da linha de testes de estresse climático do sistema financeiro de Battiston et al. (2017). O modelo simula o balanço e o "
        "resultado de uma firma representativa de cada setor e país. No risco de transição, os ativos são afetados por encalhe "
        "(<i>stranding</i>) e a queda de produção reduz o fluxo de caixa; no risco físico, a destruição de capital produtivo reduz ativos "
        "ou aumenta a dívida pela reconstrução, e a interrupção de negócios reduz o fluxo de caixa.", st["body"]))
    A(Paragraph(
        "Dois elementos distinguem o modelo. Primeiro, o risco nasce da mudança de expectativas do mercado sobre o cenário: quando o "
        "mercado passa a acreditar num cenário, ativos e fluxos de caixa futuros são reprecificados de imediato. Segundo, há duas "
        "fontes de incerteza, a ambiguidade sobre qual cenário prevalecerá e os choques de produtividade da firma dentro de cada "
        "cenário. A saída usada neste relatório é", st["body0"]))
    A(_eq(key="dpd_def", number=2))
    A(Paragraph(
        "para o setor <i>k</i>, o país <i>j</i>, o cenário <i>c</i> e o ano <i>t</i>, em pontos percentuais. Na base do IIASA, as "
        "variáveis correspondentes são <i>pd_adjustment</i> e <i>baseline_pd</i>." + bl_txt, st["body0"]))

    A(Paragraph("2.3 Os cenários de curto prazo do NGFS", st["h2"]))
    A(Paragraph(
        "Os cenários de curto prazo cobrem 2024–2030 e integram três modelos: o GEM-E3, de equilíbrio geral com 50 setores e 46 países; "
        "o EIRIN, macrofinanceiro; e o CLIMACRED, de crédito. Os choques físicos combinam eventos simultâneos, como seca, onda de calor e "
        "incêndio (eventos secos) ou enchente e tempestade (eventos úmidos), e se propagam entre regiões pelo comércio e pelo sistema "
        "financeiro (NGFS, 2025). A Tabela 1 resume os cenários com série para a carteira analisada.", st["body"]))
    desc = {
        "HWTP": "Transição ordenada e tecnológica; receita de carbono reinvestida em subsídios verdes.",
        "SWUC": "Mudança abrupta de preferências e de política climática; transição tardia e desordenada.",
        "DIRE": "Economias avançadas fazem a transição; demais regiões sofrem desastres sucessivos (América do Sul: seco em 2026, úmido em 2029).",
        "DAPS_SAM": "Sem nova política climática; sequência de desastres na América do Sul (seco em 2026, úmido em 2027).",
        "DAPS_NAM": "Sem nova política climática; desastres na América do Norte (afeta só exposições na região).",
    }
    A(KeepTogether([_caption(st, "<b>Tabela 1.</b> Cenários de curto prazo do NGFS utilizados."),
                    _table([[r["sc"]["nome"], r["sc"].get("tipo", ""), desc.get(r["sc"]["id"], "")] for r in R],
                           ["Cenário", "Natureza", "Narrativa"], [4.6, 3.4, 8.0], st, align_right_from=9)]))

    A(Paragraph("2.4 Aplicações relacionadas", st["h2"]))
    A(Paragraph(
        "Barón et al. (2026) aplicaram a ΔPD do CLIMACRED para a América do Sul à carteira corporativa dos bancos uruguaios, somando a "
        "ΔPD setorial à PD de base e medindo a perda esperada incremental como fração do capital regulatório. No cenário de desastres, "
        "a PD do agronegócio passou de 2,620% para 28,390%. O presente relatório segue o mesmo encadeamento, com três diferenças: usa a "
        "série específica do Brasil, transfere a ΔPD ao contrato por deslocamento da variável latente e mede também o capital para "
        "perdas inesperadas.", st["body"]))

    A(Paragraph("2.5 O modelo CreditRisk+", st["h2"]))
    A(Paragraph(
        "O CreditRisk+ (CREDIT SUISSE FIRST BOSTON, 1997) é um modelo atuarial de perdas de carteira. Cada contrato <i>i</i> entra "
        "em inadimplência segundo uma Poisson de intensidade PD<sub>i</sub>, modulada por fatores de risco setoriais X<sub>k</sub> "
        "independentes, com distribuição gama de média um. A dependência entre inadimplências surge apenas pelos fatores comuns:",
        st["body0"]))
    A(_eq(key="crp_poisson", number=3))
    A(Paragraph(
        "em que w<sub>i0</sub> é o peso idiossincrático e w<sub>ik</sub> o peso do fator <i>k</i>. Agrupando as perdas em múltiplos "
        "de uma unidade L<sub>0</sub>, com ν<sub>i</sub> = LGD<sub>i</sub>·EAD<sub>i</sub>/L<sub>0</sub> arredondado, a função "
        "geradora de probabilidades da perda da carteira tem forma fechada:", st["body0"]))
    A(_eq(key="crp_pgf", number=4))
    A(Paragraph("com os parâmetros de cada fator dados por", st["body0"]))
    A(_eq(key="crp_par", number=5))
    A(Paragraph(
        "em que μ<sub>k</sub> é o número esperado de inadimplências do fator, σ<sub>k</sub> seu desvio-padrão e λ a volatilidade "
        "relativa (premissa de calibragem). A distribuição de perdas sai da expansão de G(z), pela recursão de Panjer ou, "
        "de forma equivalente e mais rápida, avaliando G na circunferência unitária com a transformada rápida de Fourier. O capital "
        "econômico alocado é o quantil da perda no nível de confiança <i>q</i>, decomposto em perda esperada e perda inesperada:",
        st["body0"]))
    A(_eq(key="crp_cea", number=6))
    A(Paragraph(
        "No estresse, as mesmas exposições são avaliadas com as PDs estressadas do cenário, o que produz CEA<sub>stress</sub> = "
        "PE<sub>stress</sub> + PI<sub>stress</sub>. Diferentemente do ASRF, que supõe carteira infinitamente granular e um único fator, o "
        "CreditRisk+ capta a concentração em nomes e em setores.", st["body"]))

    # 3 Metodologia
    A(Paragraph("3. Metodologia", st["h1"]))
    A(Paragraph("3.1 Mapeamento setorial", st["h2"]))
    A(Paragraph(
        "Cada contrato é associado a um setor do CLIMACRED a partir da classificação CNAE 2.0 do tomador: a classe de quatro dígitos tem "
        "precedência sobre a divisão de dois dígitos (por exemplo, as classes 1931 e 1932 vão para biocombustíveis), e um campo "
        "opcional permite indicar o setor diretamente, recurso útil para geradoras de energia, que o modelo distingue por fonte. "
        "Contratos sem série para o seu país recebem a série do país padrão; contratos sem setor mapeado não recebem choque.", st["body"]))
    A(Paragraph("3.2 Transferência da ΔPD ao contrato", st["h2"]))
    A(Paragraph(
        "A ΔPD do CLIMACRED refere-se à firma representativa do setor. Duas formas de aplicá-la a um contrato <i>i</i> foram "
        "implementadas. A soma direta, coerente com o uso previsto pelos autores para a firma representativa, é", st["body0"]))
    A(_eq(key="add", number=7))
    A(Paragraph("O deslocamento da variável latente converte a ΔPD em Δz a partir de uma PD de referência e aplica (1):", st["body0"]))
    A(_eq(key="dz", number=8))
    A(Paragraph(
        "As duas formas coincidem quando a PD do contrato é igual à PD de referência. A soma direta atribui o mesmo acréscimo absoluto a "
        "um contrato de rating A e a um de rating B; o deslocamento preserva a ordenação e gera multiplicadores maiores para PDs baixas. "
        "A escolha da PD de referência importa: a PD de linha de base do CLIMACRED mede o choque na escala do próprio modelo, enquanto "
        "a média da carteira o mede na escala das PDs de doze meses. Neste relatório, a aplicação adotada foi o " + metodo + ".",
        st["body0"]))
    A(Paragraph(
        "A <i>baseline_pd</i> do CLIMACRED não é uma PD de doze meses. Para trazer o choque ao horizonte anual, supõe-se carteira "
        "homogênea com intensidade de default constante no horizonte T do modelo, de modo que a PD acumulada em T anos corresponde a "
        "uma PD anual π<sub>T</sub>(p). O deslocamento passa a ser medido entre as PDs anualizadas:", st["body0"]))
    A(_eq(key="dz_h"))
    A(Paragraph(
        "Como π<sub>T</sub> comprime a escala, o Δz anualizado é menor que o da expressão (8) e o choque resultante é mais brando. "
        + (f"Neste relatório, o ajuste foi aplicado com T = {f2(p.horizon)} anos, premissa a documentar a partir da especificação do "
           "CLIMACRED." if p.mode == "dz" and p.horizon > 1 else
           "Neste relatório, o ajuste não foi aplicado (T = 1); ele fica disponível como análise de sensibilidade."),
        st["body"]))
    A(Paragraph("3.3 Perdas e capital", st["h2"]))
    A(Paragraph("A perda esperada e o capital econômico de cada contrato são", st["body0"]))
    A(_eq(key="pe", number=9))
    A(_eq(key="k_irb", number=10))
    A(Paragraph("com correlação R<sub>i</sub> e ajuste de prazo b<sub>i</sub> dados por", st["body0"]))
    A(_eq(key="r_b", number=11))
    A(Paragraph(
        "A fórmula (10) é a função de ponderação de risco do IRB para exposições corporativas (BASEL COMMITTEE ON BANKING SUPERVISION, "
        "CRE31; GORDY, 2003), adotada pelo Banco Central do Brasil para o cálculo da parcela RWA<sub>CIRB</sub> (Resolução BCB n. 303/2023). "
        "O capital ASRF do contrato, o RWA correspondente e o capital econômico da carteira na mesma lógica CEA = PE + PI são", st["body0"]))
    A(_eq(key="asrf_cap", number=12))
    A(Paragraph(
        f"com fator de escala s = {f2(p.irb_scale)} e piso de PD de {pc(p.pd_floor)}; o prazo efetivo M fica entre um e cinco anos. "
        "Como K já exclui a perda esperada, K·EAD é diretamente comparável à perda inesperada do CreditRisk+. Os impactos são as "
        "diferenças em relação à situação de base, avaliadas no ano de maior impacto de cada cenário"
        + ("" if p.year == "pico" else f" (aqui, no ano fixo de {p.year})")
        + (f", e expressos também como fração do Patrimônio de Referência informado ({money(pr)})" if has_pr(pr) else "")
        + ". O balanço é mantido estático.",
        st["body0"]))
    A(Paragraph(
        "Contratos em estágio 3 (Resolução CMN n. 4.966/2021) já estão inadimplidos: a PD é 100% e não há choque de PD a aplicar. "
        "Para eles adota-se o tratamento de exposições em default do IRB, com a provisão constituída como estimativa de "
        "EL<super>best</super> (ou LGD·EAD, na ausência de provisão):", st["body"]))
    A(_eq(key="k_def"))
    A(Paragraph(
        "No CreditRisk+, a perda dessas exposições é determinística, LGD·EAD, e apenas desloca a distribuição, sem alterar a perda "
        "inesperada. Nos dois modelos PE + PI desses contratos soma LGD·EAD, e o efeito climático recai somente sobre os estágios 1 e 2"
        + (f". Na carteira analisada há {B['n_def']} contratos em estágio 3, com {money(B['ead_def'])} de EAD." if B.get("n_def") else "."),
        st["body"]))

    crp = out.get("crp")
    if crp:
        cpar = crp["params"]
        A(Paragraph("3.4 Calibragem do CreditRisk+", st["h2"]))
        A(Paragraph(
            f"A calibragem é parametrizável. Neste relatório: nível de confiança de {pc(cpar.conf)}; "
            + ("um fator gama por setor do CLIMACRED, com cada contrato integralmente ligado ao fator do seu setor"
               if cpar.sectors == "climacred" else "um único fator sistêmico comum a todos os contratos")
            + f"; peso idiossincrático w<sub>0</sub> = {f2(cpar.w0)}; volatilidade relativa da taxa de inadimplência "
            f"σ<sub>k</sub>/μ<sub>k</sub> = {f2(cpar.vol_ratio)} na base e {f2(cpar.vol_ratio * cpar.stress_vol)} no estresse; e unidade de "
            f"perda L<sub>0</sub> = {money(crp['L0'])}, correspondente a {cpar.bands_max} bandas para a maior exposição. A volatilidade "
            "relativa é a principal premissa: ela controla a espessura da cauda e, portanto, a perda inesperada.", st["body"]))

    # 4 Dados
    A(Paragraph("4. Dados", st["h1"]))
    A(Paragraph(
        f"A carteira {'é fictícia, gerada para ilustração, e ' if cart_src == 'ex' else ''}contém {len(c)} contratos, com EAD de "
        f"{money(B['ead'])}, PD média ponderada de {pc(B['pdw'])}, perda esperada de {money(B['pe'])} e capital "
        f"econômico de {money(B['cap'])} na situação de base. A Figura 1 mostra a distribuição da exposição por setor. A ΔPD "
        + ("é ilustrativa, ancorada em valores publicados e completada por premissas, e não deve ser usada para decisões."
           if ill else f"vem do arquivo {data.get('fonte')} (NGFS Phase 5 Short-Term, versão 1.1, IIASA)."), st["body"]))
    A(KeepTogether([_fig_to_image(_fig_sectors(out), 14.5),
                    _caption(st, "<b>Figura 1.</b> Exposição no default por setor do CLIMACRED (quinze maiores).")]))

    # 5 Resultados
    A(Paragraph("5. Resultados", st["h1"]))
    A(Paragraph(
        f"A Tabela 2 consolida o resultado por cenário. O cenário mais severo é {W['sc']['nome']}, em {YEARS[W['yi']]}, com PD média "
        f"ponderada de {pc(W['ev']['pd_media'])} e impacto total de {impact(W['ev']['dtot'], pr)}. A Figura 2 decompõe esse impacto "
        "entre perda esperada e capital, e a Figura 3 mostra a trajetória anual da perda esperada incremental: os cenários de "
        "transição acumulam efeito ao longo do tempo, enquanto os cenários físicos produzem picos concentrados nos anos dos eventos.",
        st["body"]))
    g = _mb
    rows = [["Linha de base", "–", pc(B["pdw"]), g(B["pe"]), "–", g(B["cap"]), "–", "–"]]
    rows += [[r["sc"]["nome"], str(YEARS[r["yi"]]), pc(r["ev"]["pd_media"]), g(r["ev"]["pe"]), g(r["ev"]["dpe"]), g(r["ev"]["cap"]),
              g(r["ev"]["dcap"]), impact(r["ev"]["dtot"], pr).replace(" do PR", "")] for r in R]
    A(KeepTogether([_caption(st, "<b>Tabela 2.</b> Perda esperada e capital econômico por cenário (R$; mi = milhões, bi = bilhões), no ano de avaliação."),
                    _table(rows, ["Cenário", "Ano", "PD média", "PE", "Δ PE", "Capital", "Δ capital", "Δ total % PR" if has_pr(pr) else "Δ total"],
                           [4.4, 1.0, 1.6, 1.6, 1.6, 1.8, 1.7, 2.0], st, align_right_from=1)]))
    A(KeepTogether([_fig_to_image(_fig_bars(out), 14.5),
                    _caption(st, f"<b>Figura 2.</b> Impacto incremental {'em % do Patrimônio de Referência' if has_pr(pr) else 'em R$'}: perda esperada (cinza) e "
                                 "capital econômico (hachurado).")]))
    A(KeepTogether([_fig_to_image(_fig_trajectory(out), 14.5),
                    _caption(st, "<b>Figura 3.</b> Perda esperada incremental por ano e cenário.")]))

    # setores
    sec_rows = []
    per = pd.concat([r["per"].assign(cen=r["sc"]["curto"]) for r in R])
    piv = per.assign(setor=per.setor.map(SECTOR_NAME).fillna("Sem mapeamento")).pivot_table(
        index="setor", columns="cen", values="delta_pe", aggfunc="sum").fillna(0)
    cols = [r["sc"]["curto"] for r in R]
    piv = piv[cols]
    piv = piv.loc[piv.max(axis=1).sort_values(ascending=False).index].head(10)
    for s, v in piv.iterrows():
        sec_rows.append([s] + [_mb(x) for x in v])
    A(Paragraph(
        f"A Tabela 3 mostra os dez setores com maior perda incremental. {piv.index[0]} concentra o maior efeito. Nos cenários físicos o "
        "choque se espalha por agricultura, energia elétrica, construção e serviços; nos de transição, concentra-se em carvão, petróleo, "
        "gás e derivados, enquanto setores ligados à geração renovável chegam a ter ΔPD negativa.", st["body"]))
    w_first = 16.0 - 1.85 * len(cols)
    A(KeepTogether([_caption(st, "<b>Tabela 3.</b> Perda esperada incremental por setor e cenário (R$), dez maiores."),
                    _table(sec_rows, ["Setor"] + cols, [w_first] + [1.85] * len(cols), st)]))

    # método
    a_, d_ = ("other", "ev") if p.mode == "dz" else ("ev", "other")
    fm = (lambda x: pc(x / pr)) if has_pr(pr) else _mb  # noqa: E731
    cmp_rows = [[r["sc"]["nome"], fm(r[a_]["dtot"]), fm(r[d_]["dtot"])] for r in R]
    A(Paragraph("A Tabela 4 compara as duas formas de transferir a ΔPD ao contrato, mantida a mesma PD de referência.", st["body"]))
    A(KeepTogether([_caption(st, f"<b>Tabela 4.</b> Impacto total {'em % do PR' if has_pr(pr) else 'em R$'} pela soma direta e pelo deslocamento Δz."),
                    _table(cmp_rows, ["Cenário", "Soma direta", "Deslocamento Δz"], [8.0, 3.5, 3.5], st)]))

    # contratos
    top = W["per"].assign(t=W["per"].delta_pe + W["per"].delta_capital).nlargest(8, "t")
    top_rows = [[x.id_contrato, SECTOR_NAME.get(x.setor, "–"), x.rating, _mb(x.ead), pc(x.pd_base), pc(x.pd_estressada),
                 _mb(x.delta_pe), _mb(x.delta_capital)] for x in top.itertuples()]
    A(KeepTogether([_caption(st, f"<b>Tabela 5.</b> Contratos mais afetados em {W['sc']['nome']}, {YEARS[W['yi']]} (R$)."),
                    _table(top_rows, ["Contrato", "Setor", "Rating", "EAD", "PD base", "PD estress.", "Δ PE", "Δ capital"],
                           [1.6, 5.0, 1.2, 1.7, 1.6, 1.7, 1.5, 1.7], st, align_right_from=3)]))

    if crp:
        cb = crp["base"]
        A(Paragraph("5.1 Capital econômico pelo CreditRisk+", st["h2"]))
        wid = max(R, key=lambda r: crp["cen"][r["sc"]["id"]]["cea"] - cb["cea"])
        xw = crp["cen"][wid["sc"]["id"]]
        A(Paragraph(
            f"Na carteira de base, o CreditRisk+ resulta em CEA = {money(cb['pe'])} + {money(cb['pi'])} = {money(cb['cea'])}. "
            f"A Tabela 6 mostra o capital em cada cenário. O maior aumento ocorre em {wid['sc']['nome']}, com CEA<sub>stress</sub> = "
            f"{money(xw['cea'])}, acréscimo de {money(xw['cea'] - cb['cea'])}, dos quais {money(xw['pe'] - cb['pe'])} de perda "
            f"esperada e {money(xw['pi'] - cb['pi'])} de perda inesperada. A Figura 4 compara as duas distribuições de perda.",
            st["body"]))
        crow = [["Base", "–", _mb(cb["pe"]), _mb(cb["pi"]), _mb(cb["cea"]), "–"]]
        crow += [[r["sc"]["nome"], str(YEARS[r["yi"]]), _mb(crp["cen"][r["sc"]["id"]]["pe"]), _mb(crp["cen"][r["sc"]["id"]]["pi"]),
                  _mb(crp["cen"][r["sc"]["id"]]["cea"]), _mb(crp["cen"][r["sc"]["id"]]["cea"] - cb["cea"])] for r in R]
        A(KeepTogether([_caption(st, f"<b>Tabela 6.</b> CreditRisk+: CEA = PE + PI na base e em cada cenário (confiança de {pc(cpar.conf)})."),
                        _table(crow, ["Cenário", "Ano", "PE", "PI", "CEA", "Δ CEA"], [6.0, 1.2, 2.2, 2.2, 2.2, 2.2], st, align_right_from=1)]))
        A(KeepTogether([_fig_to_image(fig_capital(crp, wid["sc"]["id"], f"{wid['sc']['nome']} ({YEARS[wid['yi']]})"), 14.5),
                        _caption(st, f"<b>Figura 4.</b> Distribuição de perdas da carteira pelo CreditRisk+, na base e em "
                                     f"{wid['sc']['nome']}, na mesma escala. A perda esperada (PE) é a média da distribuição; a "
                                     f"perda inesperada (PI), ou capital econômico, vai da PE ao quantil de {pc(cpar.conf)}; o CEA "
                                     "é a soma das duas e coincide com o VaR. No painel de estresse, a curva tracejada e as linhas "
                                     "pontilhadas reproduzem a base, evidenciando o deslocamento e o alongamento da cauda.")]))

    if crp0:
        A(Paragraph("5.2 Comparação dos modelos de capital", st["h2"]))
        cc = capital_compare(out)
        A(Paragraph(
            "A Tabela 7 reúne os dois capitais na mesma lógica CEA = PE + PI. A perda esperada é a mesma; a perda inesperada difere "
            "porque o ASRF soma o capital de cada contrato com correlação regulatória entre 12% e 24% e ajuste de prazo, supondo carteira "
            "infinitamente granular, enquanto o CreditRisk+ obtém a distribuição de perdas da carteira em horizonte de um ano, com "
            "dependência dada pela volatilidade dos fatores setoriais e com efeito de concentração. "
            f"O capital de referência adotado nos destaques deste relatório é o {MLAB}.", st["body"]))
        crow7 = [[r_["Cenário"], r_["Ano"], _mb(r_["PE"]), _mb(r_["PI ASRF (K·EAD)"]), _mb(r_["CEA ASRF (PE + K·EAD)"]),
                  _mb(r_["PI CreditRisk+"]), _mb(r_["CEA CreditRisk+"])] for _, r_ in cc.iterrows()]
        A(KeepTogether([_caption(st, "<b>Tabela 7.</b> Capital econômico pelos dois modelos, na base e em cada cenário (R$)."),
                        _table(crow7, ["Cenário", "Ano", "PE", "PI ASRF", "CEA ASRF", "PI CR+", "CEA CR+"],
                               [4.6, 1.0, 1.9, 2.0, 2.2, 2.0, 2.2], st, align_right_from=1)]))

    # 6 Discussão
    A(Paragraph("6. Discussão e limitações", st["h1"]))
    A(Paragraph(
        "O ponto metodológico central é a escala. A ΔPD do CLIMACRED é medida sobre a PD de linha de base do próprio modelo, cujo nível "
        "é muito superior ao de uma PD de doze meses de carteira corporativa. Somar a ΔPD diretamente a PDs de doze meses, como em "
        "Barón et al. (2026), mistura as duas escalas e tende a produzir choques mais severos, sobretudo para bons ratings. A conversão "
        "em Δz sobre a PD de linha de base do CLIMACRED mede o choque na escala do modelo e o transfere à escala da carteira, "
        "preservando a ordenação de risco. A escolha deve ser documentada como premissa e acompanhada da comparação da Tabela 4.",
        st["body"]))
    A(Paragraph(
        "Outras limitações merecem registro. O balanço é estático e não há reação de originação, repactuação ou cobertura. A LGD é "
        "mantida constante, embora a literatura documente correlação positiva entre PD e LGD e o risco físico possa reduzir o valor de "
        "garantias. O choque físico é uniforme dentro do país, sem informação geográfica dos tomadores. O CLIMACRED não considera "
        "garantias governamentais nem programas de apoio, como seguro rural e Proagro, que no Brasil podem mitigar perdas de forma "
        "relevante. Por fim, a ΔPD reflete a reprecificação por mudança de expectativas, e não uma taxa de inadimplência observada, o que "
        "dificulta o confronto direto com eventos históricos.", st["body"]))
    A(Paragraph(
        "Para uso no ICAAP, recomenda-se: tratar o capital ASRF como capital econômico, pois na abordagem padronizada o RWA de crédito não "
        "reage à PD; levar a perda esperada incremental às provisões e à migração de estágios previstas na Resolução CMN n. 4.966/2021; "
        "somar o Δz climático ao do cenário macroeconômico adverso; e submeter as premissas à validação independente, com análise de "
        "sensibilidade e comparação com os exercícios do Banco Central.", st["body"]))

    # 7 Conclusão
    A(Paragraph("7. Conclusão", st["h1"]))
    A(Paragraph(
        f"Os cenários de curto prazo do NGFS permitem, pela primeira vez, um teste de estresse climático de crédito com PD condicional "
        f"ao cenário publicada por setor e país. Aplicada à carteira analisada, a ΔPD do CLIMACRED eleva o capital econômico pelo "
        f"{MLAB} entre {impact(model_delta(out, bestm)['dtot'], pr).replace(' do PR', '')} e {impact(DWM['dtot'], pr, True)}, com "
        "predominância dos cenários físicos no curto prazo e dos de transição ao fim do horizonte. "
        + ("Os dois modelos de capital divergem de forma relevante: o ASRF, contrato a contrato e com ajuste de prazo, e o CreditRisk+, "
           "que capta concentração. A divergência é informação útil para o ICAAP e deve ser explicada, e não escolhida. " if crp0 else "")
        + "A magnitude depende ainda da transferência da ΔPD ao contrato, que deve ser tratada como premissa explícita do exercício.",
        st["body"]))

    A(PageBreak())
    A(Paragraph("Referências", st["h1"]))
    for ref in REFERENCES:
        A(Paragraph(ref, st["ref"]))
    if ill:
        A(Spacer(1, 6))
        A(Paragraph("Nota: os resultados deste relatório usam ΔPD ilustrativa e não devem ser utilizados para decisões.", st["note"]))

    # ---------------- Apêndice A: memória de cálculo por cenário ----------------
    from scipy.stats import norm
    A(PageBreak())
    A(Paragraph("Apêndice A – Memória de cálculo por cenário", st["h1"]))
    A(Paragraph(
        "Para cada cenário, esta memória mostra (i) a ΔPD do CLIMACRED usada nos principais setores da carteira no ano de avaliação, "
        "(ii) o cálculo completo para o contrato mais afetado, da ΔPD setorial ao capital, e (iii) a agregação na carteira, pelo ASRF "
        "e pelo CreditRisk+. Valores monetários em R$; PDs em %.", st["body0"]))
    top_sec = c.groupby("sec")["ead"].sum().sort_values(ascending=False).head(6).index
    for n_, r in enumerate(R, 1):
        per, ev, yr = r["per"], r["ev"], YEARS[r["yi"]]
        A(Paragraph(f"A.{n_} {r['sc']['nome']} – {yr}", st["h2"]))
        A(Paragraph(
            f"Natureza: {(lambda t: t[:1].lower() + t[1:] if t else 'não classificada')(r['sc'].get('tipo', ''))}. Ano de avaliação: {yr}"
            + (" (ano de maior impacto do cenário)" if p.year == "pico" else "") + ". "
            + (f"Aplicação por deslocamento Δz, com referência em {REF_TXT.get(r.get('ref_used'), 'PD de referência')}."
               if p.mode == "dz" else "Aplicação por soma direta da ΔPD à PD de cada contrato."), st["body0"]))
        srows = []
        for s_ in top_sec:
            g_ = per[per.setor == s_]
            if g_.empty:
                continue
            d_, rf_ = g_["delta_pd_pp"].iloc[0], g_["pd_ref"].iloc[0]
            dz_ = (norm.ppf(_ann(rf_ + d_ / 100, p)) - norm.ppf(_ann(rf_, p))) if (p.mode == "dz" and not pd.isna(d_)) else np.nan
            srows.append([SECTOR_NAME.get(s_, s_), "–" if pd.isna(d_) else f2(d_), pc(rf_) if p.mode == "dz" else "–",
                          "–" if pd.isna(dz_) else f3(dz_)])
        A(KeepTogether([_caption(st, f"<b>Tabela A.{n_}a.</b> ΔPD setorial em {yr} (seis setores de maior EAD)."),
                        _table(srows, ["Setor", "ΔPD (p.p.)", "PD de referência", "Δz"], [8.4, 2.4, 2.8, 2.4], st)]))
        x = per.assign(t=per.delta_pe + per.delta_capital).sort_values("t", ascending=False).iloc[0]
        p0, ps_, lgd_, ead_, m_ = x.pd_base, x.pd_estressada, x.lgd, x.ead, x.m
        R0, b0, K0 = _asrf_parts(p0, lgd_, m_, p.pd_floor, p.irb_scale)
        R1, b1, K1 = _asrf_parts(ps_, lgd_, m_, p.pd_floor, p.irb_scale)
        steps = [["1", "Dados do contrato", f"{x.id_contrato} · {SECTOR_NAME.get(x.setor, x.setor)} · {x.pais} · rating {x.rating}",
                  f"PD<sub>0</sub> {pc(p0)}; LGD {pc(lgd_)}; EAD {_mb(ead_)}; M {f2(m_)}"],
                 ["2", "ΔPD do setor (pd_adjustment)", f"série do CLIMACRED, {x.pais}, {yr}", f"{f2(x.delta_pd_pp)} p.p."]]
        if p.mode == "dz":
            a_r, a_rs = _ann(x.pd_ref, p), _ann(x.pd_ref + x.delta_pd_pp / 100, p)
            z_r, z_rs = norm.ppf(a_r), norm.ppf(a_rs)
            dz = z_rs - z_r
            steps += [["3", "PD de referência", REF_TXT.get(r.get("ref_used"), "").replace("<i>", "").replace("</i>", ""), pc(x.pd_ref)]]
            if p.horizon > 1:
                steps += [["3a", f"Anualização π<sub>T</sub>(p) = 1 − (1 − p)<super>1/T</super>, T = {f2(p.horizon)}",
                           f"π({pc(x.pd_ref)}) e π({pc(x.pd_ref + x.delta_pd_pp / 100)})", f"{pc(a_r)} e {pc(a_rs)}"]]
            steps += [["4", "Δz = Φ⁻¹(π(PD<sub>ref</sub> + ΔPD)) − Φ⁻¹(π(PD<sub>ref</sub>))" if p.horizon > 1 else
                             "Δz = Φ⁻¹(PD<sub>ref</sub> + ΔPD) − Φ⁻¹(PD<sub>ref</sub>)",
                       f"Φ⁻¹({pc(a_rs)}) − Φ⁻¹({pc(a_r)}) = {f3(z_rs)} − ({f3(z_r)})", f3(dz)],
                      ["5", "PD<sub>s</sub> = Φ(Φ⁻¹(PD<sub>0</sub>) + Δz)", f"Φ({f3(norm.ppf(p0))} + {f3(dz)}) = Φ({f3(norm.ppf(p0) + dz)})", pc(ps_)]]
        else:
            steps += [["3", "PD<sub>s</sub> = PD<sub>0</sub> + ΔPD", f"{pc(p0)} + {f2(x.delta_pd_pp)} p.p.", pc(ps_)]]
        k0 = len(steps) + 1
        steps += [[str(k0), "Correlação R (base → estresse)", "0,12·w + 0,24·(1 − w), w = (1 − e<super>−50PD</super>)/(1 − e<super>−50</super>)",
                   f"{f3(R0)} → {f3(R1)}"],
                  [str(k0 + 1), "Ajuste de prazo b", "(0,11852 − 0,05478·ln PD)²", f"{f3(b0)} → {f3(b1)}"],
                  [str(k0 + 2), "K (equação 10)", "fator de capital por unidade de EAD", f"{pc(K0)} → {pc(K1)}"],
                  [str(k0 + 3), "Capital ASRF = K·EAD", f"{pc(K0)} × {_mb(ead_)} → {pc(K1)} × {_mb(ead_)}",
                   f"{_mb(K0 * ead_)} → {_mb(K1 * ead_)}"],
                  [str(k0 + 4), "PE = PD·LGD·EAD", f"{pc(p0)} × {pc(lgd_)} × {_mb(ead_)} → {pc(ps_)} × {pc(lgd_)} × {_mb(ead_)}",
                   f"{_mb(p0 * lgd_ * ead_)} → {_mb(ps_ * lgd_ * ead_)}"]]
        A(KeepTogether([_caption(st, f"<b>Tabela A.{n_}b.</b> Memória de cálculo do contrato mais afetado ({x.id_contrato})."),
                        _table(steps, ["#", "Etapa", "Cálculo", "Resultado"], [0.6, 4.6, 6.6, 4.2], st, align_right_from=9)]))
        arow = [["Perda esperada (Σ PD·LGD·EAD)", _mb(B["pe"]), _mb(ev["pe"]), _mb(ev["dpe"])],
                ["Capital ASRF (Σ K·EAD)", _mb(B["cap"]), _mb(ev["cap"]), _mb(ev["dcap"])],
                ["PD média ponderada por EAD", pc(B["pdw"]), pc(ev["pd_media"]), f2(100 * (ev["pd_media"] - B["pdw"])) + " p.p."]]
        if crp:
            xs = crp["cen"][r["sc"]["id"]]
            arow += [["CreditRisk+: PE", _mb(cb["pe"]), _mb(xs["pe"]), _mb(xs["pe"] - cb["pe"])],
                     ["CreditRisk+: PI = Q<sub>q</sub>(L) − E[L]", _mb(cb["pi"]), _mb(xs["pi"]), _mb(xs["pi"] - cb["pi"])],
                     ["CreditRisk+: CEA = PE + PI", _mb(cb["cea"]), _mb(xs["cea"]), _mb(xs["cea"] - cb["cea"])]]
        if has_pr(pr):
            arow += [["Δ (PE + capital ASRF) em % do PR", "–", "–", pc(ev["dtot"] / pr)]]
        A(KeepTogether([_caption(st, f"<b>Tabela A.{n_}c.</b> Agregação na carteira ({len(c)} contratos)."),
                        _table(arow, ["Medida", "Base", "Estresse", "Variação"], [7.0, 3.0, 3.0, 3.0], st)]))
        if crp:
            A(KeepTogether([_fig_to_image(fig_capital(crp, r["sc"]["id"], f"{r['sc']['nome']} ({yr})", figsize=(7.4, 7.0)), 13.0),
                            _caption(st, f"<b>Figura A.{n_}.</b> CreditRisk+: PE, PI e CEA na base e em {r['sc']['nome']}.")]))

    # ---------------- Apêndice B: memória do CreditRisk+ ----------------
    if crp:
        A(PageBreak())
        A(Paragraph("Apêndice B – Memória de cálculo do CreditRisk+", st["h1"]))
        n_tot = int(np.maximum(1, np.rint((c.lgd * c.ead) / crp["L0"])).sum())
        A(Paragraph(
            f"Etapa 1 – discretização. A unidade de perda é L<sub>0</sub> = max(LGD·EAD)/{cpar.bands_max} = {money(crp['L0'])}; cada "
            f"contrato recebe ν<sub>i</sub> = arredondamento de LGD<sub>i</sub>·EAD<sub>i</sub>/L<sub>0</sub> (mínimo 1). A soma das "
            f"bandas é {n_tot:,}".replace(",", ".") + f" e a grade de perdas usada tem {cb['n']:,}".replace(",", ".")
            + " pontos, truncada bem além do quantil de interesse; a massa de probabilidade capturada foi de "
            + f"{f3(100 * cb['massa'])}% na base.", st["body0"]))
        A(Paragraph(
            f"Etapa 2 – fatores. Para cada fator, μ<sub>k</sub> = Σ PD<sub>i</sub> (contratos do fator), σ<sub>k</sub> = "
            f"{f2(cpar.vol_ratio)}·μ<sub>k</sub>, α<sub>k</sub> = μ<sub>k</sub>²/σ<sub>k</sub>² = {f3(1 / cpar.vol_ratio ** 2)} e "
            f"β<sub>k</sub> = σ<sub>k</sub>²/μ<sub>k</sub>. A Tabela B.1 traz os fatores da carteira de base.", st["body0"]))
        ft = cb["fatores"].sort_values("mu", ascending=False).head(12)
        frow = [[SECTOR_NAME.get(f_.fator, f_.fator), str(f_.contratos), f3(f_.mu), f3(f_.sigma), f3(f_.alpha), f3(f_.beta),
                 f3(f_.beta / (1 + f_.beta)), _mb(f_.pe)] for f_ in ft.itertuples()]
        A(KeepTogether([_caption(st, "<b>Tabela B.1.</b> Parâmetros dos fatores na carteira de base (doze maiores por μ)."),
                        _table(frow, ["Fator", "Contr.", "μ", "σ", "α", "β", "p = β/(1+β)", "PE"],
                               [5.2, 1.2, 1.4, 1.4, 1.6, 1.4, 1.8, 2.0], st)]))
        A(Paragraph(
            "Etapa 3 – distribuição. Com P<sub>k</sub>(z) montado a partir das bandas e das PDs de cada fator, G(z) da equação (4) é "
            "avaliada nos pontos z = e<super>−2πim/M</super> pela transformada rápida de Fourier; a transformada inversa devolve a "
            "probabilidade de cada perda n·L<sub>0</sub>. O procedimento é numericamente equivalente à recursão de Panjer.",
            st["body0"]))
        A(Paragraph(
            f"Etapa 4 – quantil e decomposição. O quantil Q<sub>q</sub>(L) é o menor n·L<sub>0</sub> com probabilidade acumulada ≥ "
            f"{pc(cpar.conf)}. Na base, Q<sub>q</sub>(L) = {money(cb['quantil'])}, E[L] na grade = {money(cb['pe_banda'])}, "
            f"PI = {money(cb['pi'])} e CEA = PE + PI = {money(cb['pe'])} + {money(cb['pi'])} = {money(cb['cea'])}. No estresse repete-se o "
            f"cálculo com as PDs estressadas e σ/μ = {f2(cpar.vol_ratio * cpar.stress_vol)}, mantidas exposições e bandas (Tabela 6).",
            st["body0"]))

    buf = io.BytesIO()

    def _page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Serif", 8.5)
        canvas.drawCentredString(A4[0] / 2, 1.3 * cm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2.5 * cm, rightMargin=2.5 * cm, topMargin=2.3 * cm, bottomMargin=2.3 * cm,
                            title="Estresse climático em carteiras de crédito corporativo – ClimaCred", author=author or "ClimaCred")
    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    return buf.getvalue()
