from fastapi import FastAPI, HTTPException, Depends, Path
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

# Configuration for Alpha Vantage API
load_dotenv()
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

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

# Pydantic model for basic stock data (input)
class StockBase(BaseModel):
    symbol: str
    quantity: float

# Pydantic model for portfolio item (output, includes current price and value)
class StockPortfolioItem(StockBase):
    current_price: Optional[float] = None
    current_total_value: Optional[float] = None
    percentage_of_portfolio: Optional[float] = None

# Pydantic model for the overall portfolio response
class PortfolioDetailResponse(BaseModel):
    stocks: List[StockPortfolioItem]
    grand_total_portfolio_value: Optional[float] = None

# Dependency to get async DB session
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Finance Portfolio API"}

async def get_current_stock_price(symbol: str) -> Optional[float]:
    """Fetches the current stock price for a given symbol from Alpha Vantage."""
    if not ALPHA_VANTAGE_API_KEY:
        print("WARNING: Alpha Vantage API key not set. Using placeholder data.")
        # Placeholder logic if API key is not set, useful for initial testing without a key
        if symbol.upper() == "AAPL": return 150.00
        if symbol.upper() == "MSFT": return 300.00
        if symbol.upper() == "GOOGL": return 2700.00
        return None

    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": ALPHA_VANTAGE_API_KEY
    }
    try:
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=10) # Added timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        global_quote_data = data.get("Global Quote")
        if not global_quote_data:
            print(f"'Global Quote' not found in Alpha Vantage response for {symbol}. Response: {data}")
            if "Note" in data:
                 print(f"API Note for {symbol}: {data['Note']}")
            return None
        price_str = global_quote_data.get("05. price")
        if price_str:
            return float(price_str)
        else:
            print(f"Price not found in 'Global Quote' for {symbol}. Data: {global_quote_data}")
            return None
    except requests.exceptions.Timeout:
        print(f"Timeout while fetching price for {symbol} from Alpha Vantage.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching price for {symbol} from Alpha Vantage: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching price for {symbol} from Alpha Vantage: {e}")
        return None
    except ValueError:
        print(f"Error parsing price for {symbol} from Alpha Vantage. Raw data: {data}")
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
    """Retrieve all stocks in the portfolio with current price, total value, and percentage of portfolio."""
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

    return PortfolioDetailResponse(
        stocks=detailed_portfolio_items,
        grand_total_portfolio_value=round(grand_total_portfolio_value, 2) if grand_total_portfolio_value > 0 else 0.0
    )

@app.get("/test-connection")
async def test_connection():
    """Test if Alpha Vantage API key is set and can fetch a real price."""
    if not ALPHA_VANTAGE_API_KEY:
        return JSONResponse(status_code=200, content={"status": "error", "message": "API key not set."})
    price = await get_current_stock_price("AAPL")
    if price is None:
        return JSONResponse(status_code=200, content={"status": "error", "message": "Failed to fetch price. Check API key or rate limits."})
    return {"status": "success", "message": "API key works!", "price": price}

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