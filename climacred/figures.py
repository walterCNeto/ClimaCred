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


def _bbox(fig, t):
    fig.canvas.draw()
    return t.get_window_extent(fig.canvas.get_renderer())


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
