"""Small, dependency-light evaluation helpers for agent quality reports."""

from statistics import mean
from typing import Any, Dict, Iterable, Mapping, Sequence


def extraction_field_metrics(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> Dict[str, float]:
    fields = set(expected.keys())
    if not fields:
        return {"field_accuracy": 0.0, "coverage": 0.0}

    present = {field for field in fields if observed.get(field) not in (None, "")}
    correct = {field for field in fields if observed.get(field) == expected.get(field)}

    return {
        "field_accuracy": len(correct) / len(fields),
        "coverage": len(present) / len(fields),
    }


def binary_classification_metrics(expected: Sequence[bool], observed: Sequence[bool]) -> Dict[str, float]:
    if len(expected) != len(observed):
        raise ValueError("expected and observed must have equal length")

    tp = sum(1 for e, o in zip(expected, observed) if e and o)
    tn = sum(1 for e, o in zip(expected, observed) if not e and not o)
    fp = sum(1 for e, o in zip(expected, observed) if not e and o)
    fn = sum(1 for e, o in zip(expected, observed) if e and not o)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(expected) if expected else 0.0

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_accept_rate": fp / (fp + tn) if fp + tn else 0.0,
        "false_reject_rate": fn / (fn + tp) if fn + tp else 0.0,
    }


def latency_summary(samples_ms: Iterable[float]) -> Dict[str, float]:
    values = sorted(float(v) for v in samples_ms)
    if not values:
        return {"count": 0.0, "avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}

    def percentile(p: float) -> float:
        index = min(len(values) - 1, max(0, round((len(values) - 1) * p)))
        return values[index]

    return {
        "count": float(len(values)),
        "avg_ms": mean(values),
        "p50_ms": percentile(0.50),
        "p95_ms": percentile(0.95),
    }
