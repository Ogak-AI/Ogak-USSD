<p align="center">
  <h1 align="center">🇳🇬 Ogak USSD Platform</h1>
  <p align="center">
    <strong>Crypto-Fiat Trading via USSD for Nigeria</strong>
  </p>
  <p align="center">
    Buy and sell cryptocurrency on any mobile phone — no internet required.<br/>
    Uses Interledger Protocol (ILP) for atomic settlement between fiat and crypto legs,<br/>
    integrated with licensed Nigerian banks and VASPs, fully KYC/AML compliant.
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

Ogak lets any Nigerian dial *384*OGAK# on their phone and trade crypto — no smartphone, no internet, just USSD. You can buy USDT, USDC, BTC, ETH, or BNB with Naira, or sell crypto back for cash.

Transactions run through licensed Nigerian banks (Paystack, Flutterwave, NIP/NIBSS) and SEC-licensed crypto providers (Quidax, Busha). This matters because KYC/AML isn't bolted on after the fact — it's baked into the integration from the start. You fund through your actual bank account, so there's no pretending about identity.

The settlement engine uses ILP. Every transaction is locked by a SHA-256 condition: both the fiat and crypto sides complete together, or the transaction rolls back entirely. No partial fills, no settlement risk.

---

## Key Features

| Feature | Details |
|---|---|
| **USSD-First** | Works on any GSM phone — no smartphone or internet |
| **Atomic Settlement** | ILP condition/fulfillment: both sides settle or neither does |
| **Licensed Banking** | Paystack, Flutterwave, NIP/NIBSS for fiat |
| **Multi-Crypto** | USDT, USDC, BTC, ETH, BNB via Quidax, Busha, Binance |
| **4-Tier KYC** | Progressive limits: Tier 0–3 |
| **Open Payments** | Interoperable with Rafiki and the ILP ecosystem |
| **Real-Time Monitoring** | WebSocket dashboard for live transaction feeds |
| **Multi-Language** | English, Nigerian Pidgin, Yoruba, Hausa, Igbo |
| **Docker-Ready** | PostgreSQL, Redis, Celery stack included |
| **PIN Security** | PBKDF2-HMAC-SHA256, 100k iterations, 3-attempt lockout |
| **Audit Trail** | Immutable logs for every sensitive operation |

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

Four services, each independent:

| Service | Port | Entry Point | Job |
|---|---|---|---|
| **USSD Engine** | 8000 | `packages.ussd.main:app` | Africa's Talking callbacks, menu state machine, sessions |
| **API Gateway** | 8001 | `packages.api.main:app` | REST API, Open Payments, webhook handlers, quotes |
| **ILP Connector** | 8002 | `packages.ilp_connector.connector` | Condition/fulfillment coordination, atomic settlement |
| **Admin Dashboard** | 8003 | `packages.admin.main:app` | Real-time monitoring, WebSocket feeds, audit logs |

### ILP Atomic Settlement

Every transaction uses Prepare → Fulfill/Reject:

```
1. PREPARE
   ├── Generate SHA-256 condition + fulfillment (32-byte preimage)
   ├── Lock quote with condition attached
   ├── Start fiat leg (bank charge/credit via Paystack/Flutterwave)
   └── Start crypto leg (exchange order via Quidax/Busha)

2. FULFILL (both legs succeed)
   ├── Reveal fulfillment (preimage that hashes to condition)
   ├── Finalize bank settlement
   ├── Finalize crypto credit
   └── Mark transaction COMPLETED

3. REJECT (any failure)
   ├── Send ILP packet rejection
   ├── Best-effort rollback of partial legs
   └── Return funds to user
```

The condition is the lock: you can't claim funds on either side without the right preimage. Both legs wait for each other.

---

## Project Structure

```
ogak-ussd/
├── packages/
│   ├── ussd/                    # USSD menu engine
│   │   ├── main.py              # FastAPI app (port 8000)
│   │   ├── menu.py              # State machine
│   │   └── flows.py             # Buy/sell/KYC flows
│   ├── api/                     # REST API
│   │   ├── main.py              # FastAPI app (port 8001)
│   │   ├── routes/              # OpenAPI/webhook handlers
│   │   └── quote_service.py     # Rate and quote engine
│   ├── ilp_connector/           # ILP settlement
│   │   ├── connector.py         # Main service (port 8002)
│   │   ├── prepare.py           # Condition/fulfillment logic
│   │   └── settlement.py        # Atomic transaction coordination
│   ├── admin/                   # Admin dashboard
│   │   ├── main.py              # FastAPI app (port 8003)
│   │   └── ws.py                # WebSocket feeds
│   ├── db/                      # Database layer
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── migrations/          # Alembic schema versions
│   │   └── async_session.py     # Async DB session factory
│   ├── core/                    # Shared utilities
│   │   ├── config.py            # Environment parsing
│   │   ├── security.py          # PIN hashing, encryption
│   │   └── cache.py             # Redis client
│   └── integrations/
│       ├── paystack/            # Paystack API client
│       ├── flutterwave/         # Flutterwave API client
│       ├── quidax/              # Quidax exchange client
│       └── africas_talking/     # Africa's Talking USSD client
├── tests/                       # Pytest test suite
├── examples/                    # Example scripts
├── docker-compose.yml           # Local dev stack
├── Dockerfile                   # Multi-stage production build
├── pyproject.toml               # Python project config
├── .pre-commit-config.yaml      # Code quality hooks
└── README.md                    # This file
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| **Language** | Python 3.11+ |
| **Web Framework** | FastAPI 0.115 |
| **Database** | PostgreSQL 16 (async via asyncpg) |
| **Cache / Sessions** | Redis 7 (AOF persistence, LRU eviction) |
| **Task Queue** | Celery + Redis broker |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Migrations** | Alembic |
| **Crypto Hashing** | bcrypt (PIN), AES-256-GCM (BVN/keys) |
| **ILP** | Interledger core libraries + custom connector |
| **USSD Gateway** | Africa's Talking (Nigeria-optimized) |
| **HTTP Client** | httpx (async) |
| **Containers** | Docker + Docker Compose |
| **Code Quality** | Ruff (lint/format), mypy (type check) |
| **Testing** | pytest + pytest-asyncio |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker + Docker Compose (for local stack)
- Africa's Talking account + credentials
- Paystack and Flutterwave live keys
- Quidax and Busha API keys

### Installation

```bash
git clone https://github.com/Ogak-AI/Ogak-USSD.git
cd Ogak-USSD
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### Environment Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Key variables:

- **Database:** `DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ogak`
- **Redis:** `REDIS_URL=redis://localhost:6379/0`
- **Africa's Talking:** `AT_USERNAME=...`, `AT_API_KEY=...`
- **Paystack:** `PAYSTACK_SECRET_KEY=...`
- **Flutterwave:** `FLW_SECRET_KEY=...`
- **ILP:** `ILP_CONNECTOR_SECRET=...` (32+ chars)

See **Configuration Reference** below for the full list.

### Database Setup

```bash
# Run migrations
alembic upgrade head

# Seed initial KYC tiers (optional)
python -m packages.db.seed
```

### Running the Platform

**Development (with hot-reload):**

```bash
docker-compose up -d
```

Starts:
- USSD Engine on `http://localhost:8000`
- API Gateway on `http://localhost:8001`
- ILP Connector on `http://localhost:8002`
- Admin Dashboard on `http://localhost:8003`

**Production:**

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

---

## Services & Ports

| Service | Port | Health Check |
|---|---|---|
| USSD Engine | 8000 | `GET /health` |
| API Gateway | 8001 | `GET /health` |
| ILP Connector | 8002 | `GET /health` |
| Admin Dashboard | 8003 | `GET /health` |
| PostgreSQL | 5432 | `pg_isready` |
| Redis | 6379 | `redis-cli ping` |

---

## USSD Flow

### Menu Tree

```
*384*OGAK#
├─ 1. Buy Crypto
│  ├─ 1. USDT (Enter amount)
│  ├─ 2. USDC
│  ├─ 3. BTC
│  ├─ 4. ETH
│  └─ 5. BNB
├─ 2. Sell Crypto
│  ├─ 1. USDT (Enter amount)
│  ├─ 2. USDC
│  ├─ 3. BTC
│  ├─ 4. ETH
│  └─ 5. BNB
├─ 3. Check Balance
│  └─ Wallet address + balance
├─ 4. Link Bank Account
│  ├─ BVN entry
│  ├─ Bank name selection
│  └─ Account verification
├─ 5. Transaction History
│  └─ Last 10 transactions
├─ 6. Settings
│  ├─ Change PIN
│  ├─ View wallet address
│  └─ Language selection
└─ 0. Exit
```

### Buy Crypto Flow

```
User selects "Buy Crypto" (Menu 1)
    ↓
Select asset (USDT, USDC, BTC, ETH, BNB)
    ↓
Enter amount in NGN
    ↓
Request quote (expires in 2 minutes)
    ↓
Show fee + total (e.g., ₦10,000 → 0.0048 BTC @ 1.5% spread)
    ↓
User confirms
    ↓
Enter PIN
    ↓
USSD engine creates transaction, ILP connector prepares condition
    ↓
Fiat leg: charge user's bank account via Paystack
    ↓
Crypto leg: exchange order to Quidax/Busha
    ↓
Both succeed → fulfill condition
    ↓
Send crypto to user's wallet
    ↓
USSD: "You bought 0.0048 BTC. Delivery in 2-5 minutes."
    ↓
Webhook updates transaction status
    ↓
Admin dashboard shows completed transaction
```

### Sell Crypto Flow

```
User selects "Sell Crypto" (Menu 2)
    ↓
Select asset
    ↓
Enter amount in crypto (or NGN equivalent)
    ↓
Request quote
    ↓
Show fee + total (e.g., 0.01 BTC → ₦417,000 @ 1.5% spread)
    ↓
User confirms
    ↓
Enter PIN
    ↓
USSD engine creates transaction, ILP connector prepares condition
    ↓
Crypto leg: initiate withdrawal from exchange (cold wallet → hot wallet)
    ↓
Wait for user to send crypto to ogak wallet address (shown in USSD)
    ↓
Fiat leg: credit user's bank account via Paystack/Flutterwave
    ↓
Both succeed → fulfill condition
    ↓
USSD: "You sold 0.01 BTC for ₦417,000. Arriving in 1-2 minutes."
    ↓
Webhook updates transaction status
```

### Bank & BVN Linking (KYC Upgrade)

```
User selects "Link Bank Account" (Menu 4)
    ↓
Enter BVN (11 digits)
    ↓
ILP connector validates BVN via Flutterwave
    ↓
BVN matches a registered bank account
    ↓
User selects bank (or auto-detected)
    ↓
Initiate bank verification (Paystack Account Lookup)
    ↓
Paystack returns account name
    ↓
User confirms name matches
    ↓
Upgrade to Tier 2 (₦500k/tx limit)
    ↓
USSD: "Bank linked. Upgraded to Tier 2. New limit: ₦500,000 per transaction."
```

---

## API Reference

### USSD Callback Endpoint

Africa's Talking sends a POST request to this endpoint each time a user dials.

**POST** `/api/v1/ussd/callback`

```json
{
  "phoneNumber": "+2348012345678",
  "text": "1*1",
  "sessionId": "AFD92837F7DDFB94"
}
```

**Response:**

```json
{
  "continueSession": true,
  "response": "Welcome to Ogak. 1. Buy Crypto 2. Sell Crypto 3. Check Balance"
}
```

The USSD engine maintains session state in Redis, advancing the menu tree based on user input.

### Open Payments Endpoints

#### Get Wallet Address

**GET** `/api/v1/open-payments/wallet-addresses/{phone_number}`

Returns the OpenAPI-compliant wallet address document for a user.

**Response:**

```json
{
  "id": "https://ogak.ng/api/v1/open-payments/wallet-addresses/+2348012345678",
  "publicName": "Ogak Wallet",
  "assetCode": "NGN",
  "assetScale": 2,
  "authServer": "https://ogak.ng/auth",
  "resourceServer": "https://ogak.ng/api/v1/open-payments"
}
```

#### List Incoming Payments

**GET** `/api/v1/open-payments/incoming-payments`

List all incoming payments for the authenticated user.

#### Create Incoming Payment

**POST** `/api/v1/open-payments/incoming-payments`

Create an incoming payment with optional limit and expiry.

**Request:**

```json
{
  "walletAddressId": "...",
  "incomingAmount": {
    "value": "5000",
    "assetCode": "NGN",
    "assetScale": 2
  },
  "expiresAt": "2024-12-31T23:59:59Z"
}
```

### Webhook Endpoints

**POST** `/api/v1/webhooks/paystack`

Verifies HMAC-SHA512 signature and processes charge.success / charge.failed events.

**POST** `/api/v1/webhooks/flutterwave`

Verifies hash signature and processes charge events.

**POST** `/api/v1/webhooks/quidax`

Listens for order status updates (filled, rejected, etc.).

**POST** `/api/v1/webhooks/busha`

Listens for order and settlement status.

### Admin Dashboard API

#### Get Transaction Summary

**GET** `/api/v1/admin/transactions/summary`

```json
{
  "totalVolume": "1500000",
  "totalTransactions": 234,
  "successRate": 0.976,
  "avgSettlementTime": 142.3
}
```

#### List Transactions (Paginated)

**GET** `/api/v1/admin/transactions?page=1&limit=50&status=completed&dateFrom=2024-01-01`

#### WebSocket Feed

**WS** `/ws/admin/transactions`

Real-time transaction stream.

---

## Database Schema

Models are in `packages/db/models/`. Tables: users, sessions, transactions, kyc_tiers, wallets, quotes, audit_logs, ilp_conditions, etc. Migrations are in `packages/db/migrations/`.

---

## KYC / AML Compliance

### Tier System

| Tier | Limit/Tx | Identity Required | Bank Verification |
|---|---|---|---|
| **Tier 0** | ₦50,000 | Phone number only | No |
| **Tier 1** | ₦50,000 | Email verified | No |
| **Tier 2** | ₦500,000 | BVN + bank linked | Yes (Paystack) |
| **Tier 3** | ₦5,000,000 | Full KYC on file | Yes |

Users start at Tier 0. Tier 1 happens automatically. Tier 2+ needs BVN validation and a bank link.

### How It Works

Every transaction creates an audit log entry with timestamp and actor. BVN data is encrypted at rest (AES-256-GCM). Phone numbers get masked in logs (e.g., +234801****678). Webhook payloads include a reference to the audit trail. Celery tasks log every settlement step so you can reconstruct what happened.

---

## Integrations

### Banking Providers

| Provider | Use | Credentials |
|---|---|---|
| **Paystack** | Charge user accounts, pay out | `PAYSTACK_SECRET_KEY` |
| **Flutterwave** | Alternative charge, BVN validation | `FLW_SECRET_KEY` |
| **NIP/NIBSS** | Direct bank transfers (via Paystack) | Via Paystack |

### Crypto Exchanges / VASPs

| VASP | Use | Type | Credentials |
|---|---|---|---|
| **Quidax** | Primary crypto exchange (USDT/USDC/BTC/ETH) | SEC-licensed | `QUIDAX_SECRET_KEY` |
| **Busha** | Secondary exchange, fallback | SEC-licensed | `BUSHA_API_KEY` |
| **Binance** | Global spot trading, stablecoin conversion | Global | `BINANCE_API_KEY` |

### Africa's Talking

Receives user input, sends menu responses. SMS fallback is optional. Credentials: `AT_USERNAME`, `AT_API_KEY`, `AT_USSD_SHORTCODE`.

---

## Configuration Reference

All variables are in `.env.example`. Key sections:

**Database & Cache**
- `DATABASE_URL` — async PostgreSQL connection string
- `REDIS_URL` — Redis connection string

**Providers**
- `PAYSTACK_SECRET_KEY`, `PAYSTACK_WEBHOOK_SECRET`
- `FLW_SECRET_KEY`, `FLW_WEBHOOK_SECRET`
- `QUIDAX_SECRET_KEY`, `BUSHA_API_KEY`, `BINANCE_API_KEY`
- `AT_USERNAME`, `AT_API_KEY`, `AT_USSD_SHORTCODE`

**ILP**
- `ILP_CONNECTOR_ADDRESS` — address prefix (e.g., `g.ogak.ng.connector`)
- `ILP_CONNECTOR_SECRET` — 32+ character secret

**Security**
- `KYC_TIER1_TX_LIMIT_NGN`, `KYC_TIER2_TX_LIMIT_NGN`, `KYC_TIER3_TX_LIMIT_NGN`
- `USSD_SESSION_TTL_SECONDS` — session timeout (default 180)
- `USSD_MAX_PIN_ATTEMPTS` — attempts before lockout (default 3)
- `USSD_PIN_LOCKOUT_SECONDS` — lockout duration (default 1800)

**Rates**
- `RATE_CACHE_TTL_SECONDS` — how long to cache rates (default 30)
- `RATE_QUOTE_EXPIRY_SECONDS` — quote validity window (default 120)
- `RATE_SPREAD_BPS` — platform margin (default 150 = 1.5%)

---

## Docker Deployment

### Development

```bash
docker-compose up -d
```

Starts all services with hot-reload and mounted source volumes.

### Production

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

The `Dockerfile` uses a non-root `ogak` user, runs Uvicorn with 4 workers, and exposes ports 8000–8003.

### Infrastructure

- **PostgreSQL 16 Alpine** — `postgres_data` volume, `pg_isready` health check
- **Redis 7 Alpine** — AOF persistence, 256MB max with LRU eviction, `redis-cli ping` health check
- All services on `ogak-network` bridge

---

## Development

### Code Quality

```bash
ruff check packages/
ruff format packages/
mypy packages/
```

Enforced: Python 3.11 target, 100-char line length, strict mypy, pre-commit hooks.

### Testing

```bash
pytest
pytest --cov=packages --cov-report=html
pytest tests/test_quote_service.py -v
```

Config in `pyproject.toml`: `asyncio_mode = "auto"`, verbose output.

### Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
alembic history
```

---

## Examples

### Open Payments Receive Demo

`examples/open_payments_receive_demo.py` shows the receive-side flow:

```bash
python examples/open_payments_receive_demo.py \
    --receiver http://localhost:8001/api/v1/open-payments/wallet-addresses/+2348012345678 \
    --amount 5000
```

Steps:
1. Fetch wallet address document
2. Request non-interactive incoming-payment grant
3. Create incoming payment on resource server

Fulfillment is driven by the real settlement layer.

---

## Security

| Mechanism | Details |
|---|---|
| **PIN Hashing** | PBKDF2-HMAC-SHA256, 100k iterations, 16-byte salt |
| **Data Encryption** | AES-256-GCM for BVN/keys/fulfillments (12-byte nonce) |
| **Webhook Verification** | HMAC-SHA512 (Paystack), hash (Flutterwave) |
| **ILP Condition/Fulfillment** | SHA-256 preimage (32-byte condition, 32-byte fulfillment) |
| **Session Management** | Redis TTL-based (180s for USSD) |
| **Brute-Force Protection** | 3 PIN attempts → 30-minute lockout |
| **Phone Masking** | +234801****678 in logs and displays |
| **BVN Masking** | *******8901 for display, encrypted at rest |
| **Non-Root Container** | Production image runs as `ogak` user |

---

## Roadmap

- Transaction history in USSD (Menu 5)
- Outgoing payments (sender-side Open Payments)
- Interactive GNAP grants with user consent UI
- SMS OTP for high-value transactions
- Multi-exchange rate aggregation
- Webhook event processing for Celery settlement
- Admin dashboard frontend (HTML/JS)
- Full Rafiki integration for production ILP peering
- Rate limiting via SlowAPI
- Full i18n for Yoruba, Hausa, Igbo

---

## License

MIT License. See [pyproject.toml](pyproject.toml).

---

<p align="center">
  Built for financial inclusion in Nigeria<br/>
  <strong>Ogak Team</strong> — Crypto on any phone, no internet required.
</p>
