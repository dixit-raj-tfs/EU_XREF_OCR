#!/usr/bin/env python3
"""Plot leaf-node and description-length distributions for a sample."""

import argparse
import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def length_band(description):
    size = len(description or "")
    if size <= 25:
        return "1-25"
    if size <= 50:
        return "26-50"
    if size <= 100:
        return "51-100"
    if size <= 200:
        return "101-200"
    return "201+"


def profile(path, exclude_null_leaf):
    leaves = Counter()
    bands = Counter()
    with path.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            leaf = (row["fp_leaf_node_id"] or "").strip()
            if exclude_null_leaf and (not leaf or leaf.upper() == "NULL"):
                continue
            leaves[leaf] += 1
            bands[length_band(row["ip_description"])] += 1
    return leaves, bands


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("sample", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source_leaf, source_bands = profile(args.source, True)
    sample_leaf, sample_bands = profile(args.sample, False)
    source_total = sum(source_leaf.values())
    sample_total = sum(sample_leaf.values())
    ranked = sorted(source_leaf, key=source_leaf.get, reverse=True)

    fig, axes = plt.subplots(1, 3, figsize=(19, 6))

    top = ranked[:25][::-1]
    positions = range(len(top))
    axes[0].barh(
        [p - 0.2 for p in positions],
        [100 * source_leaf[leaf] / source_total for leaf in top],
        height=0.4,
        label="Eligible source",
    )
    axes[0].barh(
        [p + 0.2 for p in positions],
        [100 * sample_leaf[leaf] / sample_total for leaf in top],
        height=0.4,
        label="200k sample",
    )
    axes[0].set_yticks(list(positions), top, fontsize=8)
    axes[0].set_xlabel("Rows (%)")
    axes[0].set_title("Top 25 leaf-node IDs")
    axes[0].legend()

    ranks = range(1, len(ranked) + 1)
    axes[1].plot(ranks, [100 * source_leaf[x] / source_total for x in ranked], label="Eligible source")
    axes[1].plot(ranks, [100 * sample_leaf[x] / sample_total for x in ranked], label="200k sample", alpha=0.8)
    axes[1].set_yscale("log")
    axes[1].set_xlabel("Leaf-node rank in source")
    axes[1].set_ylabel("Rows (%) — log scale")
    axes[1].set_title(f"All {len(ranked):,} valid leaf-node IDs")
    axes[1].legend()

    labels = ("1-25", "26-50", "51-100", "101-200", "201+")
    x = list(range(len(labels)))
    axes[2].bar(
        [i - 0.2 for i in x],
        [100 * source_bands[label] / source_total for label in labels],
        width=0.4,
        label="Eligible source",
    )
    axes[2].bar(
        [i + 0.2 for i in x],
        [100 * sample_bands[label] / sample_total for label in labels],
        width=0.4,
        label="200k sample",
    )
    axes[2].set_xticks(x, labels, rotation=25)
    axes[2].set_xlabel("ip_description length (characters)")
    axes[2].set_ylabel("Rows (%)")
    axes[2].set_title("Description-length distribution")
    axes[2].legend()

    fig.suptitle("Grouped stratified sample validation", fontsize=15)
    fig.tight_layout()
    fig.savefig(args.output, dpi=180, bbox_inches="tight")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
