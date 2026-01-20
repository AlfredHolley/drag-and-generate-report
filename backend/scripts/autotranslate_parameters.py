import json
import os
import re
import unicodedata
from typing import Dict, Any, Tuple


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _strip_accents(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)
    )


_PHRASE_MAP: Dict[str, str] = {
    # Common lab parameters / words
    "Hematíes": "Red Blood Cells",
    "Leucocitos": "White Blood Cells",
    "Plaquetas": "Platelets",
    "Hemoglobina": "Hemoglobin",
    "Hematocrito": "Hematocrit",
    "Neutrófilos": "Neutrophils",
    "Linfocitos": "Lymphocytes",
    "Monocitos": "Monocytes",
    "Eosinófilos": "Eosinophils",
    "Basófilos": "Basophils",
    "Neutrófilos %": "Neutrophils (%)",
    "Linfocitos %": "Lymphocytes (%)",
    "Monocitos %": "Monocytes (%)",
    "Eosinófilos %": "Eosinophils (%)",
    "Basófilos %": "Basophils (%)",
    "VSG 1ª hora": "ESR (1st hour)",
    "Tiempo de protrombina": "Prothrombin Time",
    "Actividad de Protrombina": "Prothrombin Activity",
    "Tiempo de tromboplastina parcial activado (cefalina) (APTT)": "Activated Partial Thromboplastin Time (aPTT)",
    "Ratio de cefalina (APTT)": "aPTT Ratio",
    "Fibrinógeno derivado": "Fibrinogen (derived)",
    "Dímero D": "D‑Dimer",
    "Glucosa (suero/plasma)": "Glucose (serum/plasma)",
    "Colesterol total": "Total Cholesterol",
    "Colesterol HDL": "HDL Cholesterol",
    "Colesterol LDL": "LDL Cholesterol",
    "Triglicéridos": "Triglycerides",
    "Creatinina": "Creatinine",
    "Urea": "Urea",
    "Sodio": "Sodium",
    "Potasio": "Potassium",
    "Cloruro": "Chloride",
    "Magnesio": "Magnesium",
    "Hierro": "Iron",
    "Transferrina": "Transferrin",
    "Ferritina": "Ferritin",
    "Calcio total": "Total Calcium",
    "Calcio iónico": "Ionized Calcium",
    "Fósforo (Fosfato)": "Phosphorus (phosphate)",
    "Proteínas totales": "Total Proteins",
    "Albúmina": "Albumin",
    "Proteína C Reactiva": "C‑Reactive Protein",
    "Proteína C Reactiva en suero (Ultrasensible)": "C‑Reactive Protein (high‑sensitivity)",
    "Bilirrubina total": "Total Bilirubin",
    "Bilirrubina directa (conjugada)": "Direct Bilirubin (conjugated)",
    "Bilirrubina indirecta": "Indirect Bilirubin",
    "Alanina aminotransferasa (ALT/GPT)": "Alanine Aminotransferase (ALT)",
    "Aspartato aminotransferasa (AST/GOT)": "Aspartate Aminotransferase (AST)",
    "Gamma-glutamil transferasa (GGT)": "Gamma‑Glutamyl Transferase (GGT)",
    "Fosfatasa alcalina ALP": "Alkaline Phosphatase (ALP)",
    "TSH": "Thyroid Stimulating Hormone (TSH)",
    "T4": "Thyroxine (T4)",
    "Cortisol": "Cortisol",
    "Vitamina B12": "Vitamin B12",
    "Vitamina D 25OH (calcidiol)": "Vitamin D (25‑OH)",
}


def _apply_generic_rules(s: str) -> str:
    original = s

    # Antibodies shorthand
    s = re.sub(r"^Ac\s+", "Antibody ", s)
    s = re.sub(r"\bAc\.\s*", "Antibody ", s)

    # Spanish specimen terms
    s = s.replace("suero/plasma", "serum/plasma")
    s = s.replace("en suero", "(serum)")
    s = s.replace("en sangre", "(blood)")

    # Some frequent words
    replacements = {
        "ultrasensible": "high‑sensitivity",
        "total": "total",
        "libre": "free",
        "por HPLC": "(HPLC)",
        "valor superior": "upper value",
        "estimado": "estimated",
        "Filtrado glomerular": "Estimated GFR",
        "Índice de saturación": "Saturation index",
        "Capacid total de fijación del hierro": "Total Iron Binding Capacity",
        "Grupo sanguíneo": "Blood group",
        "Factor Rh (D)": "Rh factor (D)",
        "Positivo": "Positive",
        "Negativo": "Negative",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)

    # Avoid non-breaking hyphen which some embedded fonts cannot render reliably
    s = s.replace("‑", "-")

    # Keep percent sign formatting consistent
    s = s.replace(" %", " (%)") if s.endswith(" %") else s

    # If unchanged and it contains accents, at least normalize accents for readability in English UI
    if s == original:
        # e.g. "Ácido" becomes "Acido" (still Spanish but cleaner); we only do this when we truly cannot map
        s = _strip_accents(s)

    return s


def translate(spanish_name: str) -> str:
    if spanish_name in _PHRASE_MAP:
        return _PHRASE_MAP[spanish_name]
    return _apply_generic_rules(spanish_name)


def autotranslate_parameters(parameters_json_path: str) -> Tuple[int, int]:
    """
    Updates parameters.json in place:
      - Only updates entries where english_name is missing or equals the Spanish key.
      - Leaves existing curated translations untouched.
    Returns: (updated_count, total_count)
    """
    data = _load_json(parameters_json_path)
    updated = 0

    for spanish_key, meta in data.items():
        english_name = (meta or {}).get("english_name", "")
        if not english_name or english_name == spanish_key:
            new_english = translate(spanish_key)
            if new_english != english_name:
                data[spanish_key]["english_name"] = new_english
                updated += 1

    _write_json(parameters_json_path, data)
    return updated, len(data)


if __name__ == "__main__":
    root = _repo_root()
    path = os.path.join(root, "backend", "config", "parameters.json")
    updated, total = autotranslate_parameters(path)
    print(json.dumps({"updated": updated, "total": total, "path": path}, ensure_ascii=False, indent=2))

