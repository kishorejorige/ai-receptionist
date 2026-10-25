from datetime import date, timedelta

import pytest

from app import db
from app.config import load_clinic
from app.tools import make_tools


@pytest.fixture
def clinic_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "receptionist.db")
    db.init_db()
    clinic = load_clinic("demo_clinic")
    return make_tools("demo_clinic", clinic)


def next_monday():
    days_until_monday = (7 - date.today().weekday()) % 7 or 7
    return date.today() + timedelta(days=days_until_monday)


def test_check_availability_rejects_invalid_and_past_dates(clinic_tools):
    check_availability = clinic_tools[0]

    assert "error" in check_availability("not-a-date")
    assert "past" in check_availability("2000-01-01")["error"]


def test_booking_and_availability(clinic_tools):
    check_availability, book_appointment, _ = clinic_tools
    day = next_monday().isoformat()

    available = check_availability(day)["free_slots"]
    assert available
    assert "09:00" in available

    booked = book_appointment(
        "Alex Patient", "+1 (234) 567-8901", "Consultation", day, "09:00"
    )
    assert booked == {
        "status": "booked",
        "day": day,
        "slot": "09:00",
        "treatment": "Consultation",
    }
    assert "09:00" not in check_availability(day)["free_slots"]


@pytest.mark.parametrize(
    ("name", "phone", "treatment", "slot", "expected_error"),
    [
        ("", "1234567890", "Consultation", "09:00", "valid name and phone"),
        ("Alex", "123", "Consultation", "09:00", "valid name and phone"),
        ("Alex", "1234567890", "Unknown", "09:00", "Unknown treatment"),
        ("Alex", "1234567890", "Consultation", "08:00", "not available"),
    ],
)
def test_booking_rejects_invalid_details(
    clinic_tools, name, phone, treatment, slot, expected_error
):
    _, book_appointment, _ = clinic_tools

    result = book_appointment(name, phone, treatment, next_monday().isoformat(), slot)

    assert expected_error in result["error"]


def test_save_lead_normalizes_phone_and_truncates_request(clinic_tools):
    _, _, save_lead = clinic_tools

    assert save_lead(" +1 (234) 567-8901 ", "Need a callback", " Alex ") == {
        "status": "saved"
    }
    lead = db.query("SELECT name, phone, request FROM leads")[0]
    assert lead == {
        "name": "Alex",
        "phone": "12345678901",
        "request": "Need a callback",
    }

    assert save_lead("123", "Question")["error"]
