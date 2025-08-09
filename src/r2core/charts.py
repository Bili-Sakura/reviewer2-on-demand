from __future__ import annotations

from pathlib import Path
from typing import Iterable, Dict, Any
import csv


def write_arm_means(rows: Iterable[Dict[str, Any]], out_csv: Path) -> None:
    by_arm: dict[str, dict[str, list[int]]] = {}
    for r in rows:
        arm = r.get("arm", "?")
        by_arm.setdefault(arm, {"helpfulness": [], "toxicity": [], "harshness": []})
        if isinstance(r.get("helpfulness_1to7"), int):
            by_arm[arm]["helpfulness"].append(r["helpfulness_1to7"])
        if isinstance(r.get("toxicity_1to7"), int):
            by_arm[arm]["toxicity"].append(r["toxicity_1to7"])
        if isinstance(r.get("harshness_1to7"), int):
            by_arm[arm]["harshness"].append(r["harshness_1to7"])

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arm", "mean_helpfulness", "mean_toxicity", "mean_harshness"]) 
        for arm, m in by_arm.items():
            def mean(xs: list[int]) -> float:
                return sum(xs) / len(xs) if xs else 0.0
            w.writerow([arm, f"{mean(m['helpfulness']):.3f}", f"{mean(m['toxicity']):.3f}", f"{mean(m['harshness']):.3f}"])
