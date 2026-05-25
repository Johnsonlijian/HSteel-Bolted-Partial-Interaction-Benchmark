"""Generate Figure 1 for the JCSR submission package.

The schematic is programmatic artwork. It is not AI-generated and it is not a
scaled engineering drawing; its purpose is to show the mechanics object,
state variables, and evidence boundary of the reduced-order model.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle


OUT = Path(__file__).with_suffix(".png")

STEEL = "#d8dee7"
EDGE = "#334155"
LIGHT = "#f8fafc"
GRID = "#e5e7eb"
BLUE = "#2563eb"
RED = "#b91c1c"
GREEN = "#047857"
GOLD = "#b45309"


def add_panel_title(ax, label: str, title: str) -> None:
    ax.text(
        0.0,
        1.04,
        f"{label} {title}",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10.5,
        fontweight="bold",
        color=EDGE,
    )


def draw_h_limb(ax, x0: float, y0: float, h: float = 6.0) -> None:
    """Draw one simplified H-section limb in elevation."""
    flange_w = 1.2
    flange_t = 0.42
    web_w = 0.30
    ax.add_patch(Rectangle((x0 - flange_w / 2, y0), flange_w, flange_t, fc=STEEL, ec=EDGE, lw=1.25))
    ax.add_patch(Rectangle((x0 - web_w / 2, y0), web_w, h, fc=STEEL, ec=EDGE, lw=1.25))
    ax.add_patch(
        Rectangle((x0 - flange_w / 2, y0 + h - flange_t), flange_w, flange_t, fc=STEEL, ec=EDGE, lw=1.25)
    )


def callout(ax, text: str, xy: tuple[float, float], xytext: tuple[float, float], color: str = EDGE, fontsize: float = 8.5) -> None:
    ax.annotate(
        text,
        xy=xy,
        xytext=xytext,
        ha="left",
        va="center",
        fontsize=fontsize,
        color=color,
        arrowprops={
            "arrowstyle": "-|>",
            "lw": 1.1,
            "color": color,
            "shrinkA": 2,
            "shrinkB": 3,
            "connectionstyle": "arc3,rad=0.05",
        },
        bbox={"boxstyle": "round,pad=0.16", "fc": "white", "ec": "none", "alpha": 0.88},
    )


def draw_section_inset(ax) -> None:
    """Small plan/cross-section icon to clarify the built-up H-section object."""
    x0, y0 = 0.62, 5.75
    ax.add_patch(Rectangle((x0, y0), 1.45, 1.02, fc="white", ec="#cbd5e1", lw=0.8))
    ax.text(x0 + 0.08, y0 + 0.9, "cross-section", fontsize=6.8, color=EDGE, ha="left", va="top")

    def mini_h(cx: float) -> None:
        ax.add_patch(Rectangle((cx - 0.18, y0 + 0.20), 0.36, 0.07, fc=STEEL, ec=EDGE, lw=0.7))
        ax.add_patch(Rectangle((cx - 0.04, y0 + 0.20), 0.08, 0.50, fc=STEEL, ec=EDGE, lw=0.7))
        ax.add_patch(Rectangle((cx - 0.18, y0 + 0.63), 0.36, 0.07, fc=STEEL, ec=EDGE, lw=0.7))

    mini_h(x0 + 0.45)
    mini_h(x0 + 1.02)
    ax.plot([x0 + 0.735, x0 + 0.735], [y0 + 0.17, y0 + 0.75], ls="--", c="#64748b", lw=0.8)
    ax.text(x0 + 0.735, y0 + 0.07, "interface", fontsize=6.2, color="#64748b", ha="center")


def draw_member_panel(ax) -> None:
    ax.set_xlim(0, 8.6)
    ax.set_ylim(0, 7.4)
    ax.axis("off")
    add_panel_title(ax, "(a)", "Bolted built-up H-section member")

    # Fixed base and tip displacement show the member-scale boundary problem.
    ax.add_patch(Rectangle((1.05, 0.35), 6.45, 0.16, fc=EDGE, ec=EDGE, lw=0))
    for x in [1.25, 1.55, 1.85, 2.15, 2.45, 2.75, 3.05, 3.35, 3.65, 3.95, 4.25, 4.55, 4.85, 5.15, 5.45, 5.75, 6.05, 6.35, 6.65, 6.95]:
        ax.plot([x - 0.18, x], [0.16, 0.35], color=EDGE, lw=0.7)

    draw_h_limb(ax, 2.65, 0.55)
    draw_h_limb(ax, 5.35, 0.55)
    ax.text(2.65, 6.72, "limb A", ha="center", va="bottom", fontsize=7.8, color=EDGE)
    ax.text(5.35, 6.72, "limb B", ha="center", va="bottom", fontsize=7.8, color=EDGE)

    ax.add_patch(Rectangle((3.92, 0.78), 0.16, 5.54, fc="#e0f2fe", ec="none", alpha=0.55))
    ax.plot([4.0, 4.0], [0.78, 6.32], ls=(0, (4, 2)), lw=1.25, c="#64748b")
    callout(ax, "frictional\ninterface", (4.0, 5.86), (4.55, 6.24), EDGE, 8.0)

    # Bolt rows transfer shear across the interface; washers are drawn on both limbs.
    bolt_y = [1.75, 3.45, 5.15]
    for idx, y in enumerate(bolt_y, start=1):
        ax.plot([2.95, 5.05], [y, y], c=EDGE, lw=1.8, solid_capstyle="round")
        for x in (3.58, 4.42):
            ax.add_patch(Circle((x, y), 0.19, fc=LIGHT, ec=EDGE, lw=1.2))
            ax.add_patch(Circle((x, y), 0.055, fc=EDGE, ec=EDGE, lw=0))
        ax.text(5.12, y, f"row {idx}", ha="left", va="center", fontsize=8.2, color=EDGE)

    ax.add_patch(FancyArrowPatch((3.78, 4.52), (3.12, 4.52), arrowstyle="-|>", mutation_scale=13, lw=1.7, color=BLUE))
    ax.add_patch(FancyArrowPatch((4.22, 4.32), (4.88, 4.32), arrowstyle="-|>", mutation_scale=13, lw=1.7, color=BLUE))
    callout(ax, r"slip demand" + "\n" + r"$\Delta u_{b,i}$", (4.05, 4.43), (1.05, 4.75), BLUE, 8.1)

    ax.add_patch(FancyArrowPatch((3.78, 2.36), (3.18, 2.36), arrowstyle="-|>", mutation_scale=12, lw=1.7, color=RED))
    ax.add_patch(FancyArrowPatch((4.22, 2.18), (4.82, 2.18), arrowstyle="-|>", mutation_scale=12, lw=1.7, color=RED))
    callout(ax, r"friction capacity" + "\n" + r"$F_{y,i}=\mu q_{b,i}$", (4.02, 2.27), (0.82, 2.55), RED, 8.1)

    ax.add_patch(FancyArrowPatch((5.95, 6.48), (6.64, 6.48), arrowstyle="-|>", mutation_scale=16, lw=2.0, color=GOLD))
    ax.text(6.72, 6.48, r"member drift" + "\n" + r"$u_{\mathrm{tip}}$", va="center", ha="left", fontsize=8.5, color=GOLD)

    draw_section_inset(ax)

    ax.text(
        0.15,
        0.0,
        "Object: connection-scale preload loss is propagated to member-scale partial interaction.",
        ha="left",
        va="bottom",
        fontsize=8.8,
        color=EDGE,
    )


def draw_stick_slip_panel(ax) -> None:
    add_panel_title(ax, "(b)", "Row stick-slip law")
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)
    ax.spines[["right", "top"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(EDGE)
    ax.tick_params(axis="both", labelsize=8, colors=EDGE, length=3)
    ax.set_xlabel(r"slip coordinate $\Delta u_{b,i}$", fontsize=9.2)
    ax.set_ylabel(r"row force $F_i$", fontsize=9.2)
    ax.grid(True, color=GRID, lw=0.55)

    x1 = [-1.1, -0.33]
    y1 = [-0.72, -0.72]
    x2 = [-0.33, 0.33]
    y2 = [-0.72, 0.72]
    x3 = [0.33, 1.1]
    y3 = [0.72, 0.72]
    ax.plot(x1, y1, color=RED, lw=2.2)
    ax.plot(x2, y2, color=EDGE, lw=2.2)
    ax.plot(x3, y3, color=RED, lw=2.2)
    ax.axhline(0.72, color=RED, lw=0.9, ls="--")
    ax.axhline(-0.72, color=RED, lw=0.9, ls="--")
    ax.text(0.47, 0.79, r"$+\mu q_{b,i}$", fontsize=9, color=RED)
    ax.text(-1.05, -0.89, r"$-\mu q_{b,i}$", fontsize=9, color=RED)
    ax.text(-0.24, 0.15, "stick\nstiffness", fontsize=8.6, color=EDGE, ha="right")
    ax.text(0.58, 0.44, "sliding\nprojection", fontsize=8.6, color=RED, ha="left")

    ax.text(0.5, -0.25, "Friction capacity follows the current preload state.", transform=ax.transAxes, ha="center", va="top", fontsize=8.5, color=EDGE)


def draw_preload_panel(ax) -> None:
    add_panel_title(ax, "(c)", "Preload state and boundary")
    x = [0.0, 0.08, 0.18, 0.34, 0.52, 0.72, 0.88, 1.0]
    y_fit = [1.0, 0.93, 0.84, 0.71, 0.61, 0.53, 0.495, 0.489]
    y_lo = [1.0, 0.95, 0.89, 0.80, 0.70, 0.60, 0.53, 0.49]
    y_hi = [1.0, 0.91, 0.78, 0.62, 0.52, 0.49, 0.489, 0.489]

    ax.set_xlim(0, 1)
    ax.set_ylim(0.42, 1.04)
    ax.spines[["right", "top"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(EDGE)
    ax.tick_params(axis="both", labelsize=8, colors=EDGE, length=3)
    ax.set_xlabel(r"accumulated normalized work $\sum|\Delta W_{f,i}|$", fontsize=9.2)
    ax.set_ylabel(r"preload index $q_{b,i}$", fontsize=9.2)
    ax.grid(True, color=GRID, lw=0.55)
    ax.fill_between(x, y_hi, y_lo, color="#fee2e2", alpha=0.75, lw=0)
    ax.plot(x, y_fit, color=RED, lw=2.5, label="steel-bolt anchor")
    ax.axhline(0.48875, color="#64748b", lw=1.1, ls="--")
    ax.text(0.55, 0.505, r"$q_{b,\mathrm{residual}}$", fontsize=8.8, color="#475569")
    ax.text(
        0.05,
        0.455,
        r"$q_{b,i}^{n+1}=\max(q_{b,i}^n-\eta_\mathrm{dis}|\Delta W_{f,i}|,q_{b,\mathrm{residual}})$",
        fontsize=8.2,
        color=EDGE,
        bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.9},
    )

    # Evidence hierarchy as compact chips, not a workflow diagram.
    y0 = 0.86
    chips = [
        ("verified", GREEN, "analytical limits"),
        ("screening", GOLD, "90-case benchmark"),
        ("bounded", RED, "not design calibration"),
    ]
    for j, (tag, color, text) in enumerate(chips):
        yy = y0 - j * 0.09
        ax.add_patch(Rectangle((0.52, yy - 0.025), 0.20, 0.045, fc=color, ec=color, lw=0, alpha=0.88))
        ax.text(0.62, yy - 0.002, tag, color="white", fontsize=7.7, ha="center", va="center", fontweight="bold")
        ax.text(0.74, yy - 0.002, text, color=EDGE, fontsize=8.0, ha="left", va="center")


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "mathtext.fontset": "dejavusans",
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
        }
    )
    fig = plt.figure(figsize=(13.6, 7.2), dpi=180)
    gs = fig.add_gridspec(2, 3, width_ratios=[1.45, 1.0, 1.05], height_ratios=[1.0, 1.0], wspace=0.34, hspace=0.34)

    ax_member = fig.add_subplot(gs[:, 0])
    ax_law = fig.add_subplot(gs[0, 1])
    ax_state = fig.add_subplot(gs[0, 2])
    ax_boundary = fig.add_subplot(gs[1, 1:])
    ax_boundary.axis("off")

    draw_member_panel(ax_member)
    draw_stick_slip_panel(ax_law)
    draw_preload_panel(ax_state)

    ax_boundary.text(0.0, 0.86, "Evidence boundary used in this paper", fontsize=10.5, fontweight="bold", color=EDGE)
    blocks = [
        ("What is supported", "Internal mechanics; analytical limits; deterministic screening trends.", GREEN),
        ("What is bounded", "Thermal-cycling relaxation is a parameter anchor, not a universal law.", GOLD),
        ("What is not claimed", "Design resistance; measured row slip; bolt-level validation for H-section tests.", RED),
    ]
    for j, (head, body, color) in enumerate(blocks):
        x0 = 0.02 + j * 0.325
        ax_boundary.add_patch(Rectangle((x0, 0.18), 0.29, 0.52, fc="#ffffff", ec=color, lw=1.6))
        ax_boundary.add_patch(Rectangle((x0, 0.63), 0.29, 0.07, fc=color, ec=color, lw=0))
        ax_boundary.text(x0 + 0.145, 0.665, head, ha="center", va="center", fontsize=8.7, color="white", fontweight="bold")
        ax_boundary.text(x0 + 0.02, 0.55, textwrap.fill(body, width=24), ha="left", va="top", fontsize=8.1, color=EDGE, linespacing=1.28)
    ax_boundary.set_xlim(0, 1)
    ax_boundary.set_ylim(0, 1)

    fig.savefig(OUT, bbox_inches="tight", dpi=320)


if __name__ == "__main__":
    main()
