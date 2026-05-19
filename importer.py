"""
Imports pupil data from:
  - Output xlsx  (sheet: Data)        → names, grades, existing comments
  - Input xlsx   (sheet: Pupil Data)  → names, grades, all scores, other fields

Calling import_from_files() with either or both returns a merged pupil list
ready to be stored as the class JSON.
"""
import io, re
import pandas as pd

# ── Grade normalisation ────────────────────────────────────────────────────────
_GRADE_MAP = {
    "D": "D", "GD": "D",
    "O": "O1", "O1": "O1", "O2": "O2",
    "Y": "Y",
    "A-Y2": "A - Y2", "A - Y2": "A - Y2",
    "A-Y3": "A - Y3", "A - Y3": "A - Y3",
}

def _norm_grade(v):
    v = str(v).strip().upper()
    return _GRADE_MAP.get(v, "O1") if v and v != "NAN" else "O1"

# ── Score field mapping (input xlsx column → internal key) ────────────────────
_INPUT_SCORE_COLS = {
    "Character (1-3)":    "char",
    "R&R (1-3)":          "randr",
    "Effort (1-3)":       "effort",
    "Oracy (1-3)":        "oracy",
    "Curiosity (1-3)":    "curio",
    "Resilience (1-3)":   "resil",
    "Independence (1-3)": "indep",
    "Collab (1-3)":       "collab",
    "History (1-3)":      "hist",
    "Geography (1-3)":    "geog",
    "Science (1-3)":      "sci",
    "Art (1-3)":          "art",
    "Sport/PE (1-3)":     "ath",
    "Citizenship (1-3)":  "cit",
    "Computing (1-3)":    "cs",
    "Design (1-3)":       "des",
    "Spanish (1-3)":      "ling",
    "Maths subj (1-3)":   "math_s",
    "Music (1-3)":        "mus",
    "Writing subj (1-3)": "write_s",
    "Reading eng (1-3)":  "read_e",
    "Times Tables (1-3)": "tt",
}

# All score keys (old + new)
_ALL_SCORE_KEYS = list(_INPUT_SCORE_COLS.values()) + [
    "m_calc", "m_reason", "m_prob", "m_frac",
    "w_comp", "w_spell", "w_punct", "w_vocab", "w_hand", "w_fic", "w_nonfic",
    "r_fluency", "r_retrieval", "r_inference", "r_vocab",
]

def blank_scores():
    return {k: None for k in _ALL_SCORE_KEYS}

def photo_filename(first, last):
    """firstname_lastname.jpg — lowercase, underscores, hyphens preserved in hyphenated names."""
    fn = re.sub(r"[^a-z0-9\-]", "_", first.lower().strip())
    ln = re.sub(r"[^a-z0-9\-]", "_", last.lower().strip())
    return f"{fn}_{ln}.jpg"

def _blank_pupil(i, fn, ln, gender="M"):
    return {
        "id": f"ch{i:02d}",
        "first_name": fn,
        "last_name": ln,
        "full_name": f"{fn} {ln}",
        "gender": gender,
        "photo": photo_filename(fn, ln),
        "grades": {"R": "O1", "W": "O1", "M": "O1"},
        "scores": blank_scores(),
        "other": "",
        "special": [],
        "attendance": "",
        "att_code": "",
        "punctuality": "",
        "punc_code": "",
        "pupil_voice": "",
        "comments": {
            "reader": "", "writer": "", "mathematician": "",
            "learner_21c": "", "rights": "",
        },
    }

def _str(v):
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


# ── Import from output xlsx ────────────────────────────────────────────────────
def from_output_xlsx(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="Data")
    pupils = []
    i = 1
    for _, row in df.iterrows():
        fn = _str(row.get("First Name", ""))
        ln = _str(row.get("Last Name", ""))
        if not fn:
            continue
        p = _blank_pupil(i, fn, ln)
        p["grades"] = {
            "R": _norm_grade(row.get("R", "O1")),
            "W": _norm_grade(row.get("W", "O1")),
            "M": _norm_grade(row.get("M", "O1")),
        }
        p["attendance"]  = _str(row.get("Attendance", ""))
        p["att_code"]    = _str(row.get("Att Code", ""))
        p["punctuality"] = _str(row.get("Punctuality (Lates) #", ""))
        p["punc_code"]   = _str(row.get("Punc Code", ""))
        p["pupil_voice"] = _str(row.get("Pupil Voice", ""))
        p["comments"] = {
            "reader":      _str(row.get("Reader Teacher comments", "")),
            "writer":      _str(row.get("Writer Teacher comments", "")),
            "mathematician": _str(row.get("Mathematician Teacher comments", "")),
            "learner_21c": _str(row.get("21st C learner Teacher comments", "")),
            "rights":      _str(row.get("Rights and Responsibilities Teacher comments", "")),
        }
        pupils.append(p)
        i += 1
    return pupils


# ── Import from input template xlsx ───────────────────────────────────────────
def from_input_xlsx(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="Pupil Data")
    pupils = []
    i = 1
    for _, row in df.iterrows():
        fn = _str(row.get("First Name", ""))
        ln = _str(row.get("Last Name", ""))
        if not fn:
            continue
        gender = _str(row.get("Gender (M/F)", "M")) or "M"
        p = _blank_pupil(i, fn, ln, gender)
        p["grades"] = {
            "R": _norm_grade(row.get("Reading", "O1")),
            "W": _norm_grade(row.get("Writing", "O1")),
            "M": _norm_grade(row.get("Maths",   "O1")),
        }
        for col_label, key in _INPUT_SCORE_COLS.items():
            v = row.get(col_label)
            try:
                p["scores"][key] = int(v) if pd.notna(v) else None
            except (ValueError, TypeError):
                p["scores"][key] = None
        p["other"]   = _str(row.get("Positive quality", ""))
        p["special"] = _str(row.get("Special flag", ""))
        pupils.append(p)
        i += 1
    return pupils


# ── Merge two lists by full_name ───────────────────────────────────────────────
def merge(base, overlay):
    """
    Merge overlay into base matching on full_name.
    overlay wins for: grades, gender, other, special, scores (non-None).
    base wins for: comments (don't overwrite manually edited comments with blanks).
    New pupils in overlay are appended.
    """
    base_map = {p["full_name"]: p for p in base}

    for o in overlay:
        key = o["full_name"]
        if key in base_map:
            b = base_map[key]
            # Grades: overlay wins if not default O1
            for g in ("R", "W", "M"):
                if o["grades"][g] != "O1" or b["grades"][g] == "O1":
                    b["grades"][g] = o["grades"][g]
            # Gender, other, special: overlay wins if non-empty
            for field in ("gender", "other", "special"):
                if o[field]:
                    b[field] = o[field]
            # Scores: overlay wins for non-None values
            for k, v in o["scores"].items():
                if v is not None:
                    b["scores"][k] = v
            # Comments: overlay wins only if base comment is empty
            for section, text in o["comments"].items():
                if text and not b["comments"].get(section):
                    b["comments"][section] = text
            # Attendance / pupil voice: overlay wins if non-empty
            for field in ("attendance", "att_code", "punctuality", "punc_code", "pupil_voice"):
                if o[field]:
                    b[field] = o[field]
        else:
            # New pupil — append
            base_map[key] = o

    # Return sorted by last name, reassigning IDs
    result = sorted(base_map.values(), key=lambda p: p["last_name"])
    for i, p in enumerate(result, 1):
        p["id"] = f"ch{i:02d}"
    return result


# ── Main entry point ───────────────────────────────────────────────────────────
def import_from_files(output_bytes=None, input_bytes=None, existing=None):
    """
    output_bytes : bytes from output xlsx upload (or None)
    input_bytes  : bytes from input template xlsx upload (or None)
    existing     : current class pupil list (or None / [])
    Returns merged pupil list.
    """
    base = existing or []

    if output_bytes:
        out_pupils = from_output_xlsx(output_bytes)
        base = merge(base, out_pupils)

    if input_bytes:
        in_pupils = from_input_xlsx(input_bytes)
        base = merge(base, in_pupils)

    return base
