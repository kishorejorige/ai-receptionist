import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import ollama
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from google.genai import errors as genai_errors
from pydantic import BaseModel, Field

from app.agent import create_chat, get_chat_provider_model
from app.config import load_clinic
from app.db import init_db

logger = logging.getLogger("receptionist")
sessions: dict[tuple[str, str, str, str], object] = {}
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Receptionist", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


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
    provider, model = get_chat_provider_model()
    key = (req.clinic_id, req.session_id, provider, model)
    try:
        if key not in sessions:
            sessions[key] = create_chat(req.clinic_id, clinic)
        response = sessions[key].send_message(req.message)
    except genai_errors.APIError as e:
        logger.error("Gemini API error %s: %s", e.code, e.message)
        status = 429 if e.code == 429 else 503
        raise HTTPException(status_code=status,
                            detail="The assistant is busy. Please try again shortly.")
    except ConnectionError:
        logger.error("Ollama connection refused or unavailable")
        raise HTTPException(
            status_code=503,
            detail="Ollama is unavailable. Check that the local server is running.",
        )
    except httpx.TimeoutException:
        logger.error("Ollama request timed out")
        raise HTTPException(
            status_code=503,
            detail="Ollama timed out. Please try again shortly.",
        )
    except ollama.ResponseError as e:
        error = e.error.lower()
        if e.status_code == 404 and "model" in error and "not found" in error:
            logger.error("Ollama model not found (HTTP %s)", e.status_code)
            detail = "The configured Ollama model was not found. Pull the model and try again."
        else:
            logger.error("Ollama server error (HTTP %s)", e.status_code)
            detail = "Ollama returned an error. Please try again shortly."
        raise HTTPException(status_code=503, detail=detail)
    except ollama.RequestError:
        logger.error("Ollama request failed")
        raise HTTPException(
            status_code=503,
            detail="Ollama request failed. Please try again shortly.",
        )
    except Exception:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail="Something went wrong.")
    return {"reply": response.text or "Sorry, could you rephrase that?"}
