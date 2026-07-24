from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="WeaveAhead Engine",
    description="Backend AI companion for Indian handloom weavers (Team Tantunidhi)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- DATA MODELS ---

class PastOrder(BaseModel):
    item_name: str
    quantity: int
    month: str

class ForecastRequest(BaseModel):
    weaver_id: str = "WVR-HH26510"
    target_month: str = "October"
    language: str = "Odia"

class ProductionRecommendation(BaseModel):
    item: str
    suggested_quantity: int
    target_date: str
    confidence_score: float
    rationale: str
    voice_transcript: str

class ForecastResponse(BaseModel):
    team_uid: str = "HH26510"
    team_name: str = "Tantunidhi"
    institute: str = "ITER (Siksha 'O' Anusandhan), Bhubaneswar"
    theme: str = "Weaver Livelihoods & Financial Inclusion"
    problem_stat: dict
    target_month: str
    language: str
    recommendations: List[ProductionRecommendation]
    buyer_opportunities: List[str]

# --- DOMAIN DATA ---

FESTIVAL_CALENDAR = {
    "October": "Durga Puja & Festive Preparation",
    "November": "Peak Wedding Season & Bali Yatra",
    "December": "Winter Apparel & Corporate Year-End Gifting",
    "January": "Makar Sankranti & Regional Harvest Festivals"
}

PRODUCT_RULES = [
    {
        "item": "Sambalpuri Festive Saree",
        "base_qty": 18,
        "multipliers": {"October": 2.2, "November": 2.5, "December": 1.4, "January": 1.2},
        "reason": "Wedding & major festive surge demand"
    },
    {
        "item": "Tussar Silk Stole / Shawl",
        "base_qty": 25,
        "multipliers": {"October": 1.6, "November": 2.0, "December": 2.8, "January": 1.8},
        "reason": "Corporate gifting & winter apparel surge"
    },
    {
        "item": "Handloom Bags & Fabric Covers",
        "base_qty": 45,
        "multipliers": {"October": 1.5, "November": 1.8, "December": 2.2, "January": 1.4},
        "reason": "Bulk festive orders on GeM & state portals"
    },
    {
        "item": "Cotton Gamcha & Kitchen Towels",
        "base_qty": 60,
        "multipliers": {"October": 1.1, "November": 1.0, "December": 0.9, "January": 1.1},
        "reason": "Steady everyday utility product baseline"
    }
]

# --- ROUTES ---

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

@app.get("/api/v1/health")
async def health_check():
    return {"status": "online", "system": "WeaveAhead Engine"}

@app.post("/api/v1/forecast", response_model=ForecastResponse)
async def generate_forecast(req: ForecastRequest):
    month = req.target_month.capitalize()
    lang = req.language if req.language in ["Odia", "Hindi", "English"] else "Odia"
    
    event_context = FESTIVAL_CALENDAR.get(month, "Seasonal Baseline Demand")
    
    recommendations = []
    
    for rule in PRODUCT_RULES:
        mult = rule["multipliers"].get(month, 1.0)
        final_qty = int(rule["base_qty"] * mult)
        item_name = rule["item"]
        
        # Audio Transcripts in local regional languages
        if lang == "Odia":
            voice_txt = f"{month} ମାସ ପାଇଁ {final_qty} ଟି {item_name} ପ୍ରସ୍ତୁତ କରନ୍ତୁ। {event_context} ଯୋଗୁଁ ଆଗାମୀ ଦିନରେ ଚାହିଦା ବୃଦ୍ଧି ପାଇବ।"
        elif lang == "Hindi":
            voice_txt = f"{month} के लिए {final_qty} {item_name} तैयार करें। {event_context} के कारण मांग बढ़ने वाली है।"
        else:
            voice_txt = f"Plan to weave {final_qty} units of {item_name} for {month}. High demand expected due to {event_context}."
            
        recommendations.append(
            ProductionRecommendation(
                item=item_name,
                suggested_quantity=final_qty,
                target_date=f"20th {month}",
                confidence_score=min(0.98, round(0.85 + (mult * 0.04), 2)),
                rationale=f"{rule['reason']} ({event_context})",
                voice_transcript=voice_txt
            )
        )
        
    buyer_opportunities = [
        f"GeM Portal Bulk RFQ: 200 Silk Stoles for Corporate Gifting ({month})",
        f"State Portal (Boyanika) Stock Replenishment Drive",
        f"Handloom Saree & Wedding Cover Bulk Request for Upcoming Festive Season"
    ]
    
    problem_metrics = {
        "total_weavers": "35 Lakh+",
        "women_percentage": "72%",
        "below_5k_income": "67%",
        "core_issue": "Weaving blindly without demand visibility"
    }
    
    return ForecastResponse(
        target_month=month,
        language=lang,
        problem_stat=problem_metrics,
        recommendations=recommendations,
        buyer_opportunities=buyer_opportunities
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)