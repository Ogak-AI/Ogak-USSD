<p align="center">
  <h1 align="center">🇳🇬 Ogak USSD Platform</h1>
  <p align="center">
    <strong>Non-P2P Crypto-Fiat Integration via USSD for Nigeria</strong>
  </p>
  <p align="center">
    Buy and sell cryptocurrency using any mobile phone — no internet required.<br/>
    Powered by Interledger Protocol (ILP) for atomic settlement, integrated with<br/>
    licensed Nigerian banks and VASPs, and fully compliant with KYC/AML regulations.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white" alt="Redis"/>
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/ILP-Interledger-orange" alt="Interledger"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"/>
</p>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
  - [System Diagram](#system-diagram)
  - [Microservices](#microservices)
  - [ILP Atomic Settlement](#ilp-atomic-settlement)
  - [Open Payments Protocol](#open-payments-protocol)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Configuration](#environment-configuration)
  - [Database Setup](#database-setup)
  - [Running the Platform](#running-the-platform)
- [Services & Ports](#services--ports)
- [USSD Flow](#ussd-flow)
  - [Menu Tree](#menu-tree)
  - [Buy Crypto Flow](#buy-crypto-flow)
  - [Sell Crypto Flow](#sell-crypto-flow)
  - [Bank & BVN Linking (KYC Upgrade)](#bank--bvn-linking-kyc-upgrade)
- [API Reference](#api-reference)
  - [USSD Callback Endpoint](#ussd-callback-endpoint)
  - [Open Payments Endpoints](#open-payments-endpoints)
  - [Webhook Endpoints](#webhook-endpoints)
  - [Admin Dashboard API](#admin-dashboard-api)
- [Database Schema](#database-schema)
- [KYC / AML Compliance](#kyc--aml-compliance)
- [Integrations](#integrations)
  - [Banking Providers](#banking-providers)
  - [Crypto Exchanges / VASPs](#crypto-exchanges--vasps)
  - [Africa's Talking](#africas-talking)
- [Configuration Reference](#configuration-reference)
- [Docker Deployment](#docker-deployment)
- [Development](#development)
  - [Code Quality](#code-quality)
  - [Testing](#testing)
  - [Migrations](#migrations)
- [Examples](#examples)
- [Security](#security)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

**Ogak** is a production-grade USSD platform that enables any Nigerian mobile phone user to buy and sell cryptocurrency (USDT, USDC, BTC, ETH) using Nigerian Naira (NGN) — without needing a smartphone or internet connection.

The platform operates on a **non-P2P model**: all transactions are routed through licensed Nigerian banks (via Paystack/Flutterwave) and SEC-licensed Virtual Asset Service Providers (VASPs) like Quidax and Busha. This design ensures regulatory compliance while providing the accessibility of USSD.

At the heart of Ogak's settlement engine is the **Interledger Protocol (ILP)**, which provides cryptographic atomicity guarantees for every transaction. A SHA-256 condition/fulfillment mechanism ensures that either both the fiat and crypto legs of a transaction settle, or neither does — protecting users from partial execution.

---

## Key Features

| Feature | Description |
|---|---|
| 📱 **USSD-First** | Works on any GSM phone — no smartphone or internet required |
| 🔄 **Atomic Settlement** | ILP condition/fulfillment model ensures all-or-nothing execution |
| 🏦 **Licensed Banking** | Integrated with Paystack, Flutterwave, NIP/NIBSS for fiat operations |
| 🪙 **Multi-Crypto** | Supports USDT, USDC, BTC, ETH, BNB via licensed VASPs (Quidax, Busha, Binance) |
| 🛡️ **KYC/AML Tiered** | 4-tier KYC system (Tier 0–3) with progressive transaction limits |
| 🌐 **Open Payments** | Standards-compliant Open Payments API for interoperability with Rafiki and ILP ecosystem |
| 📊 **Admin Dashboard** | Real-time monitoring with WebSocket-powered transaction feeds |
| 🌍 **Multi-Language** | English, Nigerian Pidgin, Yoruba, Hausa, and Igbo support |
| 🐳 **Docker-Ready** | Full docker-compose stack with PostgreSQL, Redis, and Celery |
| 🔐 **PIN Security** | PBKDF2-HMAC-SHA256 PIN hashing with brute-force lockout |
| 📝 **Audit Trail** | Immutable audit logging for every sensitive operation |

---

## Architecture

### System Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Mobile User (any GSM phone)                     │
│                         Dials *384*OGAK# via USSD                        │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                     Africa's Talking USSD Gateway                          │
│                 (HTTP callback to Ogak USSD Service)                       │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          OGAK PLATFORM (4 Services)                         │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  ┌──────────────┐    │
│  │  USSD Engine │  │  API Gateway │  │ ILP Connector  │  │    Admin     │    │
│  │   :8000      │  │    :8001     │  │    :8002       │  │   :8003      │    │
│  │              │  │              │  │                │  │              │    │
│  │ Menu State   │  │ Open Payments│  │ Prepare →      │  │ Dashboard    │    │
│  │ Machine      │  │ Webhooks     │  │ Fulfill/Reject │  │ WebSocket    │    │
│  │ PIN Auth     │  │ REST API     │  │ Atomic Guard   │  │ Stats API    │    │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  └──────────────┘    │
│         │                 │                   │                               │
│         └────────────┬────┴───────────────────┘                               │
│                      ▼                                                        │
│  ┌──────────────────────────────────────────┐                                │
│  │            Services Layer                 │                                │
│  │  TransactionOrchestrator                  │                                │
│  │  QuoteService  │  RateService             │                                │
│  │  UserService   │  OpenPaymentsService     │                                │
│  └──────────────────────┬────────────────────┘                                │
│                         │                                                     │
│  ┌──────────────────────┴────────────────────┐                                │
│  │          Data Layer (packages/db)          │                                │
│  │  PostgreSQL (async) │ Redis (sessions)     │                                │
│  │  Alembic Migrations │ SQLAlchemy 2.0 ORM   │                                │
│  └────────────────────────────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────────┘
         │                      │                     │
         ▼                      ▼                     ▼
  ┌──────────────┐   ┌──────────────────┐   ┌─────────────────┐
  │   Nigerian    │   │  Crypto Exchanges │   │   Celery Worker  │
  │    Banks      │   │  / VASPs          │   │  (Async Tasks)   │
  │               │   │                   │   │                  │
  │  Paystack     │   │  Quidax (SEC)     │   │  Settlement      │
  │  Flutterwave  │   │  Busha (SEC)      │   │  Rollbacks       │
  │  NIP/NIBSS    │   │  Binance          │   │  Notifications   │
  └──────────────┘   └───────────────────┘   └──────────────────┘
```

### Microservices

The platform is composed of **four independent FastAPI services**, each with its own entry point and port:

| Service | Port | Entry Point | Description |
|---|---|---|---|
| **USSD Engine** | 8000 | `packages.ussd.main:app` | Africa's Talking callback handler, menu state machine, session management |
| **API Gateway** | 8001 | `packages.api.main:app` | REST API, Open Payments, webhook receivers, quote engine |
| **ILP Connector** | 8002 | `packages.ilp_connector.connector` | Atomic settlement coordination via condition/fulfillment model |
| **Admin Dashboard** | 8003 | `packages.admin.main:app` | Real-time monitoring, WebSocket feeds, transaction browser, audit log |

### ILP Atomic Settlement

Every crypto-fiat transaction follows the ILP **Prepare → Fulfill/Reject** model:

```
1. PREPARE
   ├── Generate SHA-256 condition + fulfillment (random 32-byte preimage)
   ├── Lock the quote with condition attached
   ├── Initiate fiat leg (bank charge/credit via Paystack/Flutterwave)
   └── Initiate crypto leg (exchange order via Quidax/Busha)

2. FULFILL (on success of both legs)
   ├── Reveal preimage (fulfillment) that hashes to the condition
   ├── Finalize bank settlement
   ├── Finalize crypto credit
   └── Mark transaction COMPLETED

3. REJECT (on any failure)
   ├── ILP packet rejection
   ├── Best-effort rollback of partial legs
   └── Mark transaction FAILED / ROLLED_BACK
```

**Key guarantees:**
- No funds are custodied by Ogak beyond the brief coordination window
- The condition/fulfillment invariant prevents partial settlement
- All settlement happens on the actual bank and licensed VASP rails

### Open Payments Protocol

Ogak implements the **receiver side** of the [Open Payments](https://openpayments.dev/) specification, enabling external wallets and Rafiki instances to send value into Ogak users:

- **Wallet Address Resolution** — Standard discovery endpoint for payment pointers
- **GNAP Grant Server** — Non-interactive grant issuance for incoming payment creation
- **Resource Server** — Incoming payment creation and status tracking (DB-persisted)
- **Internal Fulfillment** — Settlement hook called only by the real ILP connector/settlement engine

---

## Project Structure

```
ogak-ussd/
├── packages/                        # Main application code (monorepo-style)
│   ├── __init__.py
│   ├── ussd/                        # USSD Engine (port 8000)
│   │   ├── main.py                  # FastAPI app + lifespan
│   │   ├── gateway.py               # Africa's Talking callback handler
│   │   ├── menu.py                  # USSD menu state machine (531 lines)
│   │   └── session.py               # Redis-backed session manager
│   │
│   ├── api/                         # API Gateway (port 8001)
│   │   ├── main.py                  # FastAPI app with all routers
│   │   ├── open_payments.py         # Open Payments protocol endpoints
│   │   ├── banks.py                 # Paystack + Flutterwave integrations
│   │   ├── exchanges.py             # Quidax + Binance integrations
│   │   └── webhooks.py              # Provider webhook receivers
│   │
│   ├── ilp_connector/               # ILP Connector (port 8002)
│   │   ├── __init__.py
│   │   └── connector.py             # Prepare/Fulfill/Reject engine
│   │
│   ├── admin/                       # Admin Dashboard (port 8003)
│   │   ├── main.py                  # Dashboard with WebSocket + stats API
│   │   └── routes/                  # Additional admin routes (extensible)
│   │
│   ├── services/                    # Business Logic Layer
│   │   ├── transaction_orchestrator.py  # Atomic buy/sell execution engine
│   │   ├── quote_service.py         # Live rate quoting with ILP conditions
│   │   ├── rate_service.py          # Real-time rate aggregation + caching
│   │   ├── user_service.py          # User management, PIN, KYC operations
│   │   └── open_payments_service.py # Incoming payment persistence + fulfillment
│   │
│   ├── db/                          # Data Access Layer
│   │   ├── database.py              # Async SQLAlchemy engine + session factory
│   │   └── models.py                # ORM models (User, Transaction, Quote, etc.)
│   │
│   └── shared/                      # Shared Utilities
│       ├── config.py                # Pydantic Settings (env-driven)
│       ├── constants.py             # Nigerian banks, KYC limits, ILP constants
│       ├── crypto_utils.py          # AES-256-GCM encryption, PIN hashing, ILP crypto
│       ├── errors.py                # Structured exception hierarchy
│       └── types.py                 # Pydantic models + enums (499 lines)
│
├── migrations/                      # Alembic database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial.py           # Users, bank accounts, transactions, quotes, audit
│       └── 002_add_open_payments_incoming_payments.py
│
├── examples/
│   └── open_payments_receive_demo.py  # Python client demonstrating OP receive flow
│
├── .env.example                     # Complete environment variable template (111 vars)
├── alembic.ini                      # Alembic configuration
├── docker-compose.yml               # Full stack: 6 services + volumes + networks
├── Dockerfile                       # Multi-stage build (dev + production)
├── pyproject.toml                   # Project metadata, scripts, tool configs
├── requirements.txt                 # Pinned Python dependencies
├── .gitignore
└── README.md                        # ← You are here
```

---

## Tech Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Runtime** | Python | 3.11+ | Core language |
| **Framework** | FastAPI | 0.115.6 | All 4 microservices |
| **Server** | Uvicorn | 0.34.0 | ASGI server with hot reload |
| **ORM** | SQLAlchemy | 2.0.36 | Async ORM with `asyncpg` driver |
| **Database** | PostgreSQL | 16 | Primary data store |
| **Cache/Sessions** | Redis | 7 | USSD sessions, rate caching, Celery broker |
| **Migrations** | Alembic | 1.14.1 | Schema versioning |
| **Validation** | Pydantic | 2.10.4 | Request/response models, settings |
| **HTTP Client** | httpx | 0.28.1 | Async provider API calls |
| **Task Queue** | Celery | 5.4.0 | Async settlement, rollbacks |
| **Encryption** | cryptography | 44.0.0 | AES-256-GCM, PBKDF2 |
| **Logging** | structlog | 24.4.0 | Structured JSON logging |
| **USSD Gateway** | Africa's Talking | 1.2.7 | USSD shortcode + SMS |
| **Containerization** | Docker | Multi-stage | Dev + production images |
| **Code Quality** | Ruff + mypy | Latest | Linting + type checking |
| **Testing** | pytest + pytest-asyncio | 8.3+ | Async test support |

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 16+**
- **Redis 7+**
- **Docker & Docker Compose** (optional, for containerized deployment)

### Installation

**1. Clone the repository:**

```bash
git clone https://github.com/Ogak-AI/Ogak-USSD.git
cd Ogak-USSD
```

**2. Create and activate a virtual environment:**

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
.\venv\Scripts\activate
```

**3. Install dependencies:**

```bash
pip install -r requirements.txt
```

**4. Install the project in development mode:**

```bash
pip install -e .
```

### Environment Configuration

Copy the example environment file and fill in your production values:

```bash
cp .env.example .env
```

> ⚠️ **Important:** Never commit the `.env` file. All placeholder values in `.env.example` are clearly marked with `REPLACE_` prefixes.

Key environment variables to configure:

| Variable | Description | Required |
|---|---|---|
| `APP_SECRET_KEY` | 64-char hex secret for JWT/sessions | ✅ |
| `APP_ENCRYPTION_KEY` | 32-byte hex key for AES-256-GCM | ✅ |
| `DATABASE_URL` | PostgreSQL async connection string | ✅ |
| `REDIS_URL` | Redis connection URL | ✅ |
| `AT_USERNAME` / `AT_API_KEY` | Africa's Talking production credentials | ✅ |
| `FLW_SECRET_KEY` | Flutterwave live secret key | ✅ |
| `PAYSTACK_SECRET_KEY` | Paystack live secret key | ✅ |
| `QUIDAX_SECRET_KEY` | Quidax API key (SEC-licensed VASP) | ✅ |

See the full [Configuration Reference](#configuration-reference) for all 111 variables.

### Database Setup

**1. Ensure PostgreSQL is running and a database exists:**

```bash
# via psql
createdb ogak_db
```

**2. Run Alembic migrations:**

```bash
alembic upgrade head
```

This creates all tables: `users`, `bank_accounts`, `exchange_accounts`, `quotes`, `transactions`, `audit_logs`, and `open_payments_incoming_payments`.

### Running the Platform

**Option A: Individual services (development)**

```bash
# Terminal 1 — USSD Engine
uvicorn packages.ussd.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — API Gateway
uvicorn packages.api.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 3 — ILP Connector (runs within API for lightweight setups)
uvicorn packages.ilp_connector.main:app --host 0.0.0.0 --port 8002 --reload

# Terminal 4 — Admin Dashboard
uvicorn packages.admin.main:app --host 0.0.0.0 --port 8003 --reload

# Terminal 5 — Celery Worker (async tasks)
celery -A packages.api.worker worker --loglevel=info --concurrency=4
```

**Option B: Using project scripts (after `pip install -e .`)**

```bash
ogak-ussd    # Start USSD engine on port 8000
ogak-api     # Start API gateway on port 8001
ogak-ilp     # Start ILP connector on port 8002
ogak-admin   # Start admin dashboard on port 8003
```

**Option C: Docker Compose (recommended for production)**

```bash
docker-compose up -d
```

This spins up all 6 containers: PostgreSQL, Redis, USSD, API, ILP Connector, Admin, and Celery Worker.

---

## Services & Ports

| Service | Container Name | Port | Health Check |
|---|---|---|---|
| PostgreSQL | `ogak-postgres` | 5432 | `pg_isready` |
| Redis | `ogak-redis` | 6379 | `redis-cli ping` |
| USSD Engine | `ogak-ussd` | 8000 | `GET /health` |
| API Gateway | `ogak-api` | 8001 | `GET /health` |
| ILP Connector | `ogak-ilp` | 8002 | `GET /health` |
| Admin Dashboard | `ogak-admin` | 8003 | `GET /admin/health` |
| Celery Worker | `ogak-celery` | — | — |

---

## USSD Flow

### Menu Tree

```
*384*OGAK#
│
├── 1. Buy Crypto (NGN → USDT/BTC/USDC/ETH)
│   ├── Enter amount in Naira (min ₦5,000)
│   ├── Select crypto asset (1. USDT  2. USDC  3. BTC  4. ETH)
│   ├── View live quote (rate, fee, total)
│   ├── Confirm & Pay
│   └── Enter PIN → Transaction submitted
│
├── 2. Sell Crypto (Crypto → NGN)
│   ├── Enter Naira value
│   ├── Select crypto (1. USDT  2. BTC  3. ETH)
│   ├── View sell quote
│   ├── Confirm
│   └── Enter PIN → Funds credited to bank
│
├── 3. Check Live Rates
│   └── USDT: ₦X,XXX  |  BTC: ₦XX,XXX,XXX  (from Quidax + spread)
│
├── 4. Link Bank Account (KYC Tier 2 Upgrade)
│   ├── Select bank (Access, GTB, Zenith, UBA, FirstBank, Kuda, OPay, PalmPay...)
│   ├── Enter 10-digit account number
│   ├── Verify account name (via Flutterwave)
│   ├── Enter 11-digit BVN
│   └── Confirm → Upgraded to Tier 2 (₦500k/tx, ₦5M daily)
│
├── 5. My Transactions (coming soon)
│
├── 6. Help & Support
│   └── support@ogak.ng
│
└── 0. Exit
```

### Buy Crypto Flow

1. User enters NGN amount (minimum ₦5,000)
2. Selects crypto asset (USDT, USDC, BTC, or ETH)
3. **QuoteService** fetches live rate from Quidax, applies 1.5% spread + 0.5% fee
4. **ILP condition/fulfillment** pair is generated (SHA-256 preimage)
5. Quote is persisted in DB with 2-minute expiry
6. User confirms and enters PIN
7. **TransactionOrchestrator** executes atomically:
   - ILP PREPARE → Fiat debit (Flutterwave) → Crypto buy (Quidax) → ILP FULFILL
8. User receives confirmation with transaction reference

### Sell Crypto Flow

Symmetric to buy, but legs are reversed:
1. Crypto is debited from the user's exchange account first
2. Fiat is credited to the user's linked bank account
3. ILP FULFILL confirms atomic completion

### Bank & BVN Linking (KYC Upgrade)

1. User selects their bank from a list of 18+ Nigerian banks
2. Enters 10-digit NUBAN account number
3. Account name is resolved live via Flutterwave's `/accounts/resolve` API
4. User enters 11-digit BVN for verification
5. On success: KYC tier upgraded to Tier 2 with increased limits

---

## API Reference

### USSD Callback Endpoint

```
POST /api/v1/ussd/callback
```

This is the production Africa's Talking USSD webhook. Register it in your AT dashboard for your live shortcode.

**Request body** (form-encoded by AT):

| Field | Type | Description |
|---|---|---|
| `sessionId` | string | Unique session identifier |
| `serviceCode` | string | USSD shortcode (e.g., `*384*OGAK#`) |
| `phoneNumber` | string | User's phone in E.164 format |
| `text` | string | Concatenated user inputs (e.g., `1*25000*1`) |
| `networkCode` | string | Mobile network code (optional) |

**Response:** `{"USSD": "CON ..." }` or `{"USSD": "END ..."}`

---

### Open Payments Endpoints

#### Wallet Address Discovery
```
GET /api/v1/open-payments/wallet-addresses/{identifier}
```
Returns a standard Open Payments Wallet Address document with `authServer` and `resourceServer` URLs.

#### Grant Request (Non-Interactive)
```
POST /api/v1/open-payments/auth/grants
```
Issues a non-interactive grant for incoming payment creation. Returns an access token.

#### Create Incoming Payment
```
POST /api/v1/open-payments/resource/incoming-payments
Authorization: Bearer <access_token>
```
Creates a DB-persisted incoming payment resource. Fulfillment happens only via real settlement.

#### Get Incoming Payment Status
```
GET /api/v1/open-payments/resource/incoming-payments/{payment_id}
```

#### Create Quote
```
POST /api/v1/open-payments/quotes
```

#### Internal Fulfillment Hook (not public)
```
POST /api/v1/open-payments/internal/incoming-payments/{payment_id}/fulfill
```
Called by the ILP connector/settlement engine when real value arrives.

---

### Webhook Endpoints

| Endpoint | Provider | Purpose |
|---|---|---|
| `POST /api/v1/webhooks/paystack` | Paystack | Fiat settlement confirmation (HMAC-SHA512 verified) |
| `POST /api/v1/webhooks/flutterwave` | Flutterwave | Fiat settlement confirmation |
| `POST /api/v1/webhooks/quidax` | Quidax | Crypto order status updates |
| `POST /api/v1/webhooks/busha` | Busha | Crypto order status updates |

---

### Admin Dashboard API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the admin dashboard HTML |
| `/admin/api/stats` | GET | Real-time platform statistics (users, volume, revenue, status breakdown) |
| `/admin/api/transactions` | GET | Paginated transaction list with status filter |
| `/admin/api/audit-log` | GET | Audit log entries with action filter |
| `/admin/ws` | WS | WebSocket endpoint for live dashboard updates |
| `/admin/health` | GET | Admin service health check |

---

## Database Schema

The platform uses **7 tables** managed by Alembic migrations:

| Table | Description | Key Columns |
|---|---|---|
| `users` | Registered users (phone-identified) | `phone_number`, `hashed_pin`, `kyc_tier`, `bvn_encrypted`, `daily_volume_ngn` |
| `bank_accounts` | Linked Nigerian bank accounts | `bank_code`, `account_number`, `account_name`, `is_verified`, `paystack_recipient_code` |
| `exchange_accounts` | Linked crypto exchange/VASP accounts | `exchange`, `api_key_encrypted`, `api_secret_encrypted`, `is_verified` |
| `quotes` | Locked conversion quotes with ILP conditions | `fiat_amount_ngn`, `crypto_amount`, `exchange_rate`, `ilp_condition`, `ilp_fulfillment_encrypted`, `expires_at` |
| `transactions` | Full transaction records with dual-leg tracking | `status`, `bank_reference`, `exchange_order_id`, `ilp_packet_id`, `ilp_status`, `failure_reason`, `rollback_reference` |
| `audit_logs` | Immutable audit trail | `action`, `resource_type`, `resource_id`, `details`, `ip_address` |
| `open_payments_incoming_payments` | Open Payments incoming payment resources | `wallet_address`, `incoming_amount_value`, `received_amount_value`, `completed`, `fulfillment_reference` |

**Transaction Status Lifecycle:**

```
PENDING → QUOTED → CONFIRMED → EXECUTING → FIAT_SETTLED → CRYPTO_SETTLED → COMPLETED
                                    ↓                                          ↑
                                  FAILED ─────────── ROLLED_BACK               │
                                    ↓                                          │
                                 EXPIRED                                   (success)
```

---

## KYC / AML Compliance

Ogak enforces tiered transaction limits based on identity verification:

| Tier | Verification | Per Transaction Limit | Daily Limit |
|---|---|---|---|
| **Tier 0** | Phone only (unverified) | ₦0 (no transactions) | ₦0 |
| **Tier 1** | Phone + PIN set | ₦50,000 | ₦500,000 |
| **Tier 2** | BVN validated | ₦500,000 | ₦5,000,000 |
| **Tier 3** | Full KYC (ID + address) | ₦5,000,000 | ₦50,000,000 |

- BVN verification is performed via Flutterwave (configurable)
- Daily volume tracking resets at UTC midnight
- PIN lockout after 3 failed attempts (30-minute cooldown)
- All KYC events are logged to the `audit_logs` table

---

## Integrations

### Banking Providers

| Provider | Usage | API |
|---|---|---|
| **Paystack** | Account verification, transfers (credit), recipient management | `https://api.paystack.co` |
| **Flutterwave** | Account verification, charges (debit), transfers, BVN validation | `https://api.flutterwave.com/v3` |

Both providers implement the abstract `BankProvider` interface:
- `verify_account()` — Resolve account name from NUBAN + bank code
- `initiate_debit()` — Charge user's bank account (buy crypto)
- `initiate_credit()` — Transfer NGN to user's bank (sell crypto)
- `get_transaction_status()` — Check settlement status

### Crypto Exchanges / VASPs

| Exchange | Type | Supported Assets | Notes |
|---|---|---|---|
| **Quidax** | SEC-Licensed VASP (Primary) | BTC, USDT, USDC, ETH, BNB | Native NGN pairs, primary provider |
| **Busha** | SEC-Licensed VASP | BTC, USDT, USDC, ETH | Secondary exchange |
| **Binance** | Global Exchange | BTC, USDT, USDC, ETH, BNB | P2P API, returns USDT pairs (RateService converts to NGN) |

All exchanges implement the abstract `ExchangeProvider` interface:
- `get_price()` — Fetch live crypto/NGN rate
- `get_balance()` — Available crypto balance
- `buy_crypto()` — Execute buy order
- `sell_crypto()` — Execute sell order
- `get_order_status()` — Check order completion

### Africa's Talking

- **USSD Gateway** — Production shortcode callback at `/api/v1/ussd/callback`
- **SMS** — Transaction confirmations, OTP, PIN lockout notifications (via SMS templates)
- **Environment** — Must be set to `production` for live shortcode operation

---

## Configuration Reference

The platform is configured entirely through environment variables, loaded via Pydantic Settings. All variables are documented in `.env.example`.

<details>
<summary><strong>Click to expand full configuration reference</strong></summary>

| Category | Variable | Default | Description |
|---|---|---|---|
| **App** | `APP_NAME` | `ogak-ussd` | Application name |
| | `APP_ENV` | `development` | Environment (`production` / `development`) |
| | `APP_DEBUG` | `true` | Debug mode |
| | `APP_SECRET_KEY` | — | 64-char hex secret |
| | `APP_ENCRYPTION_KEY` | — | 32-byte hex key for AES-256-GCM |
| **Ports** | `USSD_PORT` | `8000` | USSD engine port |
| | `API_PORT` | `8001` | API gateway port |
| | `ILP_PORT` | `8002` | ILP connector port |
| | `ADMIN_PORT` | `8003` | Admin dashboard port |
| **Database** | `DATABASE_URL` | `postgresql+asyncpg://...` | Async connection string |
| | `DATABASE_SYNC_URL` | `postgresql://...` | Sync connection (Alembic) |
| **Redis** | `REDIS_URL` | `redis://localhost:6379/0` | Main Redis URL |
| | `REDIS_SESSION_DB` | `1` | DB index for sessions |
| | `REDIS_CACHE_DB` | `2` | DB index for rate cache |
| **Africa's Talking** | `AT_USERNAME` | — | AT production username |
| | `AT_API_KEY` | — | AT production API key |
| | `AT_USSD_SHORTCODE` | `*384*OGAK#` | Live USSD shortcode |
| | `AT_ENVIRONMENT` | `production` | Must be `production` for live |
| **Flutterwave** | `FLW_SECRET_KEY` | — | Live secret key (`FLWSECK-...`) |
| | `FLW_WEBHOOK_SECRET` | — | Webhook signature verification |
| **Paystack** | `PAYSTACK_SECRET_KEY` | — | Live secret key (`sk_live_...`) |
| | `PAYSTACK_WEBHOOK_SECRET` | — | HMAC-SHA512 verification |
| **Quidax** | `QUIDAX_SECRET_KEY` | — | API key for primary VASP |
| **Busha** | `BUSHA_API_KEY` | — | Secondary exchange API key |
| **Binance** | `BINANCE_API_KEY` | — | Global exchange API key |
| **ILP** | `ILP_CONNECTOR_ADDRESS` | `g.ogak.ng.connector` | ILP address prefix |
| | `ILP_CONNECTOR_SECRET` | — | Min 32-char secret |
| | `ILP_MAX_PACKET_AMOUNT` | `1000000000` | Max ILP packet (₦10M in kobo) |
| | `ILP_DEFAULT_SPREAD_BPS` | `150` | Default spread (1.5%) |
| **KYC** | `KYC_TIER1_TX_LIMIT_NGN` | `50000` | Tier 1 per-transaction limit |
| | `KYC_TIER2_TX_LIMIT_NGN` | `500000` | Tier 2 per-transaction limit |
| | `KYC_TIER3_TX_LIMIT_NGN` | `5000000` | Tier 3 per-transaction limit |
| | `BVN_VALIDATION_PROVIDER` | `flutterwave` | BVN verification provider |
| **USSD** | `USSD_SESSION_TTL_SECONDS` | `180` | Session timeout (3 minutes) |
| | `USSD_MAX_PIN_ATTEMPTS` | `3` | Attempts before lockout |
| | `USSD_PIN_LOCKOUT_SECONDS` | `1800` | Lockout duration (30 minutes) |
| **Rates** | `RATE_CACHE_TTL_SECONDS` | `30` | Rate cache duration |
| | `RATE_QUOTE_EXPIRY_SECONDS` | `120` | Quote validity window |
| | `RATE_SPREAD_BPS` | `150` | Platform spread (1.5%) |
| **Celery** | `CELERY_BROKER_URL` | `redis://localhost:6379/3` | Task queue broker |
| | `CELERY_RESULT_BACKEND` | `redis://localhost:6379/4` | Task result store |
| **Logging** | `LOG_LEVEL` | `INFO` | Log verbosity |
| | `LOG_FORMAT` | `json` | Log format (`json` / `text`) |
| **CORS** | `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed origins |
| **Open Payments** | `OP_PUBLIC_BASE_URL` | `http://localhost:8001` | Public base URL for OP endpoints |

</details>

---

## Docker Deployment

### Development

```bash
docker-compose up -d
```

This starts all services with hot-reload enabled and source code mounted as volumes.

### Production

The `Dockerfile` includes a production stage that:
- Creates a non-root `ogak` user
- Runs Uvicorn with 4 workers
- Exposes ports 8000–8004

```bash
docker-compose -f docker-compose.yml up -d --build
```

### Infrastructure

- **PostgreSQL 16 Alpine** — Persistent volume `postgres_data`, health-checked via `pg_isready`
- **Redis 7 Alpine** — AOF persistence, 256MB max memory with LRU eviction, health-checked via `redis-cli ping`
- All services connected via `ogak-network` bridge network

---

## Development

### Code Quality

```bash
# Lint with Ruff
ruff check packages/

# Format with Ruff
ruff format packages/

# Type check with mypy (strict mode)
mypy packages/
```

The project enforces:
- Python 3.11 target
- 100-char line length
- Strict mypy (no untyped defs, warn on `Any` returns)
- Pre-commit hooks for automated checks

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=packages --cov-report=html

# Run specific test file
pytest tests/test_quote_service.py -v
```

Test configuration in `pyproject.toml`:
- `asyncio_mode = "auto"` for seamless async test support
- Verbose output with short tracebacks

### Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# View migration history
alembic history
```

---

## Examples

### Open Payments Receive Demo

The `examples/open_payments_receive_demo.py` script demonstrates the receive-side Open Payments flow:

```bash
# Start Ogak API on port 8001, then:
python examples/open_payments_receive_demo.py \
    --receiver http://localhost:8001/api/v1/open-payments/wallet-addresses/+2348012345678 \
    --amount 5000
```

This performs real protocol steps:
1. Fetches the wallet address document
2. Requests a non-interactive incoming-payment grant
3. Creates an incoming payment on the resource server

Fulfillment must be driven by the real settlement layer — no simulation is used.

---

## Security

| Mechanism | Implementation |
|---|---|
| **PIN Hashing** | PBKDF2-HMAC-SHA256 with 100,000 iterations + random 16-byte salt |
| **Data Encryption** | AES-256-GCM for BVN, API keys, ILP fulfillments (12-byte nonce) |
| **Webhook Verification** | HMAC-SHA512 for Paystack, hash verification for Flutterwave |
| **ILP Condition/Fulfillment** | SHA-256 preimage scheme (32-byte condition, 32-byte fulfillment) |
| **Session Management** | Redis with TTL-based expiry (180 seconds for USSD) |
| **PIN Brute-Force Protection** | 3 attempts → 30-minute lockout with account lock flag |
| **Phone Masking** | `+234801****678` format in logs and displays |
| **BVN Masking** | `*******8901` format for display, encrypted at rest |
| **Non-Root Container** | Production Docker image runs as `ogak` user |

---

## Roadmap

- [ ] Transaction history in USSD menu (Menu 5)
- [ ] Full outgoing payments (sender-side Open Payments)
- [ ] Interactive GNAP grants with user consent UI
- [ ] SMS OTP for high-value transactions
- [ ] Multi-exchange rate aggregation (best rate selection)
- [ ] Webhook event processing for Celery settlement completion
- [ ] Admin dashboard frontend (HTML/JS client)
- [ ] Full Rafiki integration for production ILP peering
- [ ] Rate limiting via SlowAPI middleware
- [ ] Complete i18n for Yoruba, Hausa, and Igbo languages

---

## License

This project is licensed under the **MIT License**. See the [pyproject.toml](pyproject.toml) for details.

---

<p align="center">
  Built with ❤️ for financial inclusion in Nigeria<br/>
  <strong>Ogak Team</strong> — Making crypto accessible to everyone, no smartphone needed.
</p>