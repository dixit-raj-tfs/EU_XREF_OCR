#!/usr/bin/env python3
"""Sample complete FP_NUMBER groups by leaf node and description length."""

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path


LENGTH_LABELS = ("1-25", "26-50", "51-100", "101-200", "201+")


def length_band(description):
    size = len(description or "")
    if size <= 25:
        return 0
    if size <= 50:
        return 1
    if size <= 100:
        return 2
    if size <= 200:
        return 3
    return 4


def subset_for_sum(candidates, target, sizes, rng):
    """Find whole groups whose row counts sum exactly to target."""
    candidates = list(candidates)
    rng.shuffle(candidates)
    choices = {0: ()}
    for fp in candidates:
        size = sizes[fp]
        if size > target:
            continue
        for subtotal in sorted(tuple(choices), reverse=True):
            new_total = subtotal + size
            if new_total <= target and new_total not in choices:
                choices[new_total] = choices[subtotal] + (fp,)
        if target in choices:
            return choices[target]
    raise RuntimeError(f"Could not make an exact whole-group adjustment of {target} rows")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    fp_sizes = Counter()
    fp_leaf = {}
    fp_band_counts = defaultdict(Counter)
    leaf_rows = Counter()
    source_bands = Counter()
    excluded = 0

    with args.input.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"fp_number", "fp_leaf_node_id", "ip_description"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"Input must contain columns: {sorted(required)}")
        for row in reader:
            leaf = (row["fp_leaf_node_id"] or "").strip()
            if not leaf or leaf.upper() == "NULL":
                excluded += 1
                continue
            fp = row["fp_number"]
            band = length_band(row["ip_description"])
            fp_sizes[fp] += 1
            fp_band_counts[fp][band] += 1
            leaf_rows[leaf] += 1
            source_bands[band] += 1
            previous = fp_leaf.setdefault(fp, leaf)
            if previous != leaf:
                raise ValueError(f"FP_NUMBER {fp!r} spans multiple leaf nodes")

    eligible_rows = sum(fp_sizes.values())
    if args.rows > eligible_rows:
        raise ValueError(f"Requested {args.rows} rows but only {eligible_rows} are eligible")

    fp_band = {
        fp: max(counts, key=lambda band: (counts[band], -band))
        for fp, counts in fp_band_counts.items()
    }
    leaf_groups = defaultdict(list)
    strata = defaultdict(list)
    stratum_rows = Counter()
    for fp, size in fp_sizes.items():
        leaf = fp_leaf[fp]
        leaf_groups[leaf].append(fp)
        key = (leaf, fp_band[fp])
        strata[key].append(fp)
        stratum_rows[key] += size

    # Guarantee broad leaf coverage by reserving one randomly selected complete
    # group from every valid leaf before proportional allocation.
    mandatory = {rng.choice(groups) for groups in leaf_groups.values()}
    selected = set(mandatory)
    mandatory_by_stratum = Counter((fp_leaf[fp], fp_band[fp]) for fp in mandatory)
    mandatory_rows_by_stratum = Counter()
    for fp in mandatory:
        mandatory_rows_by_stratum[(fp_leaf[fp], fp_band[fp])] += fp_sizes[fp]

    # Within each leaf x dominant-length stratum, select shuffled whole groups
    # until the stratum is as close as possible to its proportional row target.
    for key, groups in strata.items():
        target = args.rows * stratum_rows[key] / eligible_rows
        running = mandatory_rows_by_stratum[key]
        available = [fp for fp in groups if fp not in mandatory]
        rng.shuffle(available)
        for fp in available:
            size = fp_sizes[fp]
            if abs(running + size - target) < abs(running - target):
                selected.add(fp)
                running += size

    current_rows = sum(fp_sizes[fp] for fp in selected)
    difference = args.rows - current_rows
    if difference > 0:
        pool = (fp for fp in fp_sizes if fp not in selected)
        selected.update(subset_for_sum(pool, difference, fp_sizes, rng))
    elif difference < 0:
        pool = (fp for fp in selected if fp not in mandatory)
        for fp in subset_for_sum(pool, -difference, fp_sizes, rng):
            selected.remove(fp)

    sample_leaf = Counter()
    sample_bands = Counter()
    written = 0
    with args.input.open(newline="", encoding="utf-8-sig") as source, args.output.open(
        "w", newline="", encoding="utf-8"
    ) as destination:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            leaf = (row["fp_leaf_node_id"] or "").strip()
            if leaf and leaf.upper() != "NULL" and row["fp_number"] in selected:
                writer.writerow(row)
                written += 1
                sample_leaf[leaf] += 1
                sample_bands[length_band(row["ip_description"])] += 1

    if written != args.rows:
        raise RuntimeError(f"Expected {args.rows} rows but wrote {written}")
    if set(sample_leaf) != set(leaf_rows):
        raise RuntimeError("The sample does not contain every valid leaf node")

    report_path = args.output.with_name(args.output.stem + "_distribution.csv")
    with report_path.open("w", newline="", encoding="utf-8") as report:
        writer = csv.writer(report)
        writer.writerow(("fp_leaf_node_id", "source_rows", "source_share", "sample_rows", "sample_share"))
        for leaf in sorted(leaf_rows, key=leaf_rows.get, reverse=True):
            writer.writerow(
                (
                    leaf,
                    leaf_rows[leaf],
                    leaf_rows[leaf] / eligible_rows,
                    sample_leaf[leaf],
                    sample_leaf[leaf] / written,
                )
            )

    print(f"Wrote {written:,} rows to {args.output}")
    print(f"Excluded {excluded:,} rows with blank/NULL leaf IDs")
    print(f"Selected {len(selected):,} complete FP_NUMBER groups")
    print(f"Represented all {len(sample_leaf):,} valid leaf IDs")
    print(f"Distribution report: {report_path}")
    print("description_band,source_share,sample_share")
    for band, label in enumerate(LENGTH_LABELS):
        print(f"{label},{source_bands[band] / eligible_rows:.6%},{sample_bands[band] / written:.6%}")


if __name__ == "__main__":
    main()
