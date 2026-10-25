import datetime as dt
import logging
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.tools import make_tools

logger = logging.getLogger("receptionist")
_client = None


def _get_client():
    global _client
    if _client is None:
        load_dotenv()
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=key)
    return _client


def build_system_prompt(clinic: dict) -> str:
    tz = ZoneInfo(clinic.get("timezone", "Asia/Kolkata"))
    now = dt.datetime.now(tz)
    services = "\n".join(
        f"- {s['name']}: {clinic['currency']} {s['price']}" for s in clinic["services"]
    )
    faqs = "\n".join(f"Q: {f['q']}\nA: {f['a']}" for f in clinic.get("faqs", []))
    return f"""You are the virtual receptionist for {clinic["name"]} ({clinic["location"]}).
Today is {now.strftime("%A, %Y-%m-%d")} and the time is {now.strftime("%H:%M")} ({clinic.get("timezone")}).

CLINIC INFORMATION (your only source of facts):
Hours: {clinic["hours_text"]}
Services and prices:
{services}
FAQs:
{faqs}

RULES:
- Answer only from the information above. Never invent prices, doctors, or policies.
- If you do not know, say so, ask for the patient's phone number, and use save_lead.
- Never give medical advice or diagnoses. Emergency (severe pain, bleeding, swelling): {clinic["emergency_note"]}
- To book: collect name, phone, treatment, and preferred date. Call check_availability first, offer the free slots, then repeat all details and wait for a clear yes before calling book_appointment.
- Never say a booking is done unless book_appointment returned status "booked".
- Keep replies short and friendly. Ask for one thing at a time.
- Reply in the patient's language when it is English, Telugu, or Hindi."""


def get_chat_provider_model() -> tuple[str, str]:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "ollama":
        return provider, os.getenv("OLLAMA_MODEL", "qwen3:4b")
    return "gemini", os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def create_chat(clinic_id: str, clinic: dict):
    provider, model = get_chat_provider_model()
    if provider == "ollama":
        from app.ollama_chat import OllamaChat

        logger.info("Creating chat with provider=%s model=%s", provider, model)
        return OllamaChat(
            build_system_prompt(clinic) + "\n/no_think",
            make_tools(clinic_id, clinic),
        )
    logger.info("Creating chat with provider=gemini model=%s", model)
    config = types.GenerateContentConfig(
        system_instruction=build_system_prompt(clinic),
        tools=make_tools(clinic_id, clinic),
        temperature=0.3,
    )
    return _get_client().chats.create(model=model, config=config)
