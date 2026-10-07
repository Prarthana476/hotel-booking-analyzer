"""Matplotlib charts. Each function returns a Figure so the GUI can embed or save it."""
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Patch

TYPE_COLOURS = {"Single": "#4C78A8", "Double": "#F58518", "Suite": "#54A24B"}


def _new(title):
    fig = Figure(figsize=(7, 4.3), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_title(title, fontsize=11, fontweight="bold")
    return fig, ax


def _no_data(fig, ax):
    ax.text(0.5, 0.5, "No data for this selection", ha="center", va="center", transform=ax.transAxes)
    ax.set_axis_off()
    return fig


def fig_monthly_occupancy(monthly, year):
    """Bars = occupancy % per month, line = revenue (seasonal demand)."""
    fig, ax = _new(f"Seasonal demand {year}: occupancy and revenue by month")
    ax.bar(monthly["month"], monthly["Occupancy rate (%)"], color="#4C78A8", label="Occupancy (%)")
    ax.set_ylabel("Occupancy (%)")
    ax.set_ylim(0, 100)
    ax2 = ax.twinx()
    ax2.plot(monthly["month"], monthly["Revenue"], color="#F58518", marker="o", label="Revenue")
    ax2.set_ylabel("Revenue")
    ax2.set_ylim(bottom=0)
    handles = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return fig


def fig_source_share(sources, label=""):
    """Pie chart of bookings by source."""
    fig, ax = _new(f"Booking sources {label}".strip())
    if sources.empty:
        return _no_data(fig, ax)
    ax.pie(sources["bookings"], labels=sources["source"], autopct="%1.0f%%",
           startangle=90, textprops={"fontsize": 8})
    ax.axis("equal")
    fig.tight_layout()
    return fig


def fig_room_usage(usage, label=""):
    """Occupancy % for each room, coloured by room type."""
    fig, ax = _new(f"Room usage {label}".strip())
    if usage.empty:
        return _no_data(fig, ax)
    ax.bar(usage["room_no"], usage["occupancy_pct"], color=[TYPE_COLOURS[t] for t in usage["room_type"]])
    ax.set_xlabel("Room")
    ax.set_ylabel("Occupancy (%)")
    ax.set_ylim(0, 100)
    ax.legend(handles=[Patch(color=c, label=t) for t, c in TYPE_COLOURS.items()], fontsize=8)
    fig.tight_layout()
    return fig


def fig_room_type_comparison(cmp, label_a="Period A", label_b="Period B"):
    """Grouped bars: occupancy % per room type in two periods."""
    fig, ax = _new("Occupancy by room type: period comparison")
    if cmp.empty:
        return _no_data(fig, ax)
    x = np.arange(len(cmp))
    ax.bar(x - 0.2, cmp["occ_a"], width=0.4, label=label_a, color="#4C78A8")
    ax.bar(x + 0.2, cmp["occ_b"], width=0.4, label=label_b, color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(cmp["room_type"])
    ax.set_ylabel("Occupancy (%)")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def save_figure(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
