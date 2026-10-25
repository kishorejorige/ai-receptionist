import pytest

from app.agent import build_system_prompt
from app.config import load_clinic


def test_load_demo_clinic():
    clinic = load_clinic("demo_clinic")

    assert clinic["name"] == "Smile Dental Clinic"
    assert clinic["timezone"] == "Asia/Kolkata"
    assert clinic["services"]
    assert clinic["sessions"] == [
        {"start": "10:00", "end": "14:00"},
        {"start": "17:00", "end": "21:00"},
    ]
    assert clinic["closed_days"] == []
    assert clinic["appointment_only_days"] == ["sun"]
    assert clinic["phones"] == ["9000000001", "9000000002"]


def test_system_prompt_includes_address_phones_and_optional_doctors():
    clinic = load_clinic("demo_clinic")

    prompt = build_system_prompt(clinic)
    assert f"Address: {clinic['address']}" in prompt
    assert "9000000001, 9000000002" in prompt
    assert "Doctors:\n- Dr. Mohd. Shafiq, Dental Surgeon (BDS)" in prompt
    assert "Dr. Rafeeq Mujtaba, Oral Health Educator" in prompt

    clinic_without_doctors = {key: value for key, value in clinic.items() if key != "doctors"}
    prompt_without_doctors = build_system_prompt(clinic_without_doctors)
    assert "Doctors:" not in prompt_without_doctors


@pytest.mark.parametrize("clinic_id", ["../secret", "clinic.yaml", "UpperCase"])
def test_load_clinic_rejects_invalid_id(clinic_id):
    with pytest.raises(FileNotFoundError):
        load_clinic(clinic_id)


def test_load_clinic_reports_missing_id():
    with pytest.raises(FileNotFoundError):
        load_clinic("missing_clinic")
