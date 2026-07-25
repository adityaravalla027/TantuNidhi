"""
WeaveAhead — FastAPI Backend
=============================
pip install fastapi uvicorn pydantic --break-system-packages
uvicorn main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="WeaveAhead API",
    description="AI-powered demand forecasting and market linkage for handloom weavers.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # keep False while using allow_origins=["*"]; browsers reject wildcard+credentials
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- Enums ----------------

class CraftType(str, Enum):
    ikat = "Ikat"
    jamdani = "Jamdani"
    banarasi = "Banarasi"
    kanjeevaram = "Kanjeevaram"
    chanderi = "Chanderi"


class ProductCategory(str, Enum):
    saree = "Saree"
    stole = "Stole"
    home_furnishing = "Home Furnishing"
    daily_use = "Daily Use"
    wedding_card_cover = "Wedding Card Cover"
    greeting_card = "Greeting Card"
    corporate_gift = "Corporate Gift"


class OrderStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    in_progress = "in_progress"
    ready = "ready"
    delivered = "delivered"
    cancelled = "cancelled"


class NotifyChannel(str, Enum):
    sms = "sms"
    whatsapp = "whatsapp"
    voice_call = "voice_call"


class Language(str, Enum):
    hindi = "hi"
    english = "en"
    bengali = "bn"
    odia = "or"
    tamil = "ta"
    telugu = "te"
    gujarati = "gu"


# ---------------- Schemas ----------------

class Weaver(BaseModel):
    id: str
    name: str
    cooperative: str
    region: str
    state: str
    craft_type: CraftType
    looms: int
    avg_days_per_piece: float
    preferred_language: Language = Language.hindi
    phone: str


class ForecastItem(BaseModel):
    product_category: ProductCategory
    trending_design: str
    demand_index: int = Field(..., ge=0, le=100)
    recommended_quantity: int
    restock_raw_material_by: str


class Forecast(BaseModel):
    region: str
    week_of: str
    language: Language
    items: list[ForecastItem]
    voice_note_url: Optional[str] = None


class OrderItem(BaseModel):
    id: str
    weaver_id: str
    product_category: ProductCategory
    quantity: int
    status: OrderStatus
    buyer_name: str
    deadline: str
    created_at: str


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class Product(BaseModel):
    id: str
    name: str
    category: ProductCategory
    craft_type: CraftType
    region: str
    weaver_id: str
    weaver_name: str
    price_inr: int
    description: str
    in_stock: int


class InventoryItem(BaseModel):
    product_id: str
    product_name: str
    quantity_in_stock: int
    raw_material_stock_days: int


class CorporateOrderRequest(BaseModel):
    company_name: str
    contact_email: str
    product_category: ProductCategory
    quantity: int = Field(..., gt=0)
    customization_notes: Optional[str] = None
    deadline: str
    region_preference: Optional[str] = None


class CorporateOrderResponse(BaseModel):
    order_id: str
    matched_weaver_id: Optional[str]
    matched_cooperative: Optional[str]
    estimated_ready_date: Optional[str]
    status: str
    message: str


class NotifyRequest(BaseModel):
    weaver_id: str
    channel: NotifyChannel
    message: str


class TranslateRequest(BaseModel):
    text: str
    target_language: Language


class TTSRequest(BaseModel):
    text: str
    language: Language


class STTRequest(BaseModel):
    audio_base64: str
    language: Language


# ---------------- Mock DB ----------------

WEAVERS: dict[str, Weaver] = {}
ORDERS: dict[str, OrderItem] = {}
PRODUCTS: dict[str, Product] = {}
INVENTORY: dict[str, InventoryItem] = {}


def _seed_data() -> None:
    weaver_seed = [
        ("Meena Devi", "Sonepur Handloom Cooperative", "Sonepur", "Odisha", CraftType.ikat, 3, 6.0, Language.odia),
        ("Rajesh Yadav", "Varanasi Weavers Guild", "Varanasi", "Uttar Pradesh", CraftType.banarasi, 2, 10.0, Language.hindi),
        ("Lakshmi Narayanan", "Kanchipuram Silk Society", "Kanchipuram", "Tamil Nadu", CraftType.kanjeevaram, 4, 12.0, Language.tamil),
        ("Rupa Das", "Bengal Jamdani Cooperative", "Shantipur", "West Bengal", CraftType.jamdani, 3, 8.0, Language.bengali),
        ("Suresh Kori", "Chanderi Weavers Trust", "Chanderi", "Madhya Pradesh", CraftType.chanderi, 2, 5.0, Language.hindi),
    ]
    for name, coop, region, state, craft, looms, days, lang in weaver_seed:
        wid = str(uuid.uuid4())[:8]
        WEAVERS[wid] = Weaver(
            id=wid, name=name, cooperative=coop, region=region, state=state,
            craft_type=craft, looms=looms, avg_days_per_piece=days,
            preferred_language=lang, phone="+91XXXXXXXXXX",
        )

    product_seed = [
        ("Ikat Silk Saree", ProductCategory.saree, CraftType.ikat, 4500),
        ("Banarasi Zari Stole", ProductCategory.stole, CraftType.banarasi, 1800),
        ("Kanjeevaram Wedding Saree", ProductCategory.saree, CraftType.kanjeevaram, 9500),
        ("Handloom Cotton Kitchen Towel Set", ProductCategory.daily_use, CraftType.ikat, 650),
        ("Handloom Wedding Card Cover (per 100)", ProductCategory.wedding_card_cover, CraftType.jamdani, 3200),
        ("Handloom Greeting Card Pack (10)", ProductCategory.greeting_card, CraftType.chanderi, 450),
    ]
    # match each product to a weaver who actually works in that craft_type,
    # falling back to round-robin only if no matching weaver exists
    weavers_by_craft: dict[CraftType, list[Weaver]] = {}
    for w in WEAVERS.values():
        weavers_by_craft.setdefault(w.craft_type, []).append(w)
    all_weavers = list(WEAVERS.values())

    for i, (name, cat, craft, price) in enumerate(product_seed):
        pid = str(uuid.uuid4())[:8]
        pool = weavers_by_craft.get(craft) or all_weavers
        w = pool[i % len(pool)]
        PRODUCTS[pid] = Product(
            id=pid, name=name, category=cat, craft_type=craft, region=w.region,
            weaver_id=w.id, weaver_name=w.name, price_inr=price,
            description=f"Authentic {craft.value} handwoven by {w.name}, {w.cooperative}.",
            in_stock=random.randint(5, 40),
        )
        INVENTORY[pid] = InventoryItem(
            product_id=pid, product_name=name,
            quantity_in_stock=PRODUCTS[pid].in_stock,
            raw_material_stock_days=random.randint(3, 30),
        )

    order_seed_statuses = [OrderStatus.pending, OrderStatus.in_progress, OrderStatus.ready]
    for i, wid in enumerate(WEAVERS.keys()):
        oid = str(uuid.uuid4())[:8]
        ORDERS[oid] = OrderItem(
            id=oid, weaver_id=wid,
            product_category=random.choice(list(ProductCategory)),
            quantity=random.randint(5, 50),
            status=order_seed_statuses[i % len(order_seed_statuses)],
            buyer_name="Sample Buyer Pvt Ltd",
            deadline=(datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d"),
            created_at=datetime.now().strftime("%Y-%m-%d"),
        )


_seed_data()


# ---------------- Intelligence layer (mocked — swap for real models) ----------------

def generate_forecast(region: str, language: Language) -> Forecast:
    designs_by_category = {
        ProductCategory.saree: ["Ikat Butta", "Zari Border", "Temple Motif"],
        ProductCategory.stole: ["Geometric Ikat", "Floral Jamdani"],
        ProductCategory.home_furnishing: ["Checked Cotton", "Block Border"],
        ProductCategory.daily_use: ["Plain Weave Cotton"],
    }
    items = []
    for cat, designs in designs_by_category.items():
        items.append(
            ForecastItem(
                product_category=cat,
                trending_design=random.choice(designs),
                demand_index=random.randint(40, 95),
                recommended_quantity=random.randint(10, 100),
                restock_raw_material_by=(datetime.now() + timedelta(days=random.randint(3, 14))).strftime("%Y-%m-%d"),
            )
        )
    return Forecast(
        region=region,
        week_of=datetime.now().strftime("%Y-%m-%d"),
        language=language,
        items=items,
        voice_note_url=f"/static/voice-notes/{region.lower().replace(' ', '-')}-{language.value}.mp3",
    )


def translate_text(text: str, target_language: Language) -> str:
    return f"[{target_language.value}] {text}"


def text_to_speech(text: str, language: Language) -> str:
    return f"/static/voice-notes/{uuid.uuid4().hex[:8]}-{language.value}.mp3"


def speech_to_text(audio_base64: str, language: Language) -> str:
    return "order ready hai"


def match_weaver_for_corporate_order(req: CorporateOrderRequest) -> Optional[Weaver]:
    candidates = list(WEAVERS.values())
    if req.region_preference:
        region_matches = [w for w in candidates if req.region_preference.lower() in w.region.lower()]
        if region_matches:
            candidates = region_matches
    if not candidates:
        return None
    return max(candidates, key=lambda w: w.looms)


# ---------------- Routes: Forecast ----------------

@app.get("/api/forecast/{region}", response_model=Forecast, tags=["Forecast"])
def get_forecast(region: str, language: Language = Query(default=Language.hindi)):
    return generate_forecast(region=region, language=language)


# ---------------- Routes: Voice / Language ----------------

@app.post("/api/translate", tags=["Voice & Language"])
def translate(req: TranslateRequest):
    return {"translated_text": translate_text(req.text, req.target_language)}


@app.post("/api/voice/tts", tags=["Voice & Language"])
def tts(req: TTSRequest):
    return {"audio_url": text_to_speech(req.text, req.language)}


@app.post("/api/voice/stt", tags=["Voice & Language"])
def stt(req: STTRequest):
    return {"transcribed_text": speech_to_text(req.audio_base64, req.language)}


# ---------------- Routes: Weavers ----------------

@app.get("/api/weavers", response_model=list[Weaver], tags=["Weavers"])
def list_weavers(region: Optional[str] = None, craft_type: Optional[CraftType] = None):
    results = list(WEAVERS.values())
    if region:
        results = [w for w in results if region.lower() in w.region.lower()]
    if craft_type:
        results = [w for w in results if w.craft_type == craft_type]
    return results


@app.get("/api/weavers/{weaver_id}", response_model=Weaver, tags=["Weavers"])
def get_weaver(weaver_id: str):
    weaver = WEAVERS.get(weaver_id)
    if not weaver:
        raise HTTPException(status_code=404, detail="Weaver not found")
    return weaver


@app.get("/api/weavers/{weaver_id}/orders", response_model=list[OrderItem], tags=["Weavers"])
def get_weaver_orders(weaver_id: str):
    if weaver_id not in WEAVERS:
        raise HTTPException(status_code=404, detail="Weaver not found")
    return [o for o in ORDERS.values() if o.weaver_id == weaver_id]


@app.patch("/api/orders/{order_id}/status", response_model=OrderItem, tags=["Weavers"])
def update_order_status(order_id: str, body: OrderStatusUpdate):
    order = ORDERS.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = body.status
    return order


# ---------------- Routes: Catalogue ----------------

@app.get("/api/catalogue", response_model=list[Product], tags=["Catalogue"])
def get_catalogue(
    region: Optional[str] = None,
    craft_type: Optional[CraftType] = None,
    category: Optional[ProductCategory] = None,
):
    results = list(PRODUCTS.values())
    if region:
        results = [p for p in results if region.lower() in p.region.lower()]
    if craft_type:
        results = [p for p in results if p.craft_type == craft_type]
    if category:
        results = [p for p in results if p.category == category]
    return results


@app.get("/api/catalogue/{product_id}", response_model=Product, tags=["Catalogue"])
def get_product(product_id: str):
    product = PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ---------------- Routes: Inventory ----------------

@app.get("/api/inventory", response_model=list[InventoryItem], tags=["Inventory"])
def get_inventory():
    return list(INVENTORY.values())


# ---------------- Routes: Corporate Gifting ----------------

@app.post(
    "/api/corporate/order",
    response_model=CorporateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Corporate Gifting"],
)
def create_corporate_order(req: CorporateOrderRequest, background_tasks: BackgroundTasks):
    matched = match_weaver_for_corporate_order(req)
    order_id = str(uuid.uuid4())[:8]

    if matched:
        new_order = OrderItem(
            id=order_id, weaver_id=matched.id, product_category=req.product_category,
            quantity=req.quantity, status=OrderStatus.pending, buyer_name=req.company_name,
            deadline=req.deadline, created_at=datetime.now().strftime("%Y-%m-%d"),
        )
        ORDERS[order_id] = new_order
        days_needed = round(matched.avg_days_per_piece * req.quantity / max(matched.looms, 1))
        estimated_ready = (datetime.now() + timedelta(days=days_needed)).strftime("%Y-%m-%d")

        background_tasks.add_task(
            notify_weaver_mock,
            matched.id,
            NotifyChannel.whatsapp,
            f"Naya corporate order mila hai: {req.quantity} x {req.product_category.value}. Deadline: {req.deadline}",
        )

        return CorporateOrderResponse(
            order_id=order_id,
            matched_weaver_id=matched.id,
            matched_cooperative=matched.cooperative,
            estimated_ready_date=estimated_ready,
            status="matched",
            message=f"Order matched to {matched.cooperative} ({matched.region}).",
        )

    return CorporateOrderResponse(
        order_id=order_id,
        matched_weaver_id=None,
        matched_cooperative=None,
        estimated_ready_date=None,
        status="unmatched",
        message="No weaver cooperative currently available for this region/category. Our team will follow up.",
    )


# ---------------- Routes: Notifications ----------------

def notify_weaver_mock(weaver_id: str, channel: NotifyChannel, message: str) -> None:
    weaver = WEAVERS.get(weaver_id)
    print(f"[NOTIFY MOCK] -> {weaver.name if weaver else weaver_id} via {channel.value}: {message}")


@app.post("/api/notify", tags=["Notifications"])
def notify(req: NotifyRequest, background_tasks: BackgroundTasks):
    if req.weaver_id not in WEAVERS:
        raise HTTPException(status_code=404, detail="Weaver not found")
    background_tasks.add_task(notify_weaver_mock, req.weaver_id, req.channel, req.message)
    return {"queued": True}


# ---------------- Routes: Stats ----------------

@app.get("/api/stats", tags=["Stats"])
def get_stats():
    regions = {w.region for w in WEAVERS.values()}
    return {
        "weavers_onboarded": len(WEAVERS),
        "regions_covered": len(regions),
        "products_listed": len(PRODUCTS),
        "orders_in_progress": len([o for o in ORDERS.values() if o.status == OrderStatus.in_progress]),
    }


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "WeaveAhead API", "docs": "/docs"}
