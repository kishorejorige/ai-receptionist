import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agent import create_chat
from app.config import load_clinic
from app.db import init_db

logger = logging.getLogger("receptionist")
sessions: dict = {}


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Receptionist", lifespan=lifespan)


class ChatRequest(BaseModel):
    clinic_id: str = "demo_clinic"
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1000)


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        clinic = load_clinic(req.clinic_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Clinic not found")
    key = f"{req.clinic_id}:{req.session_id}"
    try:
        if key not in sessions:
            sessions[key] = create_chat(req.clinic_id, clinic)
        response = sessions[key].send_message(req.message)
    except Exception:
        logger.exception("Gemini request failed")
        raise HTTPException(
            status_code=503, detail="The assistant is busy. Please try again shortly."
        )
    return {"reply": response.text or "Sorry, could you rephrase that?"}
