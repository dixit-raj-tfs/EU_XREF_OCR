#!/usr/bin/env python3
"""Create a row-proportional, FP_NUMBER-group-preserving CSV sample."""

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path


def largest_remainder_targets(row_counts, sample_size):
    total = sum(row_counts.values())
    exact = {leaf: sample_size * count / total for leaf, count in row_counts.items()}
    targets = {leaf: int(value) for leaf, value in exact.items()}
    remainder = sample_size - sum(targets.values())
    ranked = sorted(exact, key=lambda leaf: (exact[leaf] - targets[leaf], row_counts[leaf]), reverse=True)
    for leaf in ranked[:remainder]:
        targets[leaf] += 1
    return exact, {leaf: count for leaf, count in targets.items() if count}


def attainable_group_selections(groups, limit, rng):
    """Return one random group selection for every attainable row sum <= limit."""
    groups = list(groups)
    rng.shuffle(groups)
    selections = {0: ()}
    for fp_number, size in groups:
        if size > limit:
            continue
        for old_sum in sorted(tuple(selections), reverse=True):
            new_sum = old_sum + size
            if new_sum <= limit and new_sum not in selections:
                selections[new_sum] = selections[old_sum] + (fp_number,)
        if len(selections) == limit + 1:
            break
    return selections


def choose_groups(groups_by_leaf, targets, sample_size, seed):
    rng = random.Random(seed)
    options = {}
    for leaf in targets:
        options[leaf] = attainable_group_selections(groups_by_leaf[leaf], sample_size, rng)

    # Multiple-choice knapsack: choose one attainable count per leaf, total exactly
    # sample_size, and minimize squared deviation from proportional integer quotas.
    states = {0: (0, ())}
    leaves = list(targets)
    for leaf in leaves:
        next_states = {}
        quota = targets[leaf]
        for running_total, (cost, choices) in states.items():
            for count in options[leaf]:
                new_total = running_total + count
                if new_total > sample_size:
                    continue
                candidate = (cost + (count - quota) ** 2, choices + (count,))
                if new_total not in next_states or candidate[0] < next_states[new_total][0]:
                    next_states[new_total] = candidate
        states = next_states

    if sample_size not in states:
        raise RuntimeError("No exact sample of the requested size can be formed from whole FP_NUMBER groups")

    _, chosen_counts = states[sample_size]
    selected = set()
    actual_by_leaf = {}
    for leaf, count in zip(leaves, chosen_counts):
        selected.update(options[leaf][count])
        if count:
            actual_by_leaf[leaf] = count
    return selected, actual_by_leaf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    fp_sizes = Counter()
    fp_leaf = {}
    leaf_rows = Counter()
    with args.input.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"fp_number", "fp_leaf_node_id"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"Input must contain columns: {sorted(required)}")
        for row in reader:
            fp = row["fp_number"]
            leaf = row["fp_leaf_node_id"]
            fp_sizes[fp] += 1
            leaf_rows[leaf] += 1
            previous = fp_leaf.setdefault(fp, leaf)
            if previous != leaf:
                raise ValueError(f"FP_NUMBER {fp!r} spans multiple leaf nodes")

    exact, targets = largest_remainder_targets(leaf_rows, args.rows)
    groups_by_leaf = defaultdict(list)
    for fp, size in fp_sizes.items():
        groups_by_leaf[fp_leaf[fp]].append((fp, size))

    selected, actual_by_leaf = choose_groups(groups_by_leaf, targets, args.rows, args.seed)

    written = 0
    with args.input.open(newline="", encoding="utf-8-sig") as source, args.output.open(
        "w", newline="", encoding="utf-8"
    ) as destination:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            if row["fp_number"] in selected:
                writer.writerow(row)
                written += 1

    if written != args.rows:
        raise RuntimeError(f"Expected {args.rows} rows but wrote {written}")

    print(f"Wrote {written} rows to {args.output}")
    print(f"Selected {len(selected)} complete FP_NUMBER groups across {len(actual_by_leaf)} leaf nodes")
    print("leaf_node,target_rows,actual_rows,source_share,sample_share")
    for leaf in sorted(actual_by_leaf, key=actual_by_leaf.get, reverse=True):
        print(
            f"{leaf},{exact[leaf]:.3f},{actual_by_leaf[leaf]},"
            f"{leaf_rows[leaf] / sum(leaf_rows.values()):.6%},{actual_by_leaf[leaf] / written:.6%}"
        )


if __name__ == "__main__":
    main()
