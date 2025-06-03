from fastapi import FastAPI, HTTPException, Depends, Path, Body
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

# SQLAlchemy model for PortfolioMeta (singleton for cash)
class PortfolioMeta(Base):
    __tablename__ = "portfolio_meta"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cash: Mapped[float] = mapped_column(sa.Float, default=0.0)

# Pydantic model for basic stock data (input)
class StockBase(BaseModel):
    symbol: str
    quantity: float

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

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
LLM_GEMINI_API_KEY = os.getenv("LLM_GEMINI_API_KEY", "")
LLM_GEMINI_API_BASE = os.getenv("LLM_GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/models")

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class AssistantChatRequest(BaseModel):
    messages: list[ChatMessage]
    portfolio: dict = None  # Optional portfolio context

@app.post("/assistant/chat")
async def assistant_chat(request: AssistantChatRequest = Body(...)):
    """Proxy chat to LLM provider, passing messages and portfolio context."""
    if LLM_PROVIDER == "openai":
        url = f"{LLM_API_BASE}/chat/completions"
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }
        # Compose system prompt with portfolio context if provided
        system_prompt = "You are a helpful finance assistant."
        if request.portfolio:
            system_prompt += f"\nHere is the user's portfolio data: {request.portfolio}"
        payload = {
            "model": os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
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
        # Gemini (Google AI Studio) support
        model = os.getenv("LLM_GEMINI_MODEL", "gemini-pro")
        url = f"{LLM_GEMINI_API_BASE}/{model}:generateContent?key={LLM_GEMINI_API_KEY}"
        # Compose system prompt with portfolio context if provided
        system_prompt = "You are a helpful finance assistant."
        if request.portfolio:
            system_prompt += f"\nHere is the user's portfolio data: {request.portfolio}"
        # Gemini expects a single list of content blocks
        content_blocks = [
            {"role": "user", "parts": [{"text": system_prompt}]}
        ]
        for m in request.messages:
            if m.role == "user":
                content_blocks.append({"role": "user", "parts": [{"text": m.content}]})
            elif m.role == "assistant":
                content_blocks.append({"role": "model", "parts": [{"text": m.content}]})
        payload = {"contents": content_blocks}
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            # Gemini's response structure
            reply = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"reply": reply}
    else:
        # Add more providers here as needed
        raise HTTPException(status_code=400, detail=f"LLM provider '{LLM_PROVIDER}' not supported yet.") 