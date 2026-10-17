from __future__ import annotations

from typing import Any

from ontology.canonicalizer import Canonicalizer


def _prf(predicted: set[str], expected: set[str]) -> dict[str, float]:
    true_positive = len(predicted & expected)
    precision = true_positive / len(predicted) if predicted else 1.0 if not expected else 0.0
    recall = true_positive / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def extraction_metrics(predictions: list[dict[str, Any]], labels: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for hard, label in ((True, "hard"), (False, "preferred")):
        expected = {str(row["skill_id"]) for row in labels if bool(row.get("hard_requirement", True)) is hard}
        predicted = {str(row["skill_id"]) for row in predictions if bool(row.get("hard_requirement", True)) is hard and row.get("skill_id")}
        output[label] = _prf(predicted, expected)
    return output


def canonicalization_metrics(cases: list[dict[str, str]]) -> dict[str, Any]:
    canonicalizer = Canonicalizer.from_default()
    methods: dict[str, dict[str, int]] = {}
    unresolved = 0
    correct = 0
    for case in cases:
        match = canonicalizer.canonicalize(case["text"])
        method = match.method
        bucket = methods.setdefault(method, {"correct": 0, "total": 0})
        bucket["total"] += 1
        is_correct = match.skill_id == case["expected_skill_id"]
        bucket["correct"] += int(is_correct)
        correct += int(is_correct)
        unresolved += int(method == "UNRESOLVED")
    for bucket in methods.values():
        bucket["accuracy"] = bucket["correct"] / bucket["total"] if bucket["total"] else 0
    return {
        "accuracy": correct / len(cases) if cases else 0,
        "by_method": methods,
        "unresolved_rate": unresolved / len(cases) if cases else 0,
        "case_count": len(cases),
    }


def gap_metrics(predicted: dict[str, str], expected: dict[str, str]) -> dict[str, Any]:
    classes = ["has", "partial", "missing"]
    confusion = {gold: {guess: 0 for guess in classes} for gold in classes}
    for skill_id in set(predicted) | set(expected):
        gold = expected.get(skill_id, "missing")
        guess = predicted.get(skill_id, "missing")
        if gold in classes and guess in classes:
            confusion[gold][guess] += 1
    f1s: list[float] = []
    for label in classes:
        tp = confusion[label][label]
        fp = sum(confusion[gold][label] for gold in classes if gold != label)
        fn = sum(confusion[label][guess] for guess in classes if guess != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    false_has = sum(confusion[gold]["has"] for gold in classes if gold != "has")
    actual_not_has = sum(sum(confusion[gold][guess] for guess in classes) for gold in classes if gold != "has")
    return {
        "confusion_matrix": confusion,
        "macro_f1": sum(f1s) / len(f1s),
        "false_has_rate": false_has / actual_not_has if actual_not_has else 0.0,
        "false_has_count": false_has,
    }


def resource_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    relevance: list[float] = []
    dead = 0
    checked = 0
    for item in items:
        resources = item.get("resources", [])[:5]
        expected = str(item.get("skill_id", "")).replace("-", " ").casefold()
        relevance.append(
            sum(1 for resource in resources if expected in (str(resource.get("title", "")) + " " + str(resource.get("url", ""))).replace("-", " ").casefold()) / 5
        )
        for resource in resources:
            status = resource.get("link_check_status", "unverified")
            if status in {"alive", "dead"}:
                checked += 1
                dead += int(status == "dead")
    return {
        "relevance_at_5": sum(relevance) / len(relevance) if relevance else 0.0,
        "dead_link_rate": dead / checked if checked else None,
        "links_checked": checked,
    }
