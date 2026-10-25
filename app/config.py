import re
from pathlib import Path

import yaml

CLINICS_DIR = Path(__file__).resolve().parent.parent / "clinics"


def load_clinic(clinic_id: str) -> dict:
    # only simple names allowed, so nobody can read other files
    if not re.fullmatch(r"[a-z0-9_-]+", clinic_id):
        raise FileNotFoundError(clinic_id)
    path = CLINICS_DIR / f"{clinic_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(clinic_id)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)
