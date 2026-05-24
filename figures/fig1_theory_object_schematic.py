"""Generate Figure 1 concept schematic for the Path-C manuscript.

The figure is intentionally conceptual: it shows the theory object and the
state variables, not a scaled engineering drawing.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle


OUT = Path(__file__).with_suffix(".png")


def draw_h_limb(ax, x0, y0, h=5.6, flange=1.15, web=0.32, color="#d9dde3"):
    """Draw a simplified H/I-section limb in elevation."""
    ax.add_patch(Rectangle((x0 - flange / 2, y0), flange, 0.42, fc=color, ec="#4a5568", lw=1.4))
    ax.add_patch(Rectangle((x0 - web / 2, y0), web, h, fc=color, ec="#4a5568", lw=1.4))
    ax.add_patch(Rectangle((x0 - flange / 2, y0 + h - 0.42), flange, 0.42, fc=color, ec="#4a5568", lw=1.4))


def main():
    fig, ax = plt.subplots(figsize=(10, 7), dpi=160)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")

    # Theory object: two H-section limbs connected by discrete bolt rows.
    draw_h_limb(ax, 3.65, 0.75)
    draw_h_limb(ax, 6.35, 0.75)
    ax.plot([5, 5], [0.85, 6.25], ls="--", lw=1.2, c="#64748b")
    ax.text(5, 6.45, "frictional interface", ha="center", va="bottom", fontsize=10, color="#334155")

    bolt_y = [2.0, 3.55, 5.1]
    for i, y in enumerate(bolt_y, start=1):
        ax.plot([4.05, 5.95], [y, y], c="#334155", lw=2.0)
        ax.add_patch(Circle((5.0, y), 0.18, fc="#f8fafc", ec="#334155", lw=1.5))
        ax.text(6.15, y, f"bolt row {i}", ha="left", va="center", fontsize=9, color="#334155")

    # Slip and friction arrows.
    ax.add_patch(FancyArrowPatch((4.65, 4.45), (4.05, 4.45), arrowstyle="-|>", mutation_scale=14, lw=1.8, color="#2563eb"))
    ax.add_patch(FancyArrowPatch((5.35, 4.25), (5.95, 4.25), arrowstyle="-|>", mutation_scale=14, lw=1.8, color="#2563eb"))
    ax.text(5.0, 4.68, r"inter-limb slip $\Delta u_b$", ha="center", fontsize=10, color="#1d4ed8")

    ax.add_patch(FancyArrowPatch((4.9, 2.55), (4.35, 2.55), arrowstyle="-|>", mutation_scale=14, lw=1.8, color="#b91c1c"))
    ax.add_patch(FancyArrowPatch((5.1, 2.35), (5.65, 2.35), arrowstyle="-|>", mutation_scale=14, lw=1.8, color="#b91c1c"))
    ax.text(5.0, 2.78, r"friction limit $F_y=\mu q_b$", ha="center", fontsize=10, color="#991b1b")

    ax.text(2.05, 6.35, "two built-up\nH-section limbs", ha="center", va="top", fontsize=10, color="#334155")
    ax.add_patch(FancyArrowPatch((2.35, 5.8), (3.2, 5.55), arrowstyle="-|>", mutation_scale=13, lw=1.2, color="#334155"))
    ax.add_patch(FancyArrowPatch((2.35, 5.45), (6.0, 5.55), arrowstyle="-|>", mutation_scale=13, lw=1.2, color="#334155"))

    # Inset: preload index decays toward a residual value with dissipation.
    inset = fig.add_axes([0.63, 0.13, 0.28, 0.25])
    x = [0, 0.15, 0.35, 0.6, 0.85, 1.0]
    y = [1.0, 0.86, 0.70, 0.58, 0.50, 0.49]
    inset.plot(x, y, c="#b91c1c", lw=2.2)
    inset.axhline(0.49, c="#64748b", ls="--", lw=1.0)
    inset.text(0.52, 0.515, r"$q_{b,res}$", fontsize=8, color="#475569")
    inset.set_xlabel(r"accumulated $W_f$", fontsize=8)
    inset.set_ylabel(r"$q_b(t)$", fontsize=8)
    inset.set_title("slow preload state", fontsize=9)
    inset.tick_params(labelsize=7)
    inset.set_xlim(0, 1)
    inset.set_ylim(0.42, 1.05)
    inset.grid(True, lw=0.4, alpha=0.35)

    ax.text(
        0.55,
        0.35,
        r"state update: $q_b \leftarrow \max(q_b-\eta_{dis}|\Delta W_f|, q_{b,res})$",
        ha="left",
        va="bottom",
        fontsize=10,
        color="#334155",
    )

    fig.savefig(OUT, bbox_inches="tight", dpi=300)


if __name__ == "__main__":
    main()
