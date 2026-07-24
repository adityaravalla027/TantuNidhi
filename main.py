import asyncio
import uuid
import time
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, EmailStr, validator
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Query, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from passlib.context import CryptContext
from jose import JWTError, jwt

# ==============================================================================
# 1. LOGGING & GLOBAL CONFIGURATION
# ==============================================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WeaveAheadEnterprise")

SECRET_KEY = "amazon_enterprise_super_secret_jwt_key_weaveahead_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

app = FastAPI(
    title="WeaveAhead Global Enterprise Core Engine",
    description="Amazon-Scale Microservice API featuring Distributed Concurrency Locks, Event Bus, and Voice Engine",
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 2. IN-MEMORY HIGH-PERFORMANCE DATA STORE (Simulates PostgreSQL + Redis Cache)
# ==============================================================================
USERS_DB: Dict[str, dict] = {}
PRODUCTS_DB: Dict[str, dict] = {}
CARTS_DB: Dict[str, list] = {}
ORDERS_DB: Dict[str, dict] = {}
INVENTORY_LOCKS: Dict[str, bool] = {}  # Atomic Distributed Lock Simulator
VOICE_DISPATCH_LOGS: List[dict] = []

def seed_initial_enterprise_data():
    """Seeds master catalog and system accounts."""
    # Seed Admin Account
    admin_id = str(uuid.uuid4())
    USERS_DB["admin@weaveahead.com"] = {
        "id": admin_id,
        "email": "admin@weaveahead.com",
        "full_name": "Global Platform Admin",
        "hashed_password": pwd_context.hash("AdminSecret123!"),
        "role": "admin",
        "created_at": datetime.utcnow().isoformat()
    }

    # Seed Seller Account
    seller_id = str(uuid.uuid4())
    USERS_DB["seller.odisha@weaveahead.com"] = {
        "id": seller_id,
        "email": "seller.odisha@weaveahead.com",
        "full_name": "Sambalpuri Weavers Cooperative",
        "hashed_password": pwd_context.hash("WeaverSecret123!"),
        "role": "seller",
        "created_at": datetime.utcnow().isoformat()
    }

    # Seed Master Products
    p1 = "prod-sambalpuri-001"
    p2 = "prod-fulia-002"
    p3 = "prod-banarasi-003"

    PRODUCTS_DB[p1] = {
        "id": p1,
        "sku": "AMZ-IKKAT-001",
        "title": "Sambalpuri Handloom Pure Silk Saree",
        "category": "Handloom Sarees",
        "price": 8500.0,
        "stock": 45,
        "seller_id": seller_id,
        "cluster": "Odisha",
        "rating": 4.9,
        "review_count": 142,
        "attributes": {"color": "Crimson Red", "fabric": "Mulberry Silk", "technique": "Double Ikkat"}
    }
    PRODUCTS_DB[p2] = {
        "id": p2,
        "sku": "AMZ-FULIA-002",
        "title": "Fulia Tangail Jamdani Cotton Saree",
        "category": "Handloom Sarees",
        "price": 3200.0,
        "stock": 100,
        "seller_id": seller_id,
        "cluster": "West Bengal",
        "rating": 4.7,
        "review_count": 88,
        "attributes": {"color": "Royal Blue", "fabric": "Organic Cotton", "technique": "Tangail Weave"}
    }
    PRODUCTS_DB[p3] = {
        "id": p3,
        "sku": "AMZ-BANARASI-003",
        "title": "Varanasi Katan Silk Zari Brocade",
        "category": "Luxury Weaves",
        "price": 18500.0,
        "stock": 12,
        "seller_id": seller_id,
        "cluster": "Uttar Pradesh",
        "rating": 5.0,
        "review_count": 56,
        "attributes": {"color": "Gold & Emerald", "fabric": "Katan Silk", "technique": "Kadwa Zari"}
    }

seed_initial_enterprise_data()

# ==============================================================================
# 3. PYDANTIC SCHEMAS (DATA VALIDATION & CONTRACTS)
# ==============================================================================
class UserRegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "customer"  # customer, seller, admin

    @validator("role")
    def validate_role(cls, v):
        if v not in ["customer", "seller", "admin"]:
            raise ValueError("Role must be one of: customer, seller, admin")
        return v

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: str

class ProductCreateRequest(BaseModel):
    sku: str
    title: str
    category: str
    price: float = Field(gt=0, description="Price must be strictly positive")
    stock: int = Field(ge=0, description="Stock cannot be negative")
    cluster: str
    attributes: Dict[str, str]

class ProductUpdateRequest(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    attributes: Optional[Dict[str, str]] = None

class CartItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, description="Quantity must be at least 1")

class CheckoutRequest(BaseModel):
    shipping_address: str
    city: str
    postal_code: str
    payment_method: str  # CREDIT_CARD, UPI, NET_BANKING, COD

class SSMLSynthesizeRequest(BaseModel):
    text: str
    language_code: str = "en-IN"  # en-IN, hi-IN, bn-IN
    voice_id: str = "Kajal"       # Amazon Polly Neural Voices: Kajal, Aditi, Joanna
    rate: str = "medium"          # slow, medium, fast
    pitch: str = "+0%"

class VoiceDispatchLogResponse(BaseModel):
    dispatch_id: str
    timestamp: str
    seller_id: str
    message_ssml: str
    status: str

# ==============================================================================
# 4. AUTHENTICATION & SECURITY SUBSYSTEM
# ==============================================================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None or email not in USERS_DB:
            raise credentials_exception
        return USERS_DB[email]
    except JWTError:
        raise credentials_exception

def require_role(allowed_roles: List[str]):
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Required role from {allowed_roles}, got '{current_user['role']}'"
            )
        return current_user
    return role_checker

# ==============================================================================
# 5. ASYNCHRONOUS EVENT BUS & AMAZON POLLY VOICE DISPATCH ENGINE
# ==============================================================================
def async_email_sms_notifications(order_id: str, email: str, total_amount: float):
    """Simulates Amazon SNS/SQS decoupled email and SMS dispatch."""
    time.sleep(0.5)
    logger.info(f"[EVENT BUS] Sent Order Confirmation Email & SMS for Order {order_id} to {email}. Total: ₹{total_amount}")

def async_amazon_polly_seller_voice_dispatch(seller_id: str, product_title: str, qty: int, cluster: str):
    """Simulates Amazon Polly Automated SSML Voice Call to Artisans/Sellers."""
    ssml_payload = f"""
    <speak>
        <amazon:domain name="news">
            <emphasis level="strong">Attention Handloom Cooperative!</emphasis>
            A new order has been confirmed for {qty} units of <prosody pitch="+5%">{product_title}</prosody>.
            <break time="400ms"/>
            Please begin warp setup and packaging for the {cluster} cluster immediately.
        </amazon:domain>
    </speak>
    """
    dispatch_entry = {
        "dispatch_id": f"DISPATCH-{uuid.uuid4().hex[:8].upper()}",
        "timestamp": datetime.utcnow().isoformat(),
        "seller_id": seller_id,
        "message_ssml": ssml_payload.strip(),
        "status": "SENT_VIA_POLLY_VOICE_GATEWAY"
    }
    VOICE_DISPATCH_LOGS.append(dispatch_entry)
    logger.info(f"[VOICE ENGINE] Automated Polly Voice Dispatch Triggered for Seller ID '{seller_id}'")

# ==============================================================================
# 6. ROUTE HANDLERS: AUTHENTICATION MODULE
# ==============================================================================
@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegisterRequest):
    if user.email in USERS_DB:
        raise HTTPException(status_code=400, detail="Account with this email already exists.")
    
    user_id = str(uuid.uuid4())
    USERS_DB[user.email] = {
        "id": user_id,
        "email": user.email,
        "full_name": user.full_name,
        "hashed_password": get_password_hash(user.password),
        "role": user.role,
        "created_at": datetime.utcnow().isoformat()
    }
    return {"message": "Account registered successfully", "user_id": user_id, "role": user.role}

@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = USERS_DB.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user["email"], "role": user["role"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["role"],
        "user_id": user["id"]
    }

@app.get("/api/v1/auth/me")
def get_user_profile(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "created_at": current_user["created_at"]
    }

# ==============================================================================
# 7. ROUTE HANDLERS: CATALOG & SEARCH MODULE
# ==============================================================================
@app.get("/api/v1/products")
def list_products(
    category: Optional[str] = None,
    cluster: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    search: Optional[str] = None,
    sort_by: str = Query("rating", regex="^(price_asc|price_desc|rating|title)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Amazon-Style Dynamic Search with Faceted Filters, Sorting, and Pagination."""
    results = list(PRODUCTS_DB.values())

    if category:
        results = [p for p in results if p["category"].lower() == category.lower()]
    if cluster:
        results = [p for p in results if p["cluster"].lower() == cluster.lower()]
    if min_price is not None:
        results = [p for p in results if p["price"] >= min_price]
    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]
    if search:
        query = search.lower()
        results = [
            p for p in results 
            if query in p["title"].lower() or query in p["sku"].lower() or query in p["category"].lower()
        ]

    # Sorting Logic
    if sort_by == "price_asc":
        results.sort(key=lambda x: x["price"])
    elif sort_by == "price_desc":
        results.sort(key=lambda x: x["price"], reverse=True)
    elif sort_by == "rating":
        results.sort(key=lambda x: x["rating"], reverse=True)
    elif sort_by == "title":
        results.sort(key=lambda x: x["title"])

    paginated_results = results[skip : skip + limit]

    return {
        "total_results": len(results),
        "skip": skip,
        "limit": limit,
        "page_count": len(paginated_results),
        "products": paginated_results
    }

@app.get("/api/v1/products/{product_id}")
def get_product_by_id(product_id: str):
    product = PRODUCTS_DB.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product

@app.post("/api/v1/products", status_code=status.HTTP_201_CREATED)
def create_product(
    product: ProductCreateRequest,
    current_user: dict = Depends(require_role(["seller", "admin"]))
):
    """Seller/Admin Portal Endpoint for Product Listing."""
    prod_id = f"prod-{uuid.uuid4().hex[:8]}"
    new_product = {
        "id": prod_id,
        "sku": product.sku,
        "title": product.title,
        "category": product.category,
        "price": product.price,
        "stock": product.stock,
        "seller_id": current_user["id"],
        "cluster": product.cluster,
        "rating": 0.0,
        "review_count": 0,
        "attributes": product.attributes
    }
    PRODUCTS_DB[prod_id] = new_product
    return new_product

@app.patch("/api/v1/products/{product_id}")
def update_product(
    product_id: str,
    update_data: ProductUpdateRequest,
    current_user: dict = Depends(require_role(["seller", "admin"]))
):
    product = PRODUCTS_DB.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    if current_user["role"] != "admin" and product["seller_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="You can only edit your own products.")

    if update_data.title is not None:
        product["title"] = update_data.title
    if update_data.price is not None:
        product["price"] = update_data.price
    if update_data.stock is not None:
        product["stock"] = update_data.stock
    if update_data.attributes is not None:
        product["attributes"].update(update_data.attributes)

    return product

# ==============================================================================
# 8. ROUTE HANDLERS: SHOPPING CART MODULE
# ==============================================================================
@app.post("/api/v1/cart/items")
def add_item_to_cart(
    item: CartItemRequest,
    current_user: dict = Depends(get_current_user)
):
    product = PRODUCTS_DB.get(item.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    if product["stock"] < item.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {product['stock']}")

    user_id = current_user["id"]
    if user_id not in CARTS_DB:
        CARTS_DB[user_id] = []

    # Check if item exists in user cart
    for cart_item in CARTS_DB[user_id]:
        if cart_item["product_id"] == item.product_id:
            if product["stock"] < (cart_item["quantity"] + item.quantity):
                raise HTTPException(status_code=400, detail="Cannot add quantity exceeding available stock.")
            cart_item["quantity"] += item.quantity
            return {"message": "Cart item updated", "cart": CARTS_DB[user_id]}

    CARTS_DB[user_id].append({"product_id": item.product_id, "quantity": item.quantity})
    return {"message": "Item added to cart", "cart": CARTS_DB[user_id]}

@app.get("/api/v1/cart")
def view_cart(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    raw_cart = CARTS_DB.get(user_id, [])

    detailed_items = []
    subtotal = 0.0

    for item in raw_cart:
        p = PRODUCTS_DB.get(item["product_id"])
        if p:
            line_total = p["price"] * item["quantity"]
            subtotal += line_total
            detailed_items.append({
                "product_id": p["id"],
                "sku": p["sku"],
                "title": p["title"],
                "price": p["price"],
                "quantity": item["quantity"],
                "line_total": line_total
            })

    estimated_tax = round(subtotal * 0.18, 2)  # 18% GST
    grand_total = round(subtotal + estimated_tax, 2)

    return {
        "user_id": user_id,
        "items": detailed_items,
        "subtotal": subtotal,
        "tax_gst_18": estimated_tax,
        "grand_total": grand_total
    }

@app.delete("/api/v1/cart/items/{product_id}")
def remove_cart_item(product_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id in CARTS_DB:
        CARTS_DB[user_id] = [item for item in CARTS_DB[user_id] if item["product_id"] != product_id]
    return {"message": f"Item {product_id} removed from cart"}

# ==============================================================================
# 9. ROUTE HANDLERS: CHECKOUT & TRANSACTIONAL ORDER ENGINE
# ==============================================================================
@app.post("/api/v1/checkout", status_code=status.HTTP_201_CREATED)
async def process_checkout(
    checkout_data: CheckoutRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Amazon-Grade Checkout Workflow:
    1. Distributed Lock Allocation (Prevents Flash Sale Overbooking)
    2. Stock Verification & Atomic Deduction
    3. Transaction Recording
    4. Async Event Triggering (SNS Notifications & Polly Voice Alerts)
    """
    user_id = current_user["id"]
    cart_items = CARTS_DB.get(user_id, [])

    if not cart_items:
        raise HTTPException(status_code=400, detail="Cannot checkout an empty shopping cart.")

    # STEP 1: Acquire Concurrency Locks
    acquired_locks = []
    try:
        for item in cart_items:
            p_id = item["product_id"]
            if INVENTORY_LOCKS.get(p_id, False):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="High traffic surge detected on an item in your cart. Please retry."
                )
            INVENTORY_LOCKS[p_id] = True
            acquired_locks.append(p_id)

        # STEP 2: Stock Verification & Calculation
        total_subtotal = 0.0
        line_items = []

        for item in cart_items:
            product = PRODUCTS_DB.get(item["product_id"])
            if not product or product["stock"] < item["quantity"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock unavailable for product '{product['title'] if product else 'Unknown'}'"
                )

            # Deduct stock atomically
            product["stock"] -= item["quantity"]
            item_subtotal = product["price"] * item["quantity"]
            total_subtotal += item_subtotal

            line_items.append({
                "product_id": product["id"],
                "title": product["title"],
                "quantity": item["quantity"],
                "price_unit": product["price"],
                "line_total": item_subtotal
            })

            # Queue background voice dispatch call to the artisan seller
            background_tasks.add_task(
                async_amazon_polly_seller_voice_dispatch,
                seller_id=product["seller_id"],
                product_title=product["title"],
                qty=item["quantity"],
                cluster=product["cluster"]
            )

        tax_gst = round(total_subtotal * 0.18, 2)
        grand_total = round(total_subtotal + tax_gst, 2)
        order_id = f"AMZ-ORD-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"

        # STEP 3: Save Order Object
        order_record = {
            "order_id": order_id,
            "user_id": user_id,
            "user_email": current_user["email"],
            "line_items": line_items,
            "subtotal": total_subtotal,
            "tax_gst": tax_gst,
            "grand_total": grand_total,
            "shipping_address": f"{checkout_data.shipping_address}, {checkout_data.city} - {checkout_data.postal_code}",
            "payment_method": checkout_data.payment_method,
            "payment_status": "PAID",
            "fulfillment_status": "DISPATCHED_TO_WEAVER_CLUSTER",
            "created_at": datetime.utcnow().isoformat()
        }

        ORDERS_DB[order_id] = order_record
        CARTS_DB[user_id] = []  # Clear Cart

        # STEP 4: Trigger Non-Blocking Event Notifications
        background_tasks.add_task(
            async_email_sms_notifications,
            order_id=order_id,
            email=current_user["email"],
            total_amount=grand_total
        )

        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "grand_total": grand_total,
            "payment_status": "PAID",
            "message": "Order processed successfully and dispatched to cooperative clusters."
        }

    finally:
        # Release All Concurrency Locks
        for locked_id in acquired_locks:
            INVENTORY_LOCKS[locked_id] = False

@app.get("/api/v1/orders")
def get_user_orders(current_user: dict = Depends(get_current_user)):
    user_orders = [ord for ord in ORDERS_DB.values() if ord["user_id"] == current_user["id"]]
    return {"order_count": len(user_orders), "orders": user_orders}

@app.get("/api/v1/orders/{order_id}")
def get_order_by_id(order_id: str, current_user: dict = Depends(get_current_user)):
    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if current_user["role"] != "admin" and order["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")
    return order

# ==============================================================================
# 10. ROUTE HANDLERS: AMAZON POLLY & VOICE CONTROL MODULE
# ==============================================================================
@app.post("/api/v1/voice/synthesize-ssml")
def synthesize_amazon_polly_ssml(req: SSMLSynthesizeRequest):
    """
    Amazon Polly SSML Text-to-Speech Parser.
    Formats raw text into full SSML structure with pitch and rate controls.
    """
    formatted_ssml = f"""
    <speak>
        <amazon:domain name="news">
            <prosody rate="{req.rate}" pitch="{req.pitch}">
                {req.text}
            </prosody>
        </amazon:domain>
    </speak>
    """
    return {
        "engine": "AWS Polly Neural Engine",
        "voice_id": req.voice_id,
        "language_code": req.language_code,
        "raw_text": req.text,
        "compiled_ssml": formatted_ssml.strip()
    }

@app.get("/api/v1/voice/dispatch-logs")
def get_voice_dispatch_logs(current_user: dict = Depends(require_role(["admin", "seller"]))):
    """Returns log entries of all automated Amazon Polly voice calls made to sellers."""
    if current_user["role"] == "admin":
        return {"logs": VOICE_DISPATCH_LOGS}
    
    # Filter logs for specific seller
    seller_logs = [log for log in VOICE_DISPATCH_LOGS if log["seller_id"] == current_user["id"]]
    return {"logs": seller_logs}

# ==============================================================================
# 11. SYSTEM HEALTH & DIAGNOSTICS
# ==============================================================================
@app.get("/health", status_code=status.HTTP_200_OK)
def system_health_check():
    return {
        "status": "OPERATIONAL",
        "timestamp": datetime.utcnow().isoformat(),
        "registered_users": len(USERS_DB),
        "catalog_items": len(PRODUCTS_DB),
        "total_orders_processed": len(ORDERS_DB),
        "active_inventory_locks": sum(1 for v in INVENTORY_LOCKS.values() if v)
    }

