"""Plot runtime, speedup and efficiency from a completed scaling suite."""
import csv
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

path = Path(sys.argv[1])
with path.open(newline="") as f:
    rows = sorted(csv.DictReader(f), key=lambda row: int(row["threads"]))
threads = [int(row["threads"]) for row in rows]
if threads != [1, 2, 4, 8, 16, 24, 36]:
    raise ValueError("The full seven-thread-count scaling suite is required")
for key, label in (("median_s", "Runtime (s)"), ("speedup", "Speedup vs T=1"),
                   ("efficiency", "Parallel efficiency")):
    fig, ax = plt.subplots()
    values = [float(row[key]) for row in rows]
    if key == "median_s":
        low = [v - float(row["min_s"]) for v, row in zip(values, rows)]
        high = [float(row["max_s"]) - v for v, row in zip(values, rows)]
        ax.errorbar(threads, values, yerr=[low, high], fmt="o-", capsize=4)
    else:
        ax.plot(threads, values, "o-")
    ax.set(xlabel="OpenMP threads", ylabel=label, title="C CPU strong scaling, 256³, K=1000")
    ax.set_xticks(threads)
    fig.savefig(path.parent / f"scaling_{key}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
