import json
import os
from typing import Dict, Any, List, Set

import pandas as pd


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _extract_spanish_parameter_names(csv_path: str) -> List[str]:
    """
    Extract unique parameter names from the medical CSV format used by this project.
    Assumptions (based on `data.csv`):
      - row 0-1: metadata
      - row 2: headers (contains "Analisis", IDs, "Unidad")
      - row 3: dates
      - row 4+: data
      - parameter rows: first column empty, second column contains the Spanish parameter name
    """
    df = pd.read_csv(csv_path, header=None, encoding="utf-8")
    names: Set[str] = set()

    for i in range(4, len(df)):
        row = df.iloc[i]
        first_col = str(row.iloc[0]).strip()
        if first_col not in ("", "nan"):
            continue

        if len(row) < 2:
            continue
        name = str(row.iloc[1]).strip()
        if not name or name.lower() == "nan":
            continue

        names.add(name)

    return sorted(names, key=lambda s: s.lower())


def sync_parameters_json(
    csv_path: str,
    parameters_json_path: str,
) -> Dict[str, Any]:
    existing: Dict[str, Any] = _load_json(parameters_json_path)
    found_names = _extract_spanish_parameter_names(csv_path)

    added = 0
    for name in found_names:
        if name in existing:
            # Keep existing mapping verbatim.
            continue
        existing[name] = {
            "english_name": name,  # placeholder; you can refine later
            "category": "",
            "unit": "",
            "explanation": "",
        }
        added += 1

    _write_json(parameters_json_path, existing)
    return {
        "total_in_csv": len(found_names),
        "total_in_json": len(existing),
        "added": added,
        "csv_path": csv_path,
        "parameters_json_path": parameters_json_path,
    }


if __name__ == "__main__":
    root = _repo_root()
    summary = sync_parameters_json(
        csv_path=os.path.join(root, "data.csv"),
        parameters_json_path=os.path.join(root, "backend", "config", "parameters.json"),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))

