"""Reservoir / stratified-reservoir sampling utilities (stdlib only).

Implements Algorithm R (Vitter, 1985) per stratum so that a bounded,
deterministic, single-pass sample can be drawn from a stream without
knowing the total row count in advance.
"""

from __future__ import annotations

import random
from typing import Dict, Hashable, List, Optional


class StratumReservoir:
    """Fixed-capacity reservoir for one stratum, filled via Algorithm R."""

    def __init__(self, capacity: int, seed: int):
        self.capacity = capacity
        self._rng = random.Random(seed)
        self._items: List[object] = []
        self._seen = 0

    def offer(self, item: object) -> None:
        self._seen += 1
        if len(self._items) < self.capacity:
            self._items.append(item)
        else:
            # Standard Algorithm R replacement step.
            j = self._rng.randint(0, self._seen - 1)
            if j < self.capacity:
                self._items[j] = item

    @property
    def items(self) -> List[object]:
        return self._items

    @property
    def seen(self) -> int:
        return self._seen


class StratifiedReservoirSampler:
    """Manages one StratumReservoir per stratum key, with a global fallback
    reservoir for any stratum not present in the pre-computed budget table
    (e.g. a value that appears in the stream but was capped/unknown at
    budget-computation time).
    """

    def __init__(
        self,
        stratum_budgets: Dict[str, int],
        seed_base: int,
        fallback_capacity: int = 0,
    ):
        self.seed_base = seed_base
        self._reservoirs: Dict[str, StratumReservoir] = {
            key: StratumReservoir(capacity=cap, seed=self._derive_seed(key))
            for key, cap in stratum_budgets.items()
        }
        self._fallback_capacity = fallback_capacity
        self._fallback: Optional[StratumReservoir] = (
            StratumReservoir(capacity=fallback_capacity, seed=self._derive_seed("__fallback__"))
            if fallback_capacity > 0
            else None
        )

    def _derive_seed(self, key: Hashable) -> int:
        # Deterministic per-stratum seed derived from a fixed base seed.
        return (self.seed_base * 1_000_003 + hash(str(key))) % (2 ** 31 - 1)

    def offer(self, stratum_key: str, item: object) -> None:
        reservoir = self._reservoirs.get(stratum_key)
        if reservoir is not None:
            reservoir.offer(item)
        elif self._fallback is not None:
            self._fallback.offer(item)

    def all_items(self) -> List[object]:
        result: List[object] = []
        for reservoir in self._reservoirs.values():
            result.extend(reservoir.items)
        if self._fallback is not None:
            result.extend(self._fallback.items)
        return result

    def stratum_summary(self) -> Dict[str, Dict[str, int]]:
        summary = {
            key: {"capacity": r.capacity, "seen": r.seen, "sampled": len(r.items)}
            for key, r in self._reservoirs.items()
        }
        if self._fallback is not None:
            summary["__fallback__"] = {
                "capacity": self._fallback.capacity,
                "seen": self._fallback.seen,
                "sampled": len(self._fallback.items),
            }
        return summary


def compute_proportional_budgets(
    stratum_counts: Dict[str, int], total_budget: int
) -> Dict[str, int]:
    """Allocate ``total_budget`` slots across strata proportional to their
    observed counts, guaranteeing every non-empty stratum gets >= 1 slot
    (when budget allows) and that budgets sum to at most ``total_budget``.
    """
    total_count = sum(stratum_counts.values())
    if total_count == 0:
        return {}

    raw_budgets = {
        key: (count / total_count) * total_budget for key, count in stratum_counts.items()
    }
    floored = {key: max(1, int(v)) if stratum_counts[key] > 0 else 0 for key, v in raw_budgets.items()}

    # Trim overallocation caused by the "at least 1" floor, largest strata
    # lose the surplus first (they can spare it proportionally more).
    overshoot = sum(floored.values()) - total_budget
    if overshoot > 0:
        for key in sorted(floored, key=lambda k: stratum_counts[k], reverse=True):
            if overshoot <= 0:
                break
            reducible = floored[key] - 1
            take = min(reducible, overshoot)
            floored[key] -= take
            overshoot -= take

    return floored
