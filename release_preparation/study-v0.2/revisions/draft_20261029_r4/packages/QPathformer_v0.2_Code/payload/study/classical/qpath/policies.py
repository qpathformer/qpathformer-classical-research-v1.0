"""Internal Q-Pathformer policy primitives; no network or provider operations.

These helpers implement bounded policy contracts. They do not constitute a
validated continual-learning experiment or choose its pending task sequence.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import math
import random
import unicodedata
from typing import Any, Mapping, Sequence


RATING_NAMES = ("validity", "provenance_completeness", "task_relevance", "annotation_consistency")
ROUTE_KEY_VERSION = "qpf-text-route-v1"


@dataclass(frozen=True)
class PriorityAssessment:
    score: float | None
    processing_class: int
    provisional: bool
    reason: str


def assess_priority(ratings: Mapping[str, float | None], evidence: Mapping[str, str | None]) -> PriorityAssessment:
    """A numeric score requires every rating AND every associated evidence ID."""
    for name in RATING_NAMES:
        value = ratings.get(name)
        if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
            raise ValueError(f"Rating {name} must be finite and in [0, 1]")
    missing = [name for name in RATING_NAMES if ratings.get(name) is None or not evidence.get(name)]
    if missing:
        return PriorityAssessment(None, 8, True, "Incomplete rating/evidence: " + ", ".join(missing))
    score = sum(float(ratings[name]) for name in RATING_NAMES) / 4
    processing_class = max(1, min(8, 8 - math.floor(score * 8)))
    return PriorityAssessment(score, processing_class, False, "All four ratings and evidence IDs present")


def class_budget_probabilities(classes: Sequence[int]) -> list[float]:
    """P(i)=1/(2N)+(9-c_i)/(2 W n_c), over nonempty processing classes."""
    if not classes:
        raise ValueError("Empty source pool terminates a round")
    if any(isinstance(c, bool) or c not in range(1, 9) for c in classes):
        raise ValueError("Processing classes must be integers 1..8")
    counts = {c: classes.count(c) for c in set(classes)}
    weight_sum = sum(9 - c for c in counts)
    size = len(classes)
    return [1 / (2 * size) + (9 - c) / (2 * weight_sum * counts[c]) for c in classes]


def learning_rate(update: int, horizon: int, warmup: int, peak: float = 3e-4) -> float:
    """One-based, phase-local schedule. An early stop never rescales horizon."""
    if not (0 < warmup < horizon and 1 <= update <= horizon and peak > 0):
        raise ValueError("Require 0 < warmup < horizon, 1 <= update <= horizon, peak > 0")
    if update <= warmup:
        return peak * update / warmup
    return peak * (1 + math.cos(math.pi * (update - warmup) / (horizon - warmup))) / 2


def canonical_route_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("Inference text must be a string")
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def stable_text_route(text: str, seed: int, probabilities: Sequence[float]) -> int:
    """Hash the full text BEFORE token truncation, without record IDs or labels.

    Integer/rational comparison avoids rounding SHA-256 to a double. The final
    CDF boundary is exactly one; probabilities are frozen training estimates.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("Route seed must be a nonnegative integer")
    if not probabilities or any(not math.isfinite(p) or p < 0 for p in probabilities):
        raise ValueError("Route probabilities must be finite and nonnegative")
    if not math.isclose(sum(probabilities), 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError("Route probabilities must sum to one")
    canonical = canonical_route_text(text)
    if not canonical:
        raise ValueError("Empty post-validation input")
    digest = hashlib.sha256(str(seed).encode("ascii") + b"\x00" + canonical.encode("utf-8")).digest()
    position = Fraction(int.from_bytes(digest, "big"), 1 << 256)
    cumulative = Fraction(0)
    for index, probability in enumerate(probabilities):
        cumulative = Fraction(1) if index == len(probabilities) - 1 else cumulative + Fraction.from_float(float(probability))
        if position < cumulative:
            return index
    raise AssertionError("A valid CDF must select a route")


def draw_adaptation_sources(new_count: int, replay_count: int, batch_size: int, rng: random.Random) -> list[str]:
    """An empty new pool ends the episode; replay remains fixed during a candidate."""
    if min(new_count, replay_count, batch_size) < 0:
        raise ValueError("Counts must be nonnegative")
    if new_count == 0:
        return []
    if replay_count == 0:
        return ["new"] * batch_size
    return ["replay" if rng.random() < 0.2 else "new" for _ in range(batch_size)]


@dataclass(frozen=True)
class ReplayRecord:
    record_id: str
    label: str
    split: str = "train"
    eligible: bool = True
    parent_ids: tuple[str, ...] = ()


class ReplayBuffer:
    """Unique-ID, fixed-label, per-label reservoir with unused quotas left unused.

    `stage` returns a separate candidate buffer. Only the caller's accepted-state
    commit can replace the original. Seen IDs include records not retained by the
    reservoir, so repeated training draws cannot inflate admission counts.
    """

    def __init__(self, labels: Sequence[str], capacity: int = 2000, seed: int = 101):
        labels = sorted(set(labels))
        if not labels or capacity < 0:
            raise ValueError("A fixed nonempty label universe and nonnegative capacity are required")
        self.capacity = capacity
        quotient, remainder = divmod(capacity, len(labels))
        self.quotas = {label: quotient + (i < remainder) for i, label in enumerate(labels)}
        self.records: dict[str, list[ReplayRecord]] = {label: [] for label in labels}
        self.seen_ids: set[str] = set()
        self.seen_counts = {label: 0 for label in labels}
        self.seed = seed
        self.label_seeds = {
            label: int.from_bytes(hashlib.sha256(f"{seed}\0{label}".encode()).digest()[:8], "big")
            for label in labels
        }
        self.rngs = {label: random.Random(value) for label, value in self.label_seeds.items()}

    def admit(self, records: Sequence[ReplayRecord]) -> dict[str, Any]:
        """Admit to THIS object. Use only for an initial accepted state or a staged clone."""
        summary: dict[str, Any] = {"unique_eligible_considered": 0, "rejected": []}
        for record in sorted(records, key=lambda item: item.record_id):
            reason = None
            if not record.record_id:
                reason = "missing_id"
            elif record.record_id in self.seen_ids:
                reason = "duplicate_id"
            elif record.split != "train" or not record.eligible:
                reason = "not_eligible_training_record"
            elif record.label not in self.quotas:
                reason = "outside_frozen_label_universe"
            if reason:
                summary["rejected"].append({"record_id": record.record_id, "reason": reason})
                continue
            self.seen_ids.add(record.record_id)
            self.seen_counts[record.label] += 1
            summary["unique_eligible_considered"] += 1
            quota = self.quotas[record.label]
            bucket = self.records[record.label]
            if len(bucket) < quota:
                bucket.append(record)
            else:
                position = self.rngs[record.label].randrange(self.seen_counts[record.label])
                if position < quota:
                    bucket[position] = record
        return summary

    def stage(self, records: Sequence[ReplayRecord]) -> tuple[ReplayBuffer, dict[str, Any]]:
        candidate = deepcopy(self)
        return candidate, candidate.admit(records)

    def ids(self) -> list[str]:
        return sorted(record.record_id for bucket in self.records.values() for record in bucket)


@dataclass
class EpisodeBudget:
    """Outside rollback snapshots: retry consumes the SAME aggregate allowance."""
    resource_cap_seconds: float
    max_updates: int = 2000
    max_attempts: int = 3
    updates_consumed: int = 0
    seconds_consumed: float = 0.0
    attempts_started: int = 0

    def __post_init__(self) -> None:
        if (isinstance(self.max_updates, bool) or not isinstance(self.max_updates, int) or self.max_updates < 1
                or isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int) or self.max_attempts < 1
                or self.resource_cap_seconds <= 0
                or not math.isfinite(self.resource_cap_seconds)):
            raise ValueError("Positive explicit budget caps are required")

    def start_attempt(self) -> int:
        if (self.attempts_started >= self.max_attempts or self.updates_consumed >= self.max_updates
                or self.seconds_consumed >= self.resource_cap_seconds):
            raise RuntimeError("Episode budget exhausted; rollback cannot replenish it")
        self.attempts_started += 1
        return self.attempts_started

    def charge(self, updates: int = 0, seconds: float = 0.0) -> None:
        if (isinstance(updates, bool) or not isinstance(updates, int) or updates < 0
                or seconds < 0 or not math.isfinite(seconds)):
            raise ValueError("Update charges must be nonnegative integers; time must be finite and nonnegative")
        if self.updates_consumed + updates > self.max_updates:
            raise RuntimeError("Update would exceed the aggregate episode cap")
        self.updates_consumed += updates
        self.seconds_consumed += seconds  # Record actual overruns; never conceal elapsed work.

    @property
    def checkpoint_eligible(self) -> bool:
        return self.updates_consumed <= self.max_updates and self.seconds_consumed <= self.resource_cap_seconds


SNAPSHOT_FIELDS = {
    "model", "tokenizer", "centroids", "policy", "replay", "optimizer", "scheduler", "config", "rng"
}


class CandidateTransaction:
    """In-memory full-state isolation helper, not a crash-safe persistence layer.

    The episode budget deliberately cannot enter this transaction. Production
    durable/atomic filesystem commits remain future work.
    """
    def __init__(self, accepted: Mapping[str, Any]):
        if not SNAPSHOT_FIELDS.issubset(accepted):
            raise ValueError("Accepted snapshot is incomplete: " + ", ".join(sorted(SNAPSHOT_FIELDS - set(accepted))))
        if set(accepted) != SNAPSHOT_FIELDS:
            raise ValueError("Snapshot permits only the declared state fields; episode budgets/counters stay outside")
        self._reject_episode_budget(accepted)
        self.accepted = deepcopy(dict(accepted))
        self.candidate = deepcopy(self.accepted)
        self.ledger: list[dict[str, Any]] = []

    @staticmethod
    def _reject_episode_budget(value: Any) -> None:
        if isinstance(value, EpisodeBudget):
            raise ValueError("EpisodeBudget objects cannot enter a rollback snapshot")
        if isinstance(value, Mapping):
            reserved = {"budget", "episode_budget", "episode_counters", "episode_counter", "updates_consumed",
                        "seconds_consumed", "attempts_started"}
            for key, item in value.items():
                if isinstance(key, str) and key.casefold() in reserved:
                    raise ValueError("Consumed episode budget/counters cannot enter a rollback snapshot")
                CandidateTransaction._reject_episode_budget(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                CandidateTransaction._reject_episode_budget(item)

    def reject(self, metrics: Mapping[str, Any]) -> None:
        self.ledger.append({"decision": "reject", "metrics": deepcopy(dict(metrics))})
        self.candidate = deepcopy(self.accepted)

    def accept(self, metrics: Mapping[str, Any]) -> None:
        if set(self.candidate) != SNAPSHOT_FIELDS:
            raise ValueError("Candidate snapshot fields changed; episode budgets/counters stay outside")
        self._reject_episode_budget(self.candidate)
        self.ledger.append({"decision": "accept", "metrics": deepcopy(dict(metrics))})
        self.accepted = deepcopy(self.candidate)
        self.candidate = deepcopy(self.accepted)
