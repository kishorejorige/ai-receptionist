import pytest

from app.config import load_clinic


def test_load_demo_clinic():
    clinic = load_clinic("demo_clinic")

    assert clinic["name"] == "Smile Dental Clinic"
    assert clinic["timezone"] == "Asia/Kolkata"
    assert clinic["services"]


@pytest.mark.parametrize("clinic_id", ["../secret", "clinic.yaml", "UpperCase"])
def test_load_clinic_rejects_invalid_id(clinic_id):
    with pytest.raises(FileNotFoundError):
        load_clinic(clinic_id)


def test_load_clinic_reports_missing_id():
    with pytest.raises(FileNotFoundError):
        load_clinic("missing_clinic")
