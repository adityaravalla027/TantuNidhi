from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="WeaveAhead API",
    description="Multi-language, Voice-first, FastAPI-powered National Platform for Weavers & Cooperatives",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class TTSRequest(BaseModel):
    text: str
    language: str

class STTRequest(BaseModel):
    audio_url: str
    language: str

class TranslateRequest(BaseModel):
    text: str
    target_language: str

class CorporateOrderRequest(BaseModel):
    company_name: str
    craft_type: str
    region: str
    quantity: int
    deadline: str
    customization_notes: Optional[str] = None

class NotificationRequest(BaseModel):
    recipient_id: str
    channel: str  # sms, whatsapp, voice-call
    message: str

# --- In-Memory Mock Database ---
MOCK_CATALOGUE = [
    {"id": 1, "name": "Banarasi Silk Saree", "region": "Uttar Pradesh", "craft_type": "Banarasi", "price": 4500, "cooperative": "Varanasi Weavers Hub"},
    {"id": 2, "name": "Sambalpuri Ikat Saree", "region": "Odisha", "craft_type": "Ikat", "price": 3200, "cooperative": "Utkal Weaver Guild"},
    {"id": 3, "name": "Kanjeevaram Silk Saree", "region": "Tamil Nadu", "craft_type": "Kanjeevaram", "price": 6500, "cooperative": "Kanchi Artisans Coop"}
]

MOCK_ORDERS = {
    "weaver_001": [
        {"order_id": "ORD-101", "item": "Banarasi Silk", "quantity": 10, "status": "In Progress"},
        {"order_id": "ORD-102", "item": "Silk Stole", "quantity": 25, "status": "Ready"}
    ]
}

# --- Endpoints ---

@app.get("/forecast/{region}/{language}")
def get_forecast(region: str, language: str):
    """Provides translated, voice-ready demand forecast for a region[span_2](start_span)[span_2](end_span)."""
    forecast_text = f"Demand for {region} crafts is high this season. Prepare units locally."
    return {
        "region": region,
        "language": language,
        "forecast_raw": forecast_text,
        "voice_ready_audio_url": f"https://api.weaveahead.gov/audio/{region}_{language}.mp3"
    }

@app.post("/voice/tts")
def text_to_speech(payload: TTSRequest):
    """Converts weekly forecast text into a voice note[span_3](start_span)[span_3](end_span)."""
    return {"status": "success", "audio_url": "https://api.weaveahead.gov/generated_tts.mp3", "language": payload.language}

@app.post("/voice/stt")
def speech_to_text(payload: STTRequest):
    """Converts weaver voice input into status updates[span_4](start_span)[span_4](end_span)."""
    return {"status": "success", "transcribed_text": "order ready hai", "interpreted_intent": "mark_order_ready"}

@app.post("/translate")
def translate_text(payload: TranslateRequest):
    """Multi-language translation layer[span_5](start_span)[span_5](end_span)."""
    return {"original": payload.text, "translated": f"[{payload.target_language}] {payload.text}"}

@app.get("/weavers/{id}/orders")
def get_weaver_orders(id: str):
    """Order management for a specific weaver/cooperative[span_6](start_span)[span_6](end_span)."""
    if id not in MOCK_ORDERS:
        raise HTTPException(status_code=404, detail="Weaver not found")
    return {"weaver_id": id, "orders": MOCK_ORDERS[id]}

@app.get("/catalogue")
def get_catalogue(region: Optional[str] = None, craft_type: Optional[str] = None):
    """Buyer search / filter for regional crafts[span_7](start_span)[span_7](end_span)."""
    results = MOCK_CATALOGUE
    if region:
        results = [r for r in results if r["region"].lower() == region.lower()]
    if craft_type:
        results = [r for r in results if r["craft_type"].lower() == craft_type.lower()]
    return {"filters": {"region": region, "craft_type": craft_type}, "results": results}

@app.post("/corporate/order")
def submit_corporate_order(payload: CorporateOrderRequest, background_tasks: BackgroundTasks):
    """Bulk B2B order submission and automatic cluster matching[span_8](start_span)[span_8](end_span)."""
    background_tasks.add_task(print, f"Notifying cluster in {payload.region} for bulk order.")
    return {
        "status": "matched",
        "order_id": "CORP-9882",
        "matched_cluster": f"{payload.region} Primary Weaver Cooperative",
        "estimated_fulfillment": "30 days"
    }

@app.get("/inventory/{cooperative_id}")
def get_inventory(cooperative_id: str):
    """Stock tracking for raw materials and finished goods[span_9](start_span)[span_9](end_span)."""
    return {
        "cooperative_id": cooperative_id,
        "raw_materials": {"silk_yarn_kg": 120, "cotton_yarn_kg": 300},
        "finished_goods": 45
    }

@app.post("/notify/sms")
@app.post("/notify/whatsapp")
@app.post("/notify/voice-call")
def dispatch_notification(payload: NotificationRequest):
    """Multi-channel alert dispatch (SMS, WhatsApp, Voice Call)[span_10](start_span)[span_10](end_span)."""
    return {"status": "dispatched", "channel": payload.channel, "recipient": payload.recipient_id}
