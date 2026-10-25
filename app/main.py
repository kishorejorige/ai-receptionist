from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.config import load_clinic

app = FastAPI(title="AI Receptionist")

class ChatRequest(BaseModel):
    clinic_id: str = "demo_clinic"
    message: str

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/chat")
def chat(req: ChatRequest):
    try:
        clinic = load_clinic(req.clinic_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return {"reply": f"Hello! You've reached {clinic['name']}. (agent coming next)"}