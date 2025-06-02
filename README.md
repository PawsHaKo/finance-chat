# Finance Portfolio Tool

A web application to manage and track stock portfolios. This project allows users to add stocks, import portfolios, fetch real-time prices, and view analytics on their holdings.

---

## Features

- Manually add stocks to your portfolio
- Import portfolio from a CSV file
- Fetch current stock prices (via Finnhub API)
- Calculate current total value for each stock
- Calculate the percentage of each stock in the total portfolio
- Display overall portfolio value

---

## Tech Stack

- **Frontend:** React (Vite)
- **Backend:** Python (FastAPI)
- **Database:** SQLite (default, can be extended to PostgreSQL)
- **Stock Data API:** [Finnhub](https://finnhub.io/) (requires API key)

---

## Requirements

- Node.js (v18+ recommended)
- Python 3.9+
- (Optional) [pipenv](https://pipenv.pypa.io/) or [virtualenv](https://virtualenv.pypa.io/)

---

## Environment Variables

The backend requires a Finnhub API key. Create a `.env` file in the `backend/` directory:

```
FINNHUB_API_KEY=your_finnhub_api_key_here
```

You can obtain a free API key from [Finnhub.io](https://finnhub.io/).

---

## Installation Guide

### 1. Clone the repository

```bash
git clone <repo-url>
cd finance-chat
```

### 2. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Create .env file as described above
```

#### Run the backend server:

```bash
uvicorn main:app --reload
```

The backend will be available at `http://localhost:8000`.

### 3. Frontend Setup

```bash
cd ../frontend
npm install
```

#### Run the frontend dev server:

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## Project Structure

```
finance-chat/
├── backend/
│   ├── main.py           # FastAPI backend
│   ├── requirements.txt  # Python dependencies
│   └── portfolio.db      # SQLite database (auto-created)
├── frontend/
│   ├── src/              # React source code
│   ├── public/           # Static assets
│   └── package.json      # Frontend dependencies
└── README.md
```

---

## Usage

- Access the frontend at [http://localhost:5173](http://localhost:5173)
- The backend API is available at [http://localhost:8000](http://localhost:8000)
- Add stocks, import CSV, and view your portfolio in real time.

---

## Notes

- The backend uses Finnhub for real-time stock prices. If no API key is set, it will use placeholder data for a few symbols (AAPL, MSFT, GOOGL).
- The database defaults to SQLite for easy local development.
- For production, consider using PostgreSQL and setting up environment variables accordingly.

---

## License

MIT 