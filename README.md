# Ogak — Production USSD Crypto-Fiat Platform (Nigeria)

**Non-P2P, regulated, atomic Naira ↔ Crypto conversion over USSD.**

Ogak lets any Nigerian with a phone (feature phone or smartphone) buy and sell licensed crypto (USDT, USDC, BTC, ETH, …) using a simple USSD short code (e.g. `*737*OGAK#`).

All flows are **non-P2P**:
- Fiat legs settle through licensed Nigerian banks / payment providers (Paystack, Flutterwave, NIP).
- Crypto legs settle through licensed VASPs/exchanges (Quidax, Busha, Binance, etc.).
- Ogak never holds customer funds long-term.
- Settlement is coordinated with **Interledger Protocol (ILP)** semantics for atomicity (both legs succeed or both are rolled back).

---

## Core Principles (Production)

- **Real Africa's Talking integration only** — no simulators in production paths.
- **Live rates** from exchanges — no hardcoded prices.
- **ILP atomic coordination** — Prepare / Fulfill / Reject using cryptographic conditions.
- **KYC/AML & CBN limits** enforced per tier.
- **Full audit trail** and encrypted sensitive data at rest.
- **Webhook-driven** settlement (bank + exchange callbacks advance the state machine).

---

## Project Structure (Production Monorepo)

```
ogak-ussd/
├── packages/
│   ├── ussd/                 # Africa's Talking webhook + menu state machine
│   ├── api/                  # Open Payments + bank/exchange clients + webhooks
│   ├── ilp_connector/        # ILP Prepare/Fulfill/Reject coordinator
│   ├── services/             # RateService, QuoteService, TransactionOrchestrator, UserService
│   ├── db/                   # SQLAlchemy models + Alembic migrations
│   ├── shared/               # Config, errors, crypto utils (encryption + ILP conditions), types
│   └── admin/                # CLI admin (liquidity, transactions, connectors)
├── migrations/
├── docs/                     # Architecture, ILP flow, deployment, shortcode registration
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
└── README.md                 # This file (production only)
```

---

## Technology Stack

- **Python 3.11 + FastAPI** (async)
- **PostgreSQL 16** (primary store)
- **Redis** (USSD sessions + rate cache)
- **Alembic** (migrations)
- **Africa's Talking** (USSD production gateway)
- **Paystack + Flutterwave** (bank verification, charges, NIP transfers)
- **Quidax + Busha + Binance** (live rates + crypto orders)
- **ILP concepts** (condition = SHA-256(fulfillment), Prepare/Fulfill/Reject phases)
- **Celery** (background settlement & rollbacks)
- **Docker** (production images)

---

## Environment Variables (Required for Production)

Copy `.env.example` → `.env` and fill real values. **Never commit secrets.**

```env
# Application
APP_ENV=production
APP_DEBUG=false
APP_SECRET_KEY=<64-char-hex>
APP_ENCRYPTION_KEY=<32-byte-hex-for-AES-256-GCM>

# Database & Cache
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...

# Africa's Talking (Production)
AT_USERNAME=your-production-username
AT_API_KEY=your-production-api-key
AT_USSD_SHORTCODE=*737*OGAK#
AT_ENVIRONMENT=production

# Banks (at least one required)
PAYSTACK_SECRET_KEY=sk_live_...
PAYSTACK_WEBHOOK_SECRET=...
FLW_SECRET_KEY=FLWSECK_...
FLW_WEBHOOK_SECRET=...

# Licensed Exchanges (at least one primary VASP)
QUIDAX_SECRET_KEY=...
QUIDAX_WEBHOOK_SECRET=...
BINANCE_API_KEY=...
BINANCE_SECRET_KEY=...

# ILP / Atomicity
ILP_CONNECTOR_ADDRESS=g.ng.ogak.primary
ILP_DEFAULT_SPREAD_BPS=150

# KYC / CBN Limits (example)
KYC_TIER1_TX_LIMIT_NGN=50000
KYC_TIER1_DAILY_LIMIT_NGN=500000
# ... higher tiers

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

See `.env.example` for the complete list.

---

## How to Register a Real Nigerian USSD Short Code

1. Incorporate a company (or use an existing licensed entity).
2. Obtain necessary regulatory approvals / VASP license where required (SEC/CBN guidelines for crypto).
3. Choose a telco aggregator or work directly with MTN, Airtel, Glo, 9mobile.
4. Apply for a short code (common formats: `*737*XXXX#`, `*384*XXXX#`, etc.).
5. In the telco / aggregator portal, point the short code to your publicly reachable HTTPS endpoint:
   `https://your-domain/api/v1/ussd/callback`
6. In Africa's Talking dashboard:
   - Create a USSD service
   - Set the callback URL to the same endpoint
   - Use **Production** environment + live credentials
7. Test end-to-end with a live Nigerian SIM on the target network.

**Important**: Short code approval + production AT credentials are **mandatory** for live traffic. Sandbox is only for initial integration testing.

---

## Running in Production

### Docker (Recommended)

```bash
cp .env.example .env
# Edit .env with real production credentials

docker-compose up -d --build

# Run migrations
docker-compose exec api alembic upgrade head

# Verify
curl https://your-domain/health
```

### Key Services (ports inside compose)

- USSD service: 8000 (Africa's Talking hits `/api/v1/ussd/callback`)
- Core API + Open Payments + Webhooks: 8001
- ILP Coordinator: 8002
- Admin: 8003
- Celery worker: background

Expose only the ports you need behind a reverse proxy (nginx / traefik) with TLS.

---

## ILP Atomic Settlement Flow (Buy Crypto Example)

```
User dials *737*OGAK#
  → Select 1 (Buy)
  → Enter amount + asset
  → System creates Quote (live rate from Quidax/Binance - spread + fee)
  → ILP condition generated (SHA-256 secret stored encrypted)
  → User confirms with PIN
  → Transaction created (status=CONFIRMED)

ILP PREPARE
  ├─→ Bank leg: Create charge / virtual account / NIP reference (Paystack/Flutterwave)
  └─→ Crypto leg: Create buy order on licensed exchange (Quidax etc.)

User / system pays Naira (webhook confirms credit)
  ↓
Exchange confirms crypto credited to user sub-account / wallet
  ↓
Both legs successful → ILP FULFILL (reveal preimage)
  → Both sides final
  → User sees success on USSD / SMS

Any failure before fulfill → ILP REJECT
  → Best-effort rollback on both sides
  → Transaction marked FAILED or ROLLED_BACK
  → Audit log written
```

The same pattern (reversed) applies for Sell.

---

## Open Payments Compliance

Ogak implements a practical **receiver-side** subset of the [Open Payments](https://openpayments.dev) standard. This lets any Open Payments client (wallets, the official Interledger workshop scripts, Rafiki-based systems, or other connectors) send value to Ogak users using standardized flows.

### Key Endpoints (under `/api/v1/open-payments`)

| Purpose                        | Method + Path                                      | Notes |
|--------------------------------|----------------------------------------------------|-------|
| Wallet Address (core)          | `GET /wallet-addresses/{phone-or-id}`             | Returns the full OP wallet address document. What real clients call first. |
| Grant Request (auth server)    | `POST /auth/grants`                               | Non-interactive grants for `incoming-payment:create` (workshop-compatible). |
| Create Incoming Payment        | `POST /resource/incoming-payments` (Bearer)       | Persisted receivable. Requires valid grant access token. |
| Incoming Payment status        | `GET /resource/incoming-payments/{id}`            | Real state (receivedAmount updated only by settlement). |
| Internal Fulfill (settlement)  | `POST /internal/incoming-payments/{id}/fulfill`   | **Internal only**. Called by ILP/settlement code when real value arrives. |
| Account discovery (compat)     | `POST /accounts/discovery`                        | Convenience. Use wallet address for standard clients. |
| Quotes                         | `POST /quotes`                                    | Calls real rate service. Full external OP quote flow needs more work. |
| Health + stats                 | `GET /health`                                     | Includes count of persisted incoming payments. |

### How to receive a payment from an external Open Payments client (e.g. the workshop)

1. Start Ogak (`docker-compose up` or `uvicorn ...`).
2. Decide on a target user (phone number or user id that exists or will be created on first interaction).
3. Construct the wallet address URL:

   ```
   http://localhost:8001/api/v1/open-payments/wallet-addresses/+2348012345678
   ```

   (In production: `https://api.ogak.ng/api/v1/open-payments/wallet-addresses/+23480...`)

4. Run a client such as the [official workshop](https://github.com/interledger/open-payments-workshop) (Node) or equivalent Python script, setting:

   ```js
   const RECEIVING_WALLET_ADDRESS_URL = "http://localhost:8001/api/v1/open-payments/wallet-addresses/+2348012345678";
   ```

5. The client will:
   - Fetch the wallet address → discovers `authServer` + `resourceServer`
   - Request a non-interactive grant for `incoming-payment`
   - Create the incoming payment on the resource server (using the access token)
   - Later create an outgoing payment from the sender's side that fulfills it

6. Fulfillment (updating `receivedAmount` and marking `completed`) is performed exclusively by your real settlement layer (ILP connector + `TransactionOrchestrator`). There are no simulation or mock endpoints. When value actually arrives over the wire, the orchestrator/connector updates the Open Payments incoming payment record and drives the corresponding credit flow for the target user.

### Payment Pointers / Identifiers

Ogak supports phone-based and id-based identifiers:

- `https://api.ogak.ng/api/v1/open-payments/wallet-addresses/+2348012345678`
- `$ogak.ng/+2348012345678` (if you add a short pointer resolver in front of the full URL)

The system will attempt to resolve the identifier to a real user for nicer `publicName` and future auto-crediting.

### Production Hardening Notes

- Set `OP_PUBLIC_BASE_URL=https://api.ogak.ng` (or via your settings) so all returned URLs are correct behind a reverse proxy.
- Replace the in-memory `_ACTIVE_GRANTS` / `_INCOMING_PAYMENTS` with proper persisted tables (add Alembic migration).
- Add real token management / expiration / revocation.
- When an incoming payment is fulfilled, integrate with `TransactionOrchestrator` + `QuoteService` to credit the user's NGN balance or trigger the appropriate on-ramp leg.
- For **sender side** (Ogak users paying other Open Payments wallets), implement outgoing grants (interactive) + `outgoingPayment.create` using a Python Open Payments client or raw HTTP + JWK signing. The workshop is the reference for the flow.

### References

- Workshop (sender flow reference): https://github.com/interledger/open-payments-workshop
- Official docs: https://openpayments.dev
- Python SDK (work in progress): https://github.com/interledger/open-payments-python-sdk

### Production Setup for Open Payments

1. Run the migration:
   ```bash
   alembic upgrade head
   # or inside docker: docker-compose exec api alembic upgrade head
   ```

2. The new table `open_payments_incoming_payments` is used (see `packages/db/models.py`).

3. Real fulfillment must be wired from your settlement layer:
   - Import `get_open_payments_service()` from `packages.services.open_payments_service`
   - Call `fulfill_incoming_payment(...)` (or hit the internal endpoint from a trusted worker) when value actually arrives.
   - This updates the record and gives you the hook to credit the user via your existing `TransactionOrchestrator`.

4. Protect `/internal/...` routes (network policy, separate port, mTLS, etc.).

This gives you a real, DB-backed, no-mock Open Payments receiver that external clients (workshop scripts, other wallets, connectors) can pay into, with all settlement going through your production atomic paths.

The implementation lets Ogak participate in the broader Interledger / Open Payments ecosystem while keeping the existing USSD + atomic ILP settlement engine as the source of truth for Nigerian fiat/crypto legs.

---

## Security & Compliance Notes

- All sensitive fields (BVN, exchange API keys, ILP fulfillment preimages) are encrypted at rest with AES-256-GCM.
- PINs are hashed with PBKDF2 (100k iterations).
- Webhook signatures are verified (when secrets are configured).
- KYC tier limits are enforced before quote creation.
- Full immutable audit log is written for every material action.
- Rate limiting and input validation are applied at the USSD and API layers.
- Follow current CBN/SEC guidance for VASPs — Ogak is designed as an intermediary, not a direct P2P platform.

---

## Admin & Operations

```bash
# CLI admin (inside container or via installed script)
ogak-admin status
ogak-admin liquidity
ogak-admin recent-transactions --limit 20
```

A future web dashboard can be added under the admin service.

---

## Deployment Options

- **Railway / Render / Fly.io** — easiest for MVP (managed Postgres + Redis)
- **AWS (ECS + RDS + ElastiCache)** — recommended for scale + Nigerian data residency considerations
- **Self-hosted** in a Nigerian data center (for lowest latency + regulatory alignment)
- Use a proper reverse proxy + automatic TLS (Let's Encrypt or provider-managed).

Always run database migrations on deploy and keep Redis persistent (AOF + snapshots).

---

## Monitoring & Observability (Production Must-Haves)

- Structured JSON logs (already configured via structlog/rich in dev)
- Health checks on all services (`/health`)
- Celery task monitoring (flower or your own)
- Transaction success/failure rate alerts
- ILP prepare/fulfill/reject rate + latency
- Bank and exchange API error rate + latency
- Daily volume vs KYC tier limits

---

## Next / Roadmap (Production Hardening)

- Full virtual account + NIP reference generation for fiat legs (instead of direct charges)
- Standing order / mandate support for recurring buys
- Multiple exchange routing + best-price engine
- Voice USSD (via Africa's Talking or telco)
- Mobile money wallet integration (Opay, PalmPay, etc.) as additional fiat rails
- Real-time liquidity dashboard (Interledger-style)

---

## Support & Licensing

- Security issues: security@ogak.ng (or your internal process)
- MIT License (see LICENSE file)

**Ogak exists to bring regulated, accessible crypto on/off-ramps to every Nigerian with a phone.**

Built for production. No demos.

---

## Quick Local Verification (with real keys)

1. `docker-compose up -d`
2. `docker-compose exec api alembic upgrade head`
3. Use curl to post a realistic Africa's Talking production callback payload shape to the USSD endpoint for verification, or use a properly configured production Africa's Talking application.
4. Use production keys only when you have a real short code approved.

Do **not** run the old simulator code in production environments.
#   O g a k - U S S D  
 