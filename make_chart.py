"""Bar chart of plaintiff win rate by defendant type, from results.csv -> chart.png.

A "plaintiff win" means winner == "plaintiff"; "mixed" decisions count as not a win.

Usage:
    python make_chart.py
"""

import csv
from collections import Counter

import matplotlib.pyplot as plt

BAR = "#2a78d6"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"

with open("results.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

totals = Counter(r["defendant_type"] for r in rows)
wins = Counter(r["defendant_type"] for r in rows if r["winner"] == "plaintiff")
# Sort so the highest win rate is at the top of the horizontal bar chart
types = sorted(totals, key=lambda t: (wins[t] / totals[t], totals[t]))
rates = [100 * wins[t] / totals[t] for t in types]

fig, ax = plt.subplots(figsize=(8, 0.6 * len(types) + 1.6), dpi=150)
bars = ax.barh(types, rates, color=BAR, height=0.6)
for bar, t, rate in zip(bars, types, rates):
    ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
            f"{rate:.0f}%  ({wins[t]} of {totals[t]} cases)",
            va="center", fontsize=9, color=TEXT)

ax.set_xlim(0, 115)
ax.set_xticks(range(0, 101, 25))
ax.set_xticklabels([f"{x}%" for x in range(0, 101, 25)], color=MUTED, fontsize=9)
ax.tick_params(axis="y", colors=TEXT, labelsize=10, length=0)
ax.tick_params(axis="x", length=0)
ax.xaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(GRID)

ax.set_title("Plaintiff win rate by defendant type", loc="left",
             fontsize=13, color=TEXT, pad=22)
ax.text(0, 1.02, f"NY Appellate Division tort decisions, NYC, 2015–2025 (n={len(rows)}). "
        "Mixed outcomes not counted as wins.",
        transform=ax.transAxes, fontsize=8.5, color=MUTED)

fig.tight_layout()
fig.savefig("chart.png")
print(f"Saved chart.png ({len(rows)} cases)")
