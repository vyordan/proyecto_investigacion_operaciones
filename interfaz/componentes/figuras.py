"""Dibuja con matplotlib las ``Figura`` (especificaciones declarativas) del motor."""
from __future__ import annotations

from matplotlib.figure import Figure

from core.resultado import Figura

COLORES = ["#1f77b4", "#d62728", "#9467bd", "#ff7f0e", "#8c564b", "#17becf", "#e377c2", "#7f7f7f"]
VERDE = "#2ca02c"


def dibujar(figura: Figura) -> Figure:
    if figura.tipo == "region_factible":
        return _region_factible(figura)
    if figura.tipo == "curva_costos":
        return _curva_costos(figura)
    return _diente_sierra(figura)


def _recta(a: float, b: float, rhs: float, ancho: float, alto: float):
    """Dos puntos de la recta a·x + b·y = rhs dentro del cuadro [0, ancho] x [0, alto]."""
    if b != 0:
        return [0.0, ancho], [(rhs - a * 0.0) / b, (rhs - a * ancho) / b]
    return [rhs / a, rhs / a], [0.0, alto]


def _region_factible(figura: Figura) -> Figure:
    d = figura.datos
    X, Y = d["limites"]
    nx, ny = d["variables"]
    fig = Figure(figsize=(7.4, 5.2))
    ax = fig.subplots()

    poligono = d["poligono"]
    if len(poligono) >= 3:
        ax.fill([p[0] for p in poligono], [p[1] for p in poligono], color=VERDE, alpha=0.18,
                label="Región factible", zorder=1)
    elif len(poligono) == 2:
        ax.plot([p[0] for p in poligono], [p[1] for p in poligono], color=VERDE, lw=4, alpha=0.6,
                label="Región factible", zorder=1)

    for i, r in enumerate(d["rectas"]):
        xs, ys = _recta(r["a"], r["b"], r["rhs"], X, Y)
        ax.plot(xs, ys, color=COLORES[i % len(COLORES)], lw=2, label=r["etiqueta"], zorder=2)

    ro = d.get("recta_objetivo")
    if ro:
        xs, ys = _recta(ro["c1"], ro["c2"], ro["valor"], X, Y)
        ax.plot(xs, ys, "k--", lw=1.6, label=f"Recta de Z = {ro['valor']:g}", zorder=3)

    for v in d["vertices"]:
        if v["optimo"]:
            ax.scatter(v["x"], v["y"], s=260, marker="*", color="#FFC107", edgecolor="black", zorder=5)
        else:
            ax.scatter(v["x"], v["y"], s=36, color="black", zorder=4)
        ax.annotate(f"{v['etiqueta']} ({v['x']:g}, {v['y']:g})", (v["x"], v["y"]), textcoords="offset points",
                    xytext=(7, 7), fontsize=8, zorder=6)

    if d.get("no_acotada"):
        ax.text(0.98, 0.02, "región no acotada", transform=ax.transAxes, ha="right", va="bottom",
                fontsize=8, style="italic", alpha=0.7)

    ax.set_xlim(0, X)
    ax.set_ylim(0, Y)
    ax.set_xlabel(nx)
    ax.set_ylabel(ny)
    ax.grid(alpha=0.25)
    ax.set_title(figura.titulo)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def _curva_costos(figura: Figura) -> Figure:
    d = figura.datos
    fig = Figure(figsize=(7.2, 4.6))
    ax = fig.subplots()
    ax.plot(d["q"], d["costo_pedido"], color="#1f77b4", label="Costo de ordenar")
    ax.plot(d["q"], d["costo_mantener"], color="#ff7f0e", label="Costo de mantener")
    ax.plot(d["q"], d["costo_total"], color="black", lw=2.2, label="Costo total")
    ax.axvline(d["q_optimo"], color=VERDE, ls="--", lw=1.4)
    ax.scatter(d["q_optimo"], d["ct_optimo"], s=80, color=VERDE, zorder=5,
               label=f"Q* = {d['q_optimo']:.2f}")
    ax.set_ylim(0, max(d["costo_total"]) * 1.05)
    ax.set_xlabel("Tamaño de pedido Q")
    ax.set_ylabel("Costo anual")
    ax.set_title(figura.titulo)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def _diente_sierra(figura: Figura) -> Figure:
    d = figura.datos
    q, T, ss, rop, L = d["q"], d["t_ciclo_dias"], d["stock_seguridad"], d["rop"], d["plazo_dias"]
    ciclos = d["ciclos"]
    fig = Figure(figsize=(7.2, 4.4))
    ax = fig.subplots()
    nivel_max = q + ss
    xs, ys = [], []
    for k in range(ciclos):
        xs += [k * T, (k + 1) * T]
        ys += [nivel_max, ss]
        if k < ciclos - 1:
            xs.append((k + 1) * T)
            ys.append(nivel_max)
    ax.plot(xs, ys, color="#1f77b4", lw=2, label="Inventario")
    if ss > 0:
        ax.axhline(ss, color="#7f7f7f", ls=":", label=f"Stock de seguridad = {ss:g}")
    if rop is not None and rop <= nivel_max + 1e-9 and T > 0:
        ax.axhline(rop, color="#d62728", ls="--", label=f"Punto de reorden R = {rop:.2f}")
        pendiente = q / T
        t_pedido = (nivel_max - rop) / pendiente
        for k in range(ciclos):
            ax.axvspan(k * T + t_pedido, (k + 1) * T, color="#d62728", alpha=0.08)
        ax.annotate("se emite el pedido", (t_pedido, rop), textcoords="offset points", xytext=(6, 10),
                    fontsize=8, color="#d62728")
        if L is not None:
            ax.annotate(f"plazo de entrega ≈ {L:.1f} d", (t_pedido + (T - t_pedido) / 2, rop * 0.45),
                        ha="center", fontsize=8, color="#d62728")
    ax.set_ylim(0, nivel_max * 1.12)
    ax.set_xlabel("Tiempo (días laborales)")
    ax.set_ylabel("Unidades en inventario")
    ax.set_title(figura.titulo)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    return fig
