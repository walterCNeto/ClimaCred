"""Figura do capital econômico: distribuição de perdas com PE, PI (capital econômico) e CEA/VaR, base × estresse,
com ampliação da cauda e rótulos sem sobreposição."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .report import f2, money, unit_for  # noqa: E402

plt.rcParams.update({"mathtext.fontset": "stix", "font.family": "STIXGeneral"})

MONO = {"curve": "black", "ghost": "0.50", "pe": "0.90", "pi": "0.68", "tail": "0.15", "line": "black", "box": "white",
        "boxedge": "black", "text": "black", "alpha_pi": 1.0}
COLOR = {"curve": "#1f3b4d", "ghost": "#7d8d96", "pe": "#cfe0ea", "pi": "#f08a84", "tail": "#8b0f0a", "line": "#121212",
         "box": "white", "boxedge": "#121212", "text": "#121212", "alpha_pi": 1.0}


def _density(d: dict, L0: float, xmax: float, bw: float, nbins: int = 500):
    """Densidade da distribuição discreta do CreditRisk+, suavizada por núcleo gaussiano com reflexão em zero."""
    edges = np.linspace(0, xmax, nbins + 1)
    x = np.arange(len(d["dist"])) * L0
    h, _ = np.histogram(x, bins=edges, weights=d["dist"])
    step = edges[1] - edges[0]
    s = max(bw / step, 1.0)
    half = int(np.ceil(4 * s))
    k = np.exp(-0.5 * (np.arange(-half, half + 1) / s) ** 2)
    k /= k.sum()
    hp = np.concatenate([h[:half][::-1], h, np.zeros(half)])
    sm = np.convolve(hp, k, mode="same")[half:half + nbins]
    return (edges[:-1] + edges[1:]) / 2, sm / step


def _m(x) -> str:
    """Valor monetário com '$' escapado para o mathtext."""
    return money(x).replace("$", r"\$")


def _box(c):
    return dict(boxstyle="square,pad=0.30", fc=c["box"], ec=c["boxedge"], lw=0.6)


def _darrow(ax, x0, x1, y, c):
    ax.annotate("", xy=(x1, y), xytext=(x0, y), zorder=5,
                arrowprops=dict(arrowstyle="<|-|>", color=c["line"], lw=1.0, shrinkA=0, shrinkB=0, mutation_scale=9))


def _renderer(fig):
    """Renderizador Agg da figura, qualquer que seja o backend ativo (no Streamlit Cloud o canvas pode ser o
    FigureCanvasBase, que não tem get_renderer)."""
    if not hasattr(fig.canvas, "get_renderer"):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        FigureCanvasAgg(fig)
    fig.canvas.draw()
    return fig.canvas.get_renderer()


def _bbox(fig, t):
    return t.get_window_extent(_renderer(fig))


def _fit_label(fig, ax, t, x0, x1):
    """Se o rótulo for mais largo que a seta, alinha-o à esquerda da seta."""
    bb = _bbox(fig, t)
    a0, a1 = ax.transData.transform((x0, 0))[0], ax.transData.transform((x1, 0))[0]
    if bb.width > (a1 - a0) * 0.96:
        t.set_ha("left")
        t.set_x(x0)


def _panel(fig, ax, d, L0, xmax, dv, conf, c, title, bw, ytop, ghost=None):
    x, y = _density(d, L0, xmax, bw)
    pe, q = d["pe"], d["quantil"]
    X = x / dv
    # regiões: PE, PI (capital econômico) e cauda
    ax.fill_between(X, y, where=x <= pe, color=c["pe"], lw=0, zorder=1)
    ax.fill_between(X, y, where=(x >= pe) & (x <= q), color=c["pi"], lw=0, zorder=1)
    ax.fill_between(X, y, where=x >= q, color=c["tail"], lw=0, zorder=1)
    if ghost is not None:
        gx, gy = _density(ghost, L0, xmax, bw)
        ax.plot(gx / dv, gy, color=c["ghost"], lw=1.2, ls=(0, (5, 2.5)), zorder=2)
        for v in (ghost["pe"], ghost["quantil"]):
            ax.axvline(v / dv, ymax=0.52, color=c["ghost"], lw=0.8, ls=(0, (1, 2)), zorder=2)
    ax.plot(X, y, color=c["curve"], lw=1.8, zorder=3)
    ax.axvline(pe / dv, ymax=0.97, color=c["line"], lw=0.9, zorder=3)
    ax.axvline(q / dv, ymax=0.97, color=c["line"], lw=0.9, zorder=3)
    # linha 1: CEA = PE + PI = VaR; linha 2: PE e PI
    y1, y2, gap = 0.885 * ytop, 0.67 * ytop, 0.022 * ytop
    _darrow(ax, 0, q / dv, y1, c)
    t1 = ax.text(q / dv / 2, y1 + gap, f"CEA = PE + PI = VaR$_q$ = {_m(d['cea'])}", ha="center", va="bottom",
                 fontsize=10, color=c["text"], bbox=_box(c), zorder=6)
    _fit_label(fig, ax, t1, 0, q / dv)
    _darrow(ax, 0, pe / dv, y2, c)
    _darrow(ax, pe / dv, q / dv, y2, c)
    tpe = ax.text(pe / dv / 2, y2 + gap, f"PE\n{_m(pe)}", ha="center", va="bottom", fontsize=9.5, color=c["text"],
                  bbox=_box(c), zorder=6, linespacing=1.15)
    tpi = ax.text((pe + q) / 2 / dv, y2 + gap, f"PI = capital econômico\n{_m(d['pi'])}", ha="center", va="bottom",
                  fontsize=9.5, color=c["text"], bbox=_box(c), zorder=6, linespacing=1.15)
    _fit_label(fig, ax, tpe, 0, pe / dv)
    # resolve sobreposição entre PE e PI empurrando o rótulo de PI para a direita
    b_pe, b_pi = _bbox(fig, tpe), _bbox(fig, tpi)
    if b_pe.x1 + 6 > b_pi.x0:
        shift = b_pe.x1 + 6 - b_pi.x0
        xd = ax.transData.inverted().transform((ax.transData.transform((tpi.get_position()[0], 0))[0] + shift, 0))[0]
        tpi.set_x(xd)
    # nível de confiança junto à linha do VaR
    ax.text(q / dv, 0.03 * ytop, f"nível de confiança q = {f2(100 * conf)}%  ", rotation=90, ha="right", va="bottom",
            fontsize=8.8, color=c["text"], zorder=6)
    # ampliação da cauda
    ins = ax.inset_axes([0.765, 0.07, 0.225, 0.42])
    lo = q - 0.30 * (q - pe)
    k = x >= lo
    ins.fill_between(X[k], y[k], where=x[k] <= q, color=c["pi"], lw=0)
    ins.fill_between(X[k], y[k], where=x[k] >= q, color=c["tail"], lw=0)
    ins.plot(X[k], y[k], color=c["curve"], lw=1.2)
    ins.axvline(q / dv, color=c["line"], lw=0.8)
    ymx = max(y[k].max(), 1e-30)
    ins.set_ylim(0, ymx * 1.25)
    ins.set_xlim(lo / dv, xmax / dv)
    ins.set_yticks([])
    ins.set_xticks([])
    for sp in ins.spines.values():
        sp.set_linewidth(0.6)
        sp.set_color(c["line"])
    ins.set_title("cauda ampliada", fontsize=8.5, pad=2.5, color=c["text"])
    ins.text(0.97, 0.42, f"1 − q =\n{f2(100 * (1 - conf))}%", transform=ins.transAxes, ha="right", va="bottom", fontsize=8.3,
             color=c["text"], linespacing=1.1)
    ins.text((q / dv), ymx * 1.12, "VaR$_q$ ", ha="right", va="center", fontsize=8.5, color=c["text"])
    # eixos
    ax.set_ylim(0, ytop)
    ax.set_xlim(0, xmax / dv)
    ax.set_yticks([])
    ax.spines[["top", "right"]].set_visible(False)
    big = xmax / dv >= 10
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _: f"{v:,.0f}".replace(",", ".") if big else f2(v)))
    ax.set_ylabel("Frequência", fontsize=10.5)
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=c["text"], pad=6)


def fig_capital(crp: dict, scen_id: str, scen_name: str, mono: bool = True, figsize=(7.6, 8.2)):
    """Dois painéis na mesma escala: base e estresse (com a base em tracejado); PE, PI e CEA/VaR anotados."""
    c = MONO if mono else COLOR
    cb, cs, L0 = crp["base"], crp["cen"][scen_id], crp["L0"]
    conf = crp["params"].conf
    xmax = max(cb["quantil"], cs["quantil"]) * 1.36
    dv, un, _ = unit_for([xmax])
    bw = 0.03 * xmax
    ytop = 2.35 * max(_density(cb, L0, xmax, bw)[1].max(), _density(cs, L0, xmax, bw)[1].max())
    fig, (a1, a2) = plt.subplots(2, 1, figsize=figsize)
    _panel(fig, a1, cb, L0, xmax, dv, conf, c, "Cenário base", bw, ytop)
    _panel(fig, a2, cs, L0, xmax, dv, conf, c, f"Cenário de estresse: {scen_name}", bw, ytop, ghost=cb)
    a2.set_xlabel(f"Perda da carteira (R$ {un})", fontsize=10.5)
    d_pe, d_pi, d_cea = cs["pe"] - cb["pe"], cs["pi"] - cb["pi"], cs["cea"] - cb["cea"]
    a2.text(0.992, 0.985, f"Efeito do estresse\nΔ PE:  +{money(d_pe)}\nΔ PI:  +{money(d_pi)}\nΔ CEA: +{money(d_cea)}\n"
            "– – distribuição de base", transform=a2.transAxes, ha="right", va="top", fontsize=9.2, color=c["text"],
            linespacing=1.35, bbox=dict(boxstyle="square,pad=0.45", fc=c["box"], ec=c["boxedge"], lw=0.8), zorder=7)
    fig.tight_layout(h_pad=2.2)
    return fig


# ---------------------------------------------------------------- figuras de resultados por setor, rating e cauda
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

from .config import SECTOR_NAME, YEARS  # noqa: E402

_GREY_DIV = LinearSegmentedColormap.from_list("grey_div", [(0, "#d9d9d9"), (0.5, "#ffffff"), (0.75, "#9a9a9a"), (1, "#262626")])
_COLOR_DIV = LinearSegmentedColormap.from_list("col_div", [(0, "#2b7a78"), (0.5, "#ffffff"), (0.75, "#f08a84"), (1, "#8b0f0a")])


def _short(sec):
    return SECTOR_NAME.get(sec, "Sem mapeamento").split(" (")[0] if isinstance(sec, str) else "Sem mapeamento"


def _heat(ax, M, rows, cols, fmt, cmap, cbar_label, fig):
    vmax = max(np.nanmax(np.abs(M)), 1e-9)
    vmin = min(np.nanmin(M), -1e-9)
    norm = TwoSlopeNorm(vmin=min(vmin, -vmax * 0.15), vcenter=0.0, vmax=vmax)
    Mm = np.ma.masked_where(np.isnan(M) | (np.abs(M) < 5e-4), M)
    cm_ = cmap.with_extremes(bad="white")
    im = ax.imshow(Mm, aspect="auto", cmap=cm_, norm=norm)
    ax.add_patch(plt.Rectangle((-0.5, -0.5), M.shape[1], M.shape[0], fill=False, ec="0.75", lw=0.6))
    ax.set_xticks(range(len(cols)), cols, fontsize=9)
    ax.set_yticks(range(len(rows)), rows, fontsize=9)
    ax.tick_params(length=0)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v) or abs(v) < 5e-4:
                ax.text(j, i, "–", ha="center", va="center", fontsize=8.5, color="0.45")
                continue
            dark = norm(v) > 0.78 or (norm(v) < 0.2 and cmap is _COLOR_DIV)
            ax.text(j, i, fmt(v), ha="center", va="center", fontsize=8.5, color="white" if dark else "black",
                    style="italic" if v < 0 else "normal")
    ax.set_xticks(np.arange(-0.5, len(cols)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(rows)), minor=True)
    ax.grid(which="minor", color="0.85", lw=0.8)
    ax.tick_params(which="minor", length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.ax.tick_params(labelsize=8)
    cb.set_label(cbar_label, fontsize=9)
    cb.ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f2(v)))


def fig_sector_impact(out: dict, top: int = 12, mono: bool = True):
    """Impacto líquido (Δ PE + Δ capital ASRF) por setor e cenário, em R$ mi; valores negativos (benefício) em itálico."""
    R = out["results"]
    cols = [f"{r['sc']['curto']}\n{YEARS[r['yi']]}" for r in R]
    per = [r["per"].assign(t=r["per"].delta_pe + r["per"].delta_capital, s=r["per"].setor.map(_short)) for r in R]
    tab = np.array([[0.0] * len(R)])
    import pandas as pd
    piv = pd.concat([p.groupby("s")["t"].sum().rename(i) for i, p in enumerate(per)], axis=1).fillna(0.0)
    piv = piv.loc[piv.abs().max(axis=1).sort_values(ascending=False).index[:top]]
    piv = piv.loc[piv.max(axis=1).sort_values(ascending=False).index]
    M = piv.to_numpy(float)
    fig, ax = plt.subplots(figsize=(6.6, 0.36 * len(piv) + 1.3))
    _heat(ax, M, list(piv.index), cols, lambda v: f2(v), _GREY_DIV if mono else _COLOR_DIV, "R$ mi", fig)
    del tab
    return fig


def fig_dpd_heatmap(out: dict, data: dict, top: int = 15, mono: bool = True):
    """ΔPD do CLIMACRED (p.p.) por setor e cenário no ano de avaliação, para o país padrão; setores de maior EAD."""
    c = out["portfolio"]
    pais = out["params"].fallback_country
    dpd = data["dpd"]
    secs = c.groupby("sec")["ead"].sum().sort_values(ascending=False).index[:top]
    R = out["results"]
    M = np.full((len(secs), len(R)), np.nan)
    for j, r in enumerate(R):
        sub = dpd[(dpd.cenario == r["sc"]["id"]) & (dpd.pais == pais) & (dpd.ano == YEARS[r["yi"]])].set_index("setor")["delta_pd_pp"]
        for i, s in enumerate(secs):
            if s in sub.index:
                M[i, j] = float(sub.loc[s])
    cols = [f"{r['sc']['curto']}\n{YEARS[r['yi']]}" for r in R]
    fig, ax = plt.subplots(figsize=(6.6, 0.34 * len(secs) + 1.3))
    _heat(ax, M, [_short(s) for s in secs], cols, lambda v: f2(v), _GREY_DIV if mono else _COLOR_DIV, "ΔPD (p.p.)", fig)
    return fig


_RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]


def fig_pd_rating(out: dict, mono: bool = True):
    """PD média ponderada por EAD em cada rating, na base e em cada cenário (escala logarítmica)."""
    import pandas as pd
    R = out["results"]
    styles = ["-", "--", "-.", ":", (0, (5, 1, 1, 1, 1, 1))]
    marks = ["o", "s", "^", "D", "v"]
    c = out["portfolio"]
    c = c[~c["default"]] if "default" in c else c
    order = [x for x in _RATING_ORDER if x in set(c["rating"])] + sorted(set(c["rating"]) - set(_RATING_ORDER))
    base = c.groupby("rating").apply(lambda g: np.average(g.pdb, weights=g.ead), include_groups=False).reindex(order)
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    ax.plot(range(len(order)), 100 * base.to_numpy(), color="black", lw=2.2, marker="o", ms=4, label="Base")
    for i, r in enumerate(R):
        p = r["per"]
        p = p[p.id_contrato.isin(c.id_contrato)]
        s = p.groupby("rating").apply(lambda g: np.average(g.pd_estressada, weights=g.ead), include_groups=False).reindex(order)
        ax.plot(range(len(order)), 100 * s.to_numpy(), color="0.35" if mono else None, ls=styles[i % 5], marker=marks[i % 5],
                ms=3.2, lw=1.0, label=f"{r['sc']['curto']} ({YEARS[r['yi']]})")
    ax.set_yscale("log")
    ax.set_xticks(range(len(order)), order)
    ax.set_ylabel("PD média ponderada (%)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f2(v) if v < 1 else f"{v:.0f}"))
    ax.grid(axis="y", which="both", color="0.88", lw=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.13))
    return fig


def fig_cdf_tail(crp: dict, results: list, conf: float | None = None, mono: bool = True):
    """Função de distribuição acumulada da perda pelo CreditRisk+ na região da cauda, base e cenários."""
    styles = ["--", "-.", ":", (0, (5, 1, 1, 1, 1, 1)), (0, (3, 1))]
    L0 = crp["L0"]
    conf = conf or crp["params"].conf
    qmax = max([crp["base"]["quantil"]] + [crp["cen"][r["sc"]["id"]]["quantil"] for r in results]) * 1.15
    dv, un, _ = unit_for([qmax])
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    items = [("Base", crp["base"], "-", 2.0, "black")] + [
        (f"{r['sc']['curto']} ({YEARS[r['yi']]})", crp["cen"][r["sc"]["id"]], styles[i % 5], 1.1, "0.30" if mono else None)
        for i, r in enumerate(results)]
    ylo = 0.98
    xlo = np.inf
    for lab, d, ls, lw, col in items:
        x = np.arange(len(d["dist"])) * L0 / dv
        cdf = np.cumsum(d["dist"])
        ax.plot(x, cdf, ls=ls, lw=lw, color=col, label=lab)
        xlo = min(xlo, x[int(np.searchsorted(cdf, ylo))])
    xlo *= 0.92
    ax.axhline(conf, color="black", lw=0.7, ls=(0, (1, 2)))
    ax.text(xlo + 0.01 * (qmax / dv - xlo), conf + 0.0004, f"nível de confiança q = {f2(100 * conf)}%", ha="left",
            va="bottom", fontsize=8.5)
    ax.set_xlim(xlo, qmax / dv)
    ax.set_ylim(ylo, 1.0015)
    ax.set_xlabel(f"Perda da carteira (R$ {un})")
    ax.set_ylabel("Probabilidade acumulada")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f2(100 * v) + "%"))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f2(v)))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(color="0.9", lw=0.5)
    ax.legend(frameon=False, fontsize=8.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.17))
    return fig
