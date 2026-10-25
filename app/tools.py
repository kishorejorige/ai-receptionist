import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from app import db

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _all_slots(clinic: dict, d: dt.date) -> list[str]:
    if DAYS[d.weekday()] in clinic.get("closed_days", []):
        return []
    open_t = dt.datetime.strptime(clinic["open_time"], "%H:%M")
    close_t = dt.datetime.strptime(clinic["close_time"], "%H:%M")
    step = dt.timedelta(minutes=clinic["slot_minutes"])
    slots, cur = [], open_t
    while cur + step <= close_t:
        slots.append(cur.strftime("%H:%M"))
        cur += step
    return slots


def make_tools(clinic_id: str, clinic: dict):
    tz = ZoneInfo(clinic.get("timezone", "Asia/Kolkata"))

    def _free_slots(d: dt.date) -> list[str]:
        now = dt.datetime.now(tz)
        taken = {
            r["slot"]
            for r in db.query(
                "SELECT slot FROM bookings WHERE clinic_id=? AND day=?",
                (clinic_id, d.isoformat()),
            )
        }
        free = [s for s in _all_slots(clinic, d) if s not in taken]
        if d == now.date():
            free = [s for s in free if s > now.strftime("%H:%M")]
        return free

    def _parse_day(day: str):
        try:
            d = dt.datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            return None, "Date must be in YYYY-MM-DD format."
        if d < dt.datetime.now(tz).date():
            return None, "That date is in the past."
        return d, None

    def check_availability(day: str) -> dict:
        """List the free appointment slots for one day.

        Args:
            day: The date to check, in YYYY-MM-DD format.
        """
        d, err = _parse_day(day)
        if err:
            return {"error": err}
        free = _free_slots(d)
        if not free:
            return {
                "day": day,
                "free_slots": [],
                "note": "No free slots (closed or fully booked).",
            }
        return {"day": day, "free_slots": free}

    def book_appointment(
        patient_name: str, phone: str, treatment: str, day: str, slot: str
    ) -> dict:
        """Book an appointment. Only call after the patient has confirmed
        all details and the slot was shown as free by check_availability.

        Args:
            patient_name: Full name of the patient.
            phone: Patient phone number.
            treatment: One of the clinic's service names.
            day: Date in YYYY-MM-DD format.
            slot: Start time in 24-hour HH:MM format, e.g. 14:30.
        """
        d, err = _parse_day(day)
        if err:
            return {"error": err}
        digits = "".join(c for c in phone if c.isdigit())
        if not patient_name.strip() or len(digits) < 10:
            return {"error": "A valid name and phone number are required."}
        names = {s["name"].lower(): s["name"] for s in clinic["services"]}
        if treatment.lower() not in names:
            return {
                "error": "Unknown treatment.",
                "available_treatments": list(names.values()),
            }
        if slot not in _free_slots(d):
            return {
                "error": "That slot is not available.",
                "free_slots": _free_slots(d),
            }
        try:
            db.execute(
                "INSERT INTO bookings (clinic_id, patient_name, phone, treatment, day, slot) "
                "VALUES (?,?,?,?,?,?)",
                (
                    clinic_id,
                    patient_name.strip(),
                    digits,
                    names[treatment.lower()],
                    day,
                    slot,
                ),
            )
        except sqlite3.IntegrityError:
            return {"error": "That slot was just taken.", "free_slots": _free_slots(d)}
        return {
            "status": "booked",
            "day": day,
            "slot": slot,
            "treatment": names[treatment.lower()],
        }

    def save_lead(phone: str, request: str, name: str = "") -> dict:
        """Save contact details when the patient needs a callback or asks
        something you cannot answer from the clinic information.

        Args:
            phone: Patient phone number.
            request: Short summary of what the patient needs.
            name: Patient name, if known.
        """
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 10:
            return {"error": "A valid phone number is required."}
        db.execute(
            "INSERT INTO leads (clinic_id, name, phone, request) VALUES (?,?,?,?)",
            (clinic_id, name.strip(), digits, request.strip()[:500]),
        )
        return {"status": "saved"}

    return [check_availability, book_appointment, save_lead]
