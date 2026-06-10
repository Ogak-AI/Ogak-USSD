"""
Open Payments Receive Client Example (Python)

This script mirrors the core receive-side flow from the official workshop
https://github.com/interledger/open-payments-workshop
but is implemented in Python + httpx for use inside the Ogak project.

It performs only real Open Payments protocol steps against a receiver
(no mock data, no simulated settlement, no fabricated responses):

  - Your local Ogak instance (the receiver endpoints)
  - https://wallet.interledger-test.dev/ test wallets (for cross-testing)
  - Any other Rafiki / Open Payments compatible wallet

Usage (against local Ogak):

  1. Start Ogak so the API is on http://localhost:8001
  2. Pick (or create) a target identifier, e.g. a phone that will receive the funds.
  3. Run:

     python examples/open_payments_receive_demo.py \
         --receiver http://localhost:8001/api/v1/open-payments/wallet-addresses/+2348012345678 \
         --amount 5000

  The script performs only real protocol steps:
    - GET the wallet address document
    - Request a non-interactive incoming-payment grant on the authServer
    - Create an Incoming Payment on the resourceServer (with proper Bearer token)

Fulfillment (updating receivedAmount + completed with *actual* value) must be
driven exclusively by your production ILP connector / settlement engine.
Use the internal (non-public) hook:

  POST /api/v1/open-payments/internal/incoming-payments/{id}/fulfill

or call packages.services.open_payments_service.get_open_payments_service().fulfill_incoming_payment(...)
directly from your settlement code.

No simulation is provided or allowed.

For a full sender-to-receiver movement you also need a sending wallet + the
outgoing payment interactive grant flow. See the official JS workshop for
the complete reference implementation.

Requirements: httpx (already in the project requirements.txt)
"""

import argparse
import asyncio
import sys
from typing import Any

import httpx


async def get_wallet_address(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    print(f"\n[1] Fetching wallet address: {url}")
    resp = await client.get(url)
    resp.raise_for_status()
    wa = resp.json()
    print("    ->", wa)
    return wa


async def request_incoming_grant(
    client: httpx.AsyncClient, auth_server: str
) -> dict[str, Any]:
    print(f"\n[2] Requesting non-interactive incoming-payment grant at {auth_server}/grants")
    grant_req = {
        "access_token": {
            "access": [
                {
                    "type": "incoming-payment",
                    "actions": ["create", "read"],
                }
            ]
        }
    }
    resp = await client.post(f"{auth_server}/grants", json=grant_req)
    if resp.status_code >= 400:
        print("    Grant request failed:", resp.status_code, resp.text)
        resp.raise_for_status()
    grant = resp.json()
    print("    -> Grant response:", grant)
    access_token = grant.get("access_token", {}).get("value")
    if not access_token:
        raise RuntimeError("No access_token in grant response (interactive grant?)")
    return grant


async def create_incoming_payment(
    client: httpx.AsyncClient,
    resource_server: str,
    access_token: str,
    wallet_address_id: str,
    amount: int,
    asset_code: str = "NGN",
    asset_scale: int = 2,
) -> dict[str, Any]:
    print(f"\n[3] Creating incoming payment on {resource_server}/incoming-payments")
    headers = {"Authorization": f"Bearer {access_token}"}
    body = {
        "walletAddress": wallet_address_id,
        "incomingAmount": {
            "value": str(amount),
            "assetCode": asset_code,
            "assetScale": asset_scale,
        },
        "metadata": {
            "description": "Demo payment via Ogak Open Payments receiver",
            "source": "open-payments-receive-demo",
        },
    }
    resp = await client.post(
        f"{resource_server}/incoming-payments", json=body, headers=headers
    )
    if resp.status_code >= 400:
        print("    Create failed:", resp.status_code, resp.text)
        resp.raise_for_status()
    ip = resp.json()
    print("    -> Incoming Payment created:", ip)
    return ip


async def main():
    parser = argparse.ArgumentParser(description="Open Payments receive-side demo (Python)")
    parser.add_argument(
        "--receiver",
        default="http://localhost:8001/api/v1/open-payments/wallet-addresses/+2348012345678",
        help="Full URL to the target Open Payments wallet address (receiver)",
    )
    parser.add_argument(
        "--amount",
        type=int,
        default=5000,
        help="Amount in smallest units of the asset (e.g. kobo for NGN)",
    )
    args = parser.parse_args()

    receiver_url = args.receiver
    amount = args.amount

    print("=" * 70)
    print("Open Payments Receive Demo (Python)")
    print(f"Target receiver wallet: {receiver_url}")
    print(f"Amount: {amount}")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
        try:
            # 1. Get wallet address document (public)
            wa = await get_wallet_address(http, receiver_url)
            wallet_id = wa["id"]
            auth_server = wa["authServer"]
            resource_server = wa["resourceServer"]

            print(f"\n    Wallet ID:        {wallet_id}")
            print(f"    Auth Server:      {auth_server}")
            print(f"    Resource Server:  {resource_server}")

            # 2. Request grant (non-interactive for incoming)
            grant = await request_incoming_grant(http, auth_server)
            access_token = grant["access_token"]["value"]

            # 3. Create the actual incoming payment resource
            incoming = await create_incoming_payment(
                http,
                resource_server,
                access_token,
                wallet_id,
                amount,
            )

            print("\n" + "=" * 70)
            print("SUCCESS — Incoming payment created on the receiver.")
            print(f"Incoming Payment ID: {incoming.get('id')}")
            print("\nThis is a real Open Payments incoming payment resource.")
            print("Fulfillment (updating receivedAmount + completed) must be performed")
            print("by your real settlement layer (ILP connector / orchestrator) when")
            print("the actual funds arrive — no simulation or mock data is used.")
            print("\nFor a complete money movement you also need a sending wallet that")
            print("will create an outgoing payment pointing at this incoming payment")
            print("(see the official JS workshop for the full sender flow).")
            print("=" * 70)

        except httpx.HTTPStatusError as e:
            print(f"\nHTTP error: {e.response.status_code} {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\nError: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
