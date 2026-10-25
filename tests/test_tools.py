from datetime import date, timedelta
from unittest.mock import Mock

import pytest

from app import db, tools
from app.config import load_clinic
from app.tools import make_tools


@pytest.fixture
def alert_sender(monkeypatch):
    sender = Mock()
    monkeypatch.setattr(tools, "send_owner_booking_alert", sender)
    return sender


@pytest.fixture
def clinic_tools(tmp_path, monkeypatch, alert_sender):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "receptionist.db")
    db.init_db()
    clinic = load_clinic("demo_clinic")
    return make_tools("demo_clinic", clinic)


def next_monday():
    days_until_monday = (7 - date.today().weekday()) % 7 or 7
    return date.today() + timedelta(days=days_until_monday)


def next_sunday():
    days_until_sunday = (6 - date.today().weekday()) % 7 or 7
    return date.today() + timedelta(days=days_until_sunday)


def test_check_availability_rejects_invalid_and_past_dates(clinic_tools):
    check_availability = clinic_tools[0]

    assert "error" in check_availability("not-a-date")
    assert "past" in check_availability("2000-01-01")["error"]


def test_booking_and_availability(clinic_tools, alert_sender):
    check_availability, book_appointment, _ = clinic_tools
    day = next_monday().isoformat()

    available = check_availability(day)["free_slots"]
    assert available
    assert "10:00" in available
    assert "14:00" not in available
    assert "16:30" not in available
    assert "17:00" in available
    assert "20:30" in available
    assert "21:00" not in available

    booked = book_appointment(
        "Alex Patient", "+1 (234) 567-8901", "Consultation", day, "10:00"
    )
    assert booked == {
        "status": "booked",
        "day": day,
        "slot": "10:00",
        "treatment": "Consultation",
    }
    alert_sender.assert_called_once_with(
        "Smile Dental Clinic",
        "Alex Patient",
        "12345678901",
        "Consultation",
        day,
        "10:00",
    )
    assert "10:00" not in check_availability(day)["free_slots"]
    duplicate = book_appointment(
        "Another Patient", "+1 (234) 567-8902", "Consultation", day, "10:00"
    )
    assert "error" in duplicate
    alert_sender.assert_called_once()


def test_booking_reports_alert_failure_without_undoing_booking(
    clinic_tools, alert_sender
):
    _, book_appointment, _ = clinic_tools
    alert_sender.side_effect = OSError("SMTP unavailable")

    result = book_appointment(
        "Alex Patient",
        "1234567890",
        "Consultation",
        next_monday().isoformat(),
        "10:00",
    )

    assert result["status"] == "booked"
    assert "notification email could not be sent" in result["alert_warning"]


def test_appointment_only_sunday_has_no_slots_and_lists_phone_numbers(clinic_tools):
    check_availability, _, _ = clinic_tools

    result = check_availability(next_sunday().isoformat())

    assert result["free_slots"] == []
    assert "appointment-only" in result["note"].lower()
    assert "9000000001" in result["note"]
    assert "9000000002" in result["note"]


def test_booking_on_appointment_only_sunday_is_refused(clinic_tools):
    _, book_appointment, _ = clinic_tools

    result = book_appointment(
        "Alex Patient",
        "+1 (234) 567-8901",
        "Consultation",
        next_sunday().isoformat(),
        "10:00",
    )

    assert "error" in result


@pytest.mark.parametrize(
    ("name", "phone", "treatment", "slot", "expected_error"),
    [
        ("", "1234567890", "Consultation", "09:00", "valid name and phone"),
        ("Alex", "123", "Consultation", "09:00", "valid name and phone"),
        ("Alex", "1234567890", "Unknown", "09:00", "Unknown treatment"),
        ("Alex", "1234567890", "Consultation", "08:00", "not available"),
        ("Alex", "1234567890", "Consultation", "16:30", "not available"),
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
