# BrokeNoMore Backend Engine 🚀

A production-style, clean, modular **FastAPI** backend for **BrokeNoMore** — an AI-powered personal finance application that predicts future cash-flow problems, optimizes savings goals using constraint programming, detects recurring/unusual spending, and explains financial recommendations with transaction evidence.

---

## 🏗 System Architecture & Folder Structure

```
├── app/
│   ├── api/
│   │   └── routes.py           # Unified REST API endpoints & standard JSON wrappers
│   ├── core/
│   │   ├── config.py           # Settings, CORS, Pydantic BaseSettings (.env loading)
│   │   └── responses.py        # StandardResponse[T] and ErrorResponse models
│   ├── db/
│   │   └── session.py          # SQLAlchemy Engine, SessionLocal, and DB Dependency
│   ├── models/
│   │   └── domain.py           # SQLAlchemy DB Models (User, Transaction, Goal, Receipt)
│   ├── schemas/
│   │   └── schemas.py          # Pydantic validation & response schemas
│   ├── repositories/
│   │   └── domain_repo.py      # Database access layers & hash computation
│   ├── services/
│   │   ├── importer.py         # CSV & Excel upload parsing, debit/credit normalization
│   │   ├── forecaster.py       # Cash-flow forecasting, recurring & unusual spend detection
│   │   ├── optimizer.py        # SciPy constraint-based linear goal optimization
│   │   ├── evidence.py         # Explainable AI report generator with calculations
│   │   └── connector.py        # Simulated Bank/UPI Sandbox stream adapter
│   └── main.py                 # FastAPI App instance, CORS, Exception handlers
├── data/
│   └── sample_transactions.csv # Synthetic demo dataset
├── tests/
│   └── test_api.py             # Automated unit & integration tests (Pytest)
├── .env.example                # Configuration template
├── .gitignore                  # Git ignore rules
└── requirements.txt            # Project Python dependencies
```

---

## ⚡ Quick Start & Setup Commands

### 1. Prerequisites
- Python 3.10+
- PostgreSQL or local SQLite (built-in fallback supported)

### 2. Environment Setup
```bash
# Clone/Navigate to workspace
cd "c:/Users/hruti/OneDrive/Desktop/hach a night"

# Create virtual environment (optional)
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive API Swagger Documentation: `http://localhost:8000/docs`
- ReDoc Documentation: `http://localhost:8000/redoc`

### 4. Run Test Suite
```bash
python -m pytest tests/test_api.py -v
```

---

## 🔌 Completed REST API Endpoints

### 1. User Management
- `POST /api/v1/users` - Register a user profile.
- `GET /api/v1/users/{user_id}` - Retrieve user info.

### 2. Transaction Management & Import Pipeline
- `POST /api/v1/transactions/preview-import` - Preview CSV/Excel file import with column detection and duplicate checking.
- `POST /api/v1/transactions/confirm-import` - Confirm import and save verified records to database.
- `GET /api/v1/transactions` - Fetch user transaction history with pagination.
- `DELETE /api/v1/transactions/clear` - Wipe transaction history for demo resets.

### 3. Analytics & Dashboard
- `GET /api/v1/dashboard/summary` - Aggregate metrics (net savings, daily average, top spending categories).
- `GET /api/v1/analytics/recurring-expenses` - Detect subscriptions & periodic bills.
- `GET /api/v1/analytics/unusual-spending` - Identify anomaly spending using z-score analysis.

### 4. Forecasting & Financial Time Machine
- `GET /api/v1/forecasting/cashflow` - Project cash flow balance for N days into the future and flag buffer breaches.
- `POST /api/v1/simulations/scenario` - **Financial Time Machine**: Simulate income delay, salary cut, custom one-off expenses, or category shifts without modifying actual database records.

### 5. Savings Goals & SciPy Constraint Optimization
- `POST /api/v1/goals` - Add a priority-weighted goal.
- `GET /api/v1/goals` - List active goals.
- `DELETE /api/v1/goals/{goal_id}` - Remove a goal.
- `GET /api/v1/goals/optimize` - Execute SciPy HiGHS linear programming solver to allocate monthly surplus optimal across goals.

### 6. Transparency, Evidence & Privacy Receipts
- `GET /api/v1/reports/explorer` - Side-by-side explainable evidence report linking recommendations directly to transaction evidence.
- `GET /api/v1/privacy/receipts` - Audit log showing data source, records processed, and timestamp.
- `POST /api/v1/connectors/demo-bank-sync` - Simulated UPI / Bank stream adapter for live demonstration.

---

## 🔒 Security & Data Privacy Limitations
1. **Google Pay / Consumer Banking API Disclosure**: Direct public REST API access to Google Pay or consumer UPI transaction histories is not made publicly available by banks due to RBI/NPCI security regulations. The backend supports file uploads (CSV/XLSX) and provides a mock bank connector (`SimulatedBankConnector`) designed to interface with an authorized Account Aggregator (AA) framework in production.
2. **Database Support**: Built-in support for both SQLite (local hackathon demo) and PostgreSQL (production).
