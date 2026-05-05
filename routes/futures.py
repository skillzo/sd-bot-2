from __future__ import annotations

import hashlib
import hmac
import os
import time

import logging
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/futures", tags=["futures"])
log = logging.getLogger("webhook")

def sign(params: dict, secret_key: str) -> dict:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
    return {**params, "signature": sig}


@router.get("/account")
async def get_account():
    api_key = os.getenv("BINANCE_API_KEY", "")
    secret_key = os.getenv("BINANCE_API_SECRET", "")
    base_url = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com")

    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="Binance API keys not configured")

    params = sign({"timestamp": int(time.time() * 1000)}, secret_key)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{base_url}/fapi/v2/account",
                params=params,
                headers={"X-MBX-APIKEY": api_key},
                timeout=15,
            )
        except Exception as exc:
            log.error("Error getting account: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return r.json()
