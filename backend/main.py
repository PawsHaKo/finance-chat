from fastapi import FastAPI, HTTPException, Depends, Path, Body, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
import requests
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, selectinload
from sqlalchemy import select, update
import sqlalchemy as sa
import asyncio
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
import finnhub
import httpx
import csv
from io import StringIO
import unicodedata

load_dotenv()
# Configuration for Finnhub API
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# Finnhub client (global, reuse for all requests)
finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY) if FINNHUB_API_KEY else None

DATABASE_URL = "sqlite+aiosqlite:///./portfolio.db"
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

app = FastAPI()

# CORS setup for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# SQLAlchemy model for Stock
class Stock(Base):
    __tablename__ = "stocks"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(sa.String, unique=True, index=True)
    quantity: Mapped[float] = mapped_column(sa.Float)
    unit_cost: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)

# SQLAlchemy model for PortfolioMeta (singleton for cash)
class PortfolioMeta(Base):
    __tablename__ = "portfolio_meta"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cash: Mapped[float] = mapped_column(sa.Float, default=0.0)

# Pydantic model for basic stock data (input)
class StockBase(BaseModel):
    symbol: str
    quantity: float
    unit_cost: Optional[float] = None

# Pydantic model for portfolio item (output, includes current price and value)
class StockPortfolioItem(StockBase):
    current_price: Optional[float] = None
    current_total_value: Optional[float] = None
    percentage_of_portfolio: Optional[float] = None

# Pydantic model for cash
class CashResponse(BaseModel):
    cash: float

# Pydantic model for the overall portfolio response
class PortfolioDetailResponse(BaseModel):
    stocks: List[StockPortfolioItem]
    grand_total_portfolio_value: Optional[float] = None
    cash: Optional[float] = None

# Dependency to get async DB session
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Ensure singleton PortfolioMeta row exists
    async with async_session() as session:
        result = await session.execute(select(PortfolioMeta))
        meta = result.scalar_one_or_none()
        if not meta:
            meta = PortfolioMeta(cash=0.0)
            session.add(meta)
            await session.commit()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Finance Portfolio API"}

async def get_current_stock_price(symbol: str) -> Optional[float]:
    """Fetches the current stock price for a given symbol from Finnhub."""
    if not FINNHUB_API_KEY or not finnhub_client:
        print("WARNING: Finnhub API key not set. Using placeholder data.")
        # Placeholder logic if API key is not set, useful for initial testing without a key
        if symbol.upper() == "AAPL": return 150.00
        if symbol.upper() == "MSFT": return 300.00
        if symbol.upper() == "GOOGL": return 2700.00
        return None
    try:
        quote = await asyncio.to_thread(finnhub_client.quote, symbol.upper())
        price = quote.get("c")
        if price is not None and price != 0:
            return float(price)
        else:
            print(f"Price not found in Finnhub response for {symbol}. Data: {quote}")
            return None
    except Exception as e:
        print(f"Error fetching price for {symbol} from Finnhub: {e}")
        return None

@app.post("/portfolio/stocks/", response_model=StockBase)
async def add_stock_manually(stock: StockBase, session: AsyncSession = Depends(get_session)):
    """Manually add a stock to the portfolio or update quantity if symbol exists."""
    result = await session.execute(select(Stock).where(Stock.symbol == stock.symbol.upper()))
    existing_stock = result.scalar_one_or_none()
    if existing_stock:
        existing_stock.quantity += stock.quantity
        await session.commit()
        await session.refresh(existing_stock)
        return StockBase(symbol=existing_stock.symbol, quantity=existing_stock.quantity)
    new_stock = Stock(symbol=stock.symbol.upper(), quantity=stock.quantity)
    session.add(new_stock)
    await session.commit()
    await session.refresh(new_stock)
    return StockBase(symbol=new_stock.symbol, quantity=new_stock.quantity)

@app.get("/portfolio/stocks/", response_model=PortfolioDetailResponse)
async def get_portfolio_with_details(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Stock))
    stocks_in_db = result.scalars().all()
    detailed_portfolio_items: List[StockPortfolioItem] = []
    grand_total_portfolio_value: float = 0.0

    # First pass: Fetch prices and calculate individual total values
    for stock_in_db in stocks_in_db:
        current_price = await get_current_stock_price(stock_in_db.symbol)
        current_total_value = None
        if current_price is not None:
            current_total_value = round(current_price * stock_in_db.quantity, 2)
            grand_total_portfolio_value += current_total_value
        detailed_portfolio_items.append(
            StockPortfolioItem(
                symbol=stock_in_db.symbol,
                quantity=stock_in_db.quantity,
                current_price=current_price,
                current_total_value=current_total_value
            )
        )

    # Second pass: Calculate percentage_of_portfolio for each stock
    if grand_total_portfolio_value > 0: # Avoid division by zero
        for item in detailed_portfolio_items:
            if item.current_total_value is not None:
                item.percentage_of_portfolio = round((item.current_total_value / grand_total_portfolio_value) * 100, 2)

    # Fetch cash
    result = await session.execute(select(PortfolioMeta))
    meta = result.scalar_one_or_none()
    cash = meta.cash if meta else 0.0

    return PortfolioDetailResponse(
        stocks=detailed_portfolio_items,
        grand_total_portfolio_value=round(grand_total_portfolio_value, 2) if grand_total_portfolio_value > 0 else 0.0,
        cash=cash
    )

@app.get("/test-connection")
async def test_connection():
    """Test if Finnhub API key is set and can fetch a real price."""
    print(f"FINNHUB_API_KEY: {FINNHUB_API_KEY}")
    if not FINNHUB_API_KEY:
        return JSONResponse(status_code=200, content={"status": "error", "message": "Finnhub API key not set."})
    try:
        price = await get_current_stock_price("AAPL")
        if price is None:
            return JSONResponse(status_code=200, content={"status": "error", "message": "Failed to fetch price. Check API key or rate limits.", "details": "No price returned from Finnhub."})
        return {"status": "success", "message": "API key works!", "price": price}
    except Exception as e:
        return JSONResponse(status_code=200, content={"status": "error", "message": "Exception occurred while fetching price.", "details": str(e)})

@app.patch("/portfolio/stocks/{symbol}", response_model=StockBase)
async def update_stock(symbol: str = Path(..., description="Stock symbol"), stock: StockBase = None, session: AsyncSession = Depends(get_session)):
    """Update the quantity of a stock in the portfolio."""
    result = await session.execute(select(Stock).where(Stock.symbol == symbol.upper()))
    existing_stock = result.scalar_one_or_none()
    if not existing_stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    if stock and stock.quantity is not None:
        existing_stock.quantity = stock.quantity
        await session.commit()
        await session.refresh(existing_stock)
    return StockBase(symbol=existing_stock.symbol, quantity=existing_stock.quantity)

@app.delete("/portfolio/stocks/{symbol}")
async def delete_stock(symbol: str = Path(..., description="Stock symbol"), session: AsyncSession = Depends(get_session)):
    """Delete a stock from the portfolio by symbol."""
    result = await session.execute(select(Stock).where(Stock.symbol == symbol.upper()))
    existing_stock = result.scalar_one_or_none()
    if not existing_stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    await session.delete(existing_stock)
    await session.commit()
    return {"detail": f"Stock {symbol.upper()} deleted."}

@app.get("/portfolio/stocks/refresh", response_model=PortfolioDetailResponse)
async def refresh_portfolio_prices(session: AsyncSession = Depends(get_session)):
    """Explicitly refresh and return the portfolio with updated prices (does not modify DB)."""
    return await get_portfolio_with_details(session)

@app.get("/portfolio/stocks/{symbol}", response_model=StockPortfolioItem)
async def get_stock_with_details(symbol: str = Path(..., description="Stock symbol"), session: AsyncSession = Depends(get_session)):
    """Retrieve a single stock in the portfolio with current price, total value, and percentage of portfolio."""
    result = await session.execute(select(Stock).where(Stock.symbol == symbol.upper()))
    stock_in_db = result.scalar_one_or_none()
    if not stock_in_db:
        raise HTTPException(status_code=404, detail="Stock not found")
    current_price = await get_current_stock_price(stock_in_db.symbol)
    if current_price is None:
        current_price_for_calc = 0.0
    else:
        current_price_for_calc = current_price
    current_total_value = None
    if current_price is not None:
        current_total_value = round(current_price * stock_in_db.quantity, 2)
    # Calculate grand total for percentage (fetch all stocks, but don't fetch their prices)
    result_all = await session.execute(select(Stock))
    stocks_in_db = result_all.scalars().all()
    grand_total_portfolio_value = 0.0
    for s in stocks_in_db:
        if s.symbol == stock_in_db.symbol and current_total_value is not None:
            grand_total_portfolio_value += current_total_value
        else:
            grand_total_portfolio_value += s.quantity * (current_price_for_calc if s.symbol == stock_in_db.symbol else 0)
    percentage_of_portfolio = None
    if grand_total_portfolio_value > 0 and current_total_value is not None:
        percentage_of_portfolio = round((current_total_value / grand_total_portfolio_value) * 100, 2)
    return StockPortfolioItem(
        symbol=stock_in_db.symbol,
        quantity=stock_in_db.quantity,
        current_price=current_price,
        current_total_value=current_total_value,
        percentage_of_portfolio=percentage_of_portfolio
    )

@app.get("/portfolio/cash/", response_model=CashResponse)
async def get_cash(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(PortfolioMeta))
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(status_code=404, detail="Portfolio meta not found")
    return CashResponse(cash=meta.cash)

@app.put("/portfolio/cash/", response_model=CashResponse)
async def set_cash(cash: CashResponse, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(PortfolioMeta))
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(status_code=404, detail="Portfolio meta not found")
    if cash.cash < 0:
        raise HTTPException(status_code=400, detail="Cash cannot be negative")
    meta.cash = cash.cash
    await session.commit()
    await session.refresh(meta)
    return CashResponse(cash=meta.cash)

# --- LLM Configuration ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai") # Supported: "openai", "gemini"

# Generic model name override - if set, applies to the chosen provider
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME") # e.g., "gpt-4o", "gemini-1.5-pro-latest"

# OpenAI Specific Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"

# Gemini Specific Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/models")
DEFAULT_GEMINI_MODEL = os.getenv("DEFAULT_GEMINI_MODEL", "gemini-pro")

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class AssistantChatRequest(BaseModel):
    messages: list[ChatMessage]
    portfolio: dict = None  # Optional portfolio context

@app.post("/assistant/chat")
async def assistant_chat(request: AssistantChatRequest = Body(...)):
    """Proxy chat to LLM provider, passing messages and portfolio context."""
    system_prompt = "You are a helpful finance assistant."
    if request.portfolio:
        system_prompt += f"\nHere is the user's portfolio data: {request.portfolio}"

    if LLM_PROVIDER == "openai":
        actual_model = LLM_MODEL_NAME or DEFAULT_OPENAI_MODEL
        api_key = OPENAI_API_KEY
        api_base = OPENAI_API_BASE
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key (OPENAI_API_KEY) not configured.")

        url = f"{api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *[{"role": m.role, "content": m.content} for m in request.messages]
            ],
            "temperature": 0.7
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return {"reply": data["choices"][0]["message"]["content"]}

    elif LLM_PROVIDER == "gemini":
        actual_model = LLM_MODEL_NAME or DEFAULT_GEMINI_MODEL
        api_key = GEMINI_API_KEY
        api_base = GEMINI_API_BASE
        if not api_key:
            raise HTTPException(status_code=500, detail="Gemini API key (GEMINI_API_KEY) not configured.")

        url = f"{api_base}/{actual_model}:generateContent?key={api_key}"
        # Gemini expects a specific structure for messages and system prompt handling
        contents = []
        # Add system prompt as the first user message part if it's not implicitly handled by the model
        # For Gemini, it's better to prepend it to the first user message or have a specific turn.
        # Here, we'll prepend it to the history before the user's actual messages.
        
        # Convert messages to Gemini format
        # System prompt is handled by being part of the overall prompt history.
        # The initial system prompt is a user turn, then assistant response, then user query.
        # We will build the Gemini `contents` list from the request.messages, prefixing the system_prompt.

        gemini_messages = [] 
        # Start with the system prompt as the initial context for the model.
        # Gemini usually takes history in pairs of user/model.
        # If the first message from history is user, we can prepend system context there.
        # If it's assistant (e.g. initial greeting), system prompt could be a preceding user turn.

        # Simplified: add system prompt as a separate user turn if messages don't cover it.
        # For now, the system prompt is part of the first user message for Gemini for simplicity.
        # Let's adjust the payload based on typical Gemini API interactions.
        
        # Construct history for Gemini: it wants alternating user and model roles.
        # The very first instruction can be a user role.
        gemini_contents = [{"role": "user", "parts": [{"text": system_prompt}]}]
        if request.messages:
            # Add a model part to complete the first turn if system_prompt was the user part
            gemini_contents.append({"role": "model", "parts": [{"text": "Understood. I am ready to assist with the portfolio."}]}) 

        for msg in request.messages:
            role = "user" if msg.role == "user" else "model"
            gemini_contents.append({"role": role, "parts": [{"text": msg.content}]})

        payload = {"contents": gemini_contents}
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"reply": reply}
    else:
        raise HTTPException(status_code=400, detail=f"LLM provider '{LLM_PROVIDER}' not supported yet.")

@app.post("/portfolio/import-csv/")
async def import_portfolio_csv(
    file: UploadFile = File(...),
    mode: str = Form("replace"),
    session: AsyncSession = Depends(get_session)
):
    """
    Import portfolio from a CSV file. Mode can be 'replace' (clear all and import) or 'append' (upsert by symbol).
    CSV columns: 代號 (Symbol), 股數 (Quantity), 單位成本 (Unit Cost)
    """
    content = await file.read()
    # Try utf-8, then big5, then gbk
    for encoding in ["utf-8", "big5", "gbk"]:
        try:
            decoded = content.decode(encoding)
            break
        except Exception:
            decoded = None
    if decoded is None:
        return {"error": "Could not decode CSV file. Please use UTF-8, Big5, or GBK encoding."}
    # Normalize all whitespace in headers and values
    def normalize(s):
        if s is None:
            return None
        s = unicodedata.normalize('NFKC', s)
        s = s.replace('\u00A0', ' ').replace('\ufeff', '')  # Remove non-breaking space and BOM
        return s.strip()
    reader = csv.DictReader(StringIO(decoded))
    # Normalize fieldnames
    reader.fieldnames = [normalize(h) for h in reader.fieldnames]
    added, updated, skipped, errors = 0, 0, 0, []
    rows = list(reader)
    # Diagnostic: capture headers and first row
    debug_headers = reader.fieldnames
    debug_first_row = rows[0] if rows else {}
    def get_val(row, *keys):
        for k in keys:
            for rk in row:
                if normalize(rk) == normalize(k):
                    return normalize(row[rk])
        return None
    if mode == "replace":
        await session.execute(sa.delete(Stock))
        await session.commit()
    for row in rows:
        symbol = get_val(row, "代號", "Symbol")
        quantity = get_val(row, "股數", "Quantity")
        unit_cost = get_val(row, "單位成本", "Unit Cost")
        if not symbol or not quantity:
            skipped += 1
            continue
        try:
            symbol = normalize(symbol).upper()
            quantity = float(quantity.replace(',', ''))
            unit_cost_val = float(unit_cost.replace(',', '')) if unit_cost not in (None, "") else None
        except Exception as e:
            errors.append(f"Row error for symbol {symbol}: {e}")
            skipped += 1
            continue
        # Upsert logic
        result = await session.execute(select(Stock).where(Stock.symbol == symbol))
        stock = result.scalar_one_or_none()
        if stock:
            stock.quantity = quantity
            stock.unit_cost = unit_cost_val
            updated += 1
        else:
            stock = Stock(symbol=symbol, quantity=quantity, unit_cost=unit_cost_val)
            session.add(stock)
            added += 1
    await session.commit()
    return {
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "mode": mode,
        "total": added + updated
    } 