"""Is code frequency actually Pareto-distributed? CCDF diagnostic + tail fits.

For each variable (diag-code counts, drug-class counts):
  - empirical CCDF P(X >= x) on log-log (straight line <=> power law / Pareto tail)
  - power-law tail fit: Hill MLE alpha, x_min chosen by minimizing KS distance
    (light Clauset-Shalizi-Newman), requiring >=50 tail points
  - lognormal fit on all counts for comparison
Charts: data CCDF in entity color, power-law guide dashed, lognormal dotted.
"""

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from scipy import stats

from oscar_cs.db import connect_views
from oscar_cs.health_status import ANALYSIS_WINDOW_END, ANALYSIS_WINDOW_START
from oscar_cs.paths import FIGURES

OUT = FIGURES
SURFACE, INK, INK_2, MUTED, GRID, AXIS = (
    "#fcfcfb",
    "#0b0b0b",
    "#52514e",
    "#898781",
    "#e1e0d9",
    "#c3c2b7",
)
BLUE, AQUA = "#2a78d6", "#1baf7a"

sns.set_theme(
    style="whitegrid",
    rc={
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "grid.color": GRID,
        "axes.edgecolor": AXIS,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.titlecolor": INK,
        "font.size": 11,
        "axes.titlesize": 12.5,
        "figure.dpi": 150,
        "savefig.dpi": 150,
    },
)

con = connect_views()
W = {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END}
diag = (
    con.execute(
        """
select count(*) as n from claim_lines
where try_cast(date_svc as date) between $ws and $we
group by upper(trim(replace(diag1, '.', ''))) order by n desc
""",
        W,
    )
    .df()["n"]
    .to_numpy()
    .astype(float)
)
cls = (
    con.execute(
        """
select count(*) as n from prescription_drugs
where try_cast(date_svc as date) between $ws and $we
group by drug_class order by n desc
""",
        W,
    )
    .df()["n"]
    .to_numpy()
    .astype(float)
)


def ccdf(x):
    xs = np.sort(x)
    # P(X >= xs[i]) with ties handled: use position of first occurrence
    n = len(xs)
    vals, first_idx = np.unique(xs, return_index=True)
    p = 1.0 - first_idx / n
    return vals, p


def hill_fit(x, x_min):
    tail = x[x >= x_min]
    n = len(tail)
    alpha = 1.0 + n / np.sum(np.log(tail / x_min))
    # KS between empirical conditional CCDF and fitted (x/xmin)^-(alpha-1)
    vals, p = ccdf(tail)
    p_cond = p / p[0]
    fitted = (vals / x_min) ** (-(alpha - 1.0))
    ks = np.max(np.abs(p_cond - fitted))
    return alpha, n, ks


def best_tail(x):
    candidates = np.unique(x)
    out = []
    for xm in candidates:
        if (x >= xm).sum() < 50:
            break
        out.append((xm, *hill_fit(x, xm)))
    xm, alpha, n, ks = min(out, key=lambda t: t[3])
    return xm, alpha, n, ks


def plot_ccdf(x, color, name, unit, fname):
    xm, alpha, n_tail, ks = best_tail(x)
    mu, sigma = np.log(x).mean(), np.log(x).std()
    vals, p = ccdf(x)

    fig, ax = plt.subplots(figsize=(7.8, 4.8), layout="constrained")
    ax.plot(vals, p, color=color, lw=2.5, label=f"observed ({len(x):,} codes)")
    # lognormal guide over full range
    grid_x = np.logspace(0, np.log10(vals.max()), 200)
    ax.plot(
        grid_x,
        stats.norm.sf((np.log(grid_x) - mu) / sigma),
        color=MUTED,
        lw=1.8,
        ls=":",
        label=f"lognormal fit (μ={mu:.1f}, σ={sigma:.1f})",
    )
    # power-law guide over the fitted tail
    p_at_xm = p[np.searchsorted(vals, xm)]
    tail_x = np.logspace(np.log10(xm), np.log10(vals.max()), 50)
    ax.plot(
        tail_x,
        p_at_xm * (tail_x / xm) ** (-(alpha - 1.0)),
        color=INK_2,
        lw=1.8,
        ls="--",
        label=f"Pareto tail fit (α≈{alpha:.1f}, x≥{xm:.0f})",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title(f"{name}: is the tail a straight line?", loc="left")
    ax.set_xlabel(f"x = {unit} carrying a code (log)")
    ax.set_ylabel("share of codes with ≥ x (log CCDF)")
    leg = ax.legend(loc="lower left", fontsize=10, frameon=True, framealpha=1.0)
    leg.get_frame().set_facecolor(SURFACE)
    leg.get_frame().set_edgecolor(GRID)
    sns.despine(left=True, bottom=True)
    fig.savefig(OUT / ("2026-11-02_eda-session_" + fname))
    plt.close(fig)
    print(
        f"{name}: alpha={alpha:.2f}, x_min={xm:.0f}, tail codes={n_tail:,} "
        f"({100 * n_tail / len(x):.1f}% of codes), KS={ks:.3f}; "
        f"lognormal mu={mu:.2f} sigma={sigma:.2f}"
    )


plot_ccdf(diag, BLUE, "Diagnostic codes", "claim rows", "ccdf_diag_codes.png")
plot_ccdf(cls, AQUA, "Drug classes", "fills", "ccdf_drug_classes.png")
