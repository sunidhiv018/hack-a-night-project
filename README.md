# BrokeNoMore 🚀
> **AI-Powered Cash-Flow Intelligence, Risk Forecasting & Savings Optimization**

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-118%20Passing%20(100%25)-success.svg?style=flat-square)](file:///c:/Users/verma/hackanight/hack-a-night-project/tests)
[![SciPy](https://img.shields.io/badge/Optimizer-SciPy%20SLSQP-8CAAE6.svg?style=flat-square&logo=scipy&logoColor=white)](https://scipy.org)
[![Scikit-Learn](https://img.shields.io/badge/ML-TF--IDF%20%2B%20IsolationForest-F7931E.svg?style=flat-square&logo=scikitlearn&logoColor=white)](https://scikit-learn.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

---

## 🌟 What is BrokeNoMore?

**BrokeNoMore** is an intelligent personal finance engine built to eliminate "end-of-the-month broke syndrome". Instead of just tracking past expenses, BrokeNoMore looks ahead: it models upcoming cash flow, predicts safety buffer breaches before they happen, optimizes savings goals mathematically, and provides explainable AI recommendations grounded in your verified transaction ledger.

---

## ✨ Core Features

| Feature | Description |
| :--- | :--- |
| 🔮 **90-Day Cash Flow Forecast** | Dynamic rolling balance projection that flags upcoming risk levels (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`) and detects scheduled recurring expenses before they drain your account. |
| ⚡ **Smart GPay AutoSync** | Local, privacy-first notification parser that extracts transaction details from UPI notifications with zero OTP/PIN retention and SHA-256 deduplication. |
| 🎯 **SciPy Savings Optimizer** | Sequential Least Squares Programming (`SLSQP`) that mathematically allocates monthly surplus across priority-weighted savings goals. |
| ⏳ **Financial Time Machine** | Non-destructive sandbox allowing users to simulate "what-if" financial scenarios (salary delays, rent increases, emergency bills) without altering the live ledger. |
| 🤖 **Milo — Your Money Buddy** | Context-grounded conversational copilot that answers balance, budget, and afford questions with clickable transaction evidence. |
| 🛡️ **Cryptographic Privacy Receipts** | Transparent audit trail recording data processing operations, SHA-256 integrity hashes, and zero external third-party data leaks. |

---

## 🏗 System Architecture & Project Structure

```
hack-a-night-project/
├── app/
│   ├── api/
│   │   └── routes.py           # Unified REST API endpoints & schemas
│   ├── core/
│   │   ├── config.py           # Application settings & environment variables
│   │   └── responses.py        # Standardized API response envelopes
│   ├── db/
│   │   └── session.py          # SQLAlchemy 2.0 database engine & session maker
│   ├── ml/
│   │   ├── artifacts/          # Serialized models & metadata.json benchmark logs
│   │   ├── engine.py           # Real-time inference & rule-based safety fallbacks
│   │   └── train.py            # Training pipeline, challenge benchmark & backtesting
│   ├── models/
│   │   └── domain.py           # SQLAlchemy database entities (User, Transaction, Goal, Audit)
│   ├── repositories/
│   │   └── domain_repo.py      # Data access layer & SHA-256 hash deduplication
│   ├── schemas/
│   │   ├── schemas.py          # Strict Pydantic v2 input/output validation models
│   │   └── ai_schemas.py       # ML categorization & copilot request schemas
│   ├── services/
│   │   ├── importer.py         # CSV & XLSX statement parser & validation
│   │   ├── forecaster.py       # Cash-flow rolling forecaster & recurring detector
│   │   ├── risk_engine.py      # Safety buffer breach analyzer & risk classifier
│   │   ├── optimizer.py        # SciPy constraint-based savings optimizer
│   │   ├── copilot.py          # Grounded AI money buddy query handler
│   │   ├── gpay_parser.py      # GPay notification regex & security parser
│   │   └── evidence.py         # Explainable AI report generator
│   └── main.py                 # FastAPI application factory & static web router
├── frontend/                   # HTML5 / CSS3 / Vanilla JS SPA Dashboard
│   ├── dashboard.html          # Overview & real-time metrics
│   ├── forecasts.html          # 90-day cash flow & risk timeline
│   ├── savings.html            # Goals hub & SciPy surplus allocator
│   ├── time-machine.html       # Scenario simulation sandbox
│   ├── reports.html            # Categorical charts & privacy receipts
│   ├── smart-capture.html      # GPay AutoSync & notification capture demo
│   ├── chat.html               # Milo conversational assistant
│   └── server.js               # Node.js Express static gateway & API proxy
├── tests/                      # 118 automated test cases across 6 suites
└── requirements.txt            # Pinned Python dependencies
```

---

## ⚡ Quick Start (2-Minute Setup)

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.12 and 3.14)
- **Node.js 18+** (Optional, for frontend Express server)

### 2. Install Backend Dependencies
```bash
# Clone the repository
git clone https://github.com/sunidhiv018/hack-a-night-project.git
cd hack-a-night-project

# Create and activate virtual environment (recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### 3. Start the Application
```bash
# Start FastAPI backend & integrated frontend on port 8000
uvicorn app.main:app --reload --port 8000
```

- 🌐 **Web Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- 📚 **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 📖 **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

*(Optional) If running the standalone Node.js frontend gateway:*
```bash
cd frontend
npm install
npm start
# Opens frontend on http://localhost:3001
```

---

## 🧪 Testing & ML Verification

### Run the Full Test Suite
The project includes 118 automated unit and integration tests covering API endpoints, database isolation, risk calculations, ML pipelines, and GPay capture:
```bash
python -m pytest tests/ -v
```
```
====================== 118 passed in 6.89s (100%) ======================
```

### Run ML Training & Challenge Benchmark
```bash
python app/ml/train.py
```
- **Synthetic Accuracy**: 100.0% on clean standard financial transactions.
- **Hard Challenge Accuracy**: 61.9% (Macro-F1: 0.6313) on ambiguous, misspelled entries.
- **Safety Guardrail**: Transactions with prediction probability $< 0.45$ are flagged as `"Needs Review"` rather than hallucinating categories.
- **Anomaly Detection**: `IsolationForest` achieves **0.7857 Precision / 0.7857 Recall** with **100% Severe Outlier Recall**.

---

## 🔌 Core API Endpoints

| Category | Method & Path | Description |
| :--- | :--- | :--- |
| **Users** | `POST /api/v1/users` | Register a new user profile |
| **Imports** | `POST /api/v1/transactions/preview-import` | Upload & preview CSV/XLSX statements with deduplication |
| | `POST /api/v1/transactions/confirm-import` | Commit verified import records into the ledger |
| | `GET /api/v1/transactions` | Retrieve paginated transactions |
| **Analytics** | `GET /api/v1/dashboard/summary` | Fetch balance, income, expenses, and category metrics |
| | `GET /api/v1/forecasting/cashflow` | Generate 7/14/30/60/90-day cash flow forecast & risk level |
| | `POST /api/v1/simulations/scenario` | Run non-destructive Financial Time Machine scenarios |
| **Goals** | `POST /api/v1/goals` | Create a priority-weighted savings target |
| | `GET /api/v1/goals/optimize` | Run SciPy SLSQP optimization to distribute monthly surplus |
| **Smart Sync** | `POST /api/v1/notifications/listener` | Ingest and parse UPI / GPay notification payloads safely |
| **AI Copilot** | `POST /api/v1/copilot/query` | Ask Milo financial questions grounded in user ledger data |
| **Audit** | `GET /api/v1/privacy/receipts` | Retrieve cryptographic ledger of processed operations |

---

## 🔒 Security, Privacy & Design Principles

1. **Multi-Tenant User Isolation**: Every database operation strictly filters by verified `user_id`.
2. **SQL Injection Immunity**: 100% parameterized SQLAlchemy ORM queries; no raw SQL string concatenation.
3. **Zero-Knowledge GPay Capture**: Notification text is parsed locally using deterministic regular expressions. Sensitive PINs, passwords, and OTPs are stripped and never stored or transmitted.
4. **Account Aggregator (AA) Design**: Direct consumer banking APIs are restricted in India by RBI/NPCI regulations. The project implements standard Open Banking / AA integration patterns alongside Excel/CSV imports.

---

## 👥 Team & Submission

- **Project**: BrokeNoMore
- **Submission Track**: Hack-a-Night Hackathon
- **Repository**: [https://github.com/sunidhiv018/hack-a-night-project](https://github.com/sunidhiv018/hack-a-night-project.git)
- **License**: MIT
