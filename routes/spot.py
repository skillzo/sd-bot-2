from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/spot", tags=["spot"])
log = logging.getLogger("webhook")


def _sign(params: dict, secret_key: str) -> dict:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    signature = hmac.new(secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
    return {**params, "signature": signature}


def _spot_config() -> tuple[str, str, str]:
    api_key = os.getenv("BINANCE_API_KEY", "")
    secret_key = os.getenv("BINANCE_API_SECRET", "")
    base_url = os.getenv("BINANCE_SPOT_BASE_URL", "https://testnet.binance.vision/api")
    return api_key, secret_key, base_url


@router.get("/account")
async def get_account():
    api_key, secret_key, base_url = _spot_config()
    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="Binance API keys not configured")

    params = _sign({"timestamp": int(time.time() * 1000)}, secret_key)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{base_url}/api/v3/account",
                params=params,
                headers={"X-MBX-APIKEY": api_key},
                timeout=15,
            )
        except Exception as exc:
            log.error("Spot account error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.get("/ticker/price")
async def get_ticker_price(symbol: str = Query(..., description="Example: BTCUSDT")):
    _, _, base_url = _spot_config()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{base_url}/api/v3/ticker/price",
                params={"symbol": symbol.upper()},
                timeout=15,
            )
        except Exception as exc:
            log.error("Spot ticker error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.post("/order")
async def place_order(
    symbol: str = Query(..., description="Example: BTCUSDT"),
    side: str = Query(..., description="BUY or SELL"),
    type: str = Query(..., description="MARKET or LIMIT"),
    quantity: float = Query(...),
    price: float | None = Query(default=None, description="Required for LIMIT"),
    time_in_force: str | None = Query(default=None, description="e.g. GTC for LIMIT"),
):
    api_key, secret_key, base_url = _spot_config()
    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="Binance API keys not configured")

    params = {
        "symbol": symbol.upper(),
        "side": side.upper(),
        "type": type.upper(),
        "quantity": quantity,
        "timestamp": int(time.time() * 1000),
    }
    if params["type"] == "LIMIT":
        if price is None or not time_in_force:
            raise HTTPException(status_code=400, detail="LIMIT order needs price and time_in_force")
        params["price"] = price
        params["timeInForce"] = time_in_force

    signed = _sign(params, secret_key)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                f"{base_url}/api/v3/order",
                params=signed,
                headers={"X-MBX-APIKEY": api_key},
                timeout=15,
            )
        except Exception as exc:
            log.error("Spot place order error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.delete("/order")
async def cancel_order(
    symbol: str = Query(..., description="Example: BTCUSDT"),
    order_id: int = Query(..., description="Binance orderId"),
):
    api_key, secret_key, base_url = _spot_config()
    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="Binance API keys not configured")

    params = _sign(
        {"symbol": symbol.upper(), "orderId": order_id, "timestamp": int(time.time() * 1000)},
        secret_key,
    )
    async with httpx.AsyncClient() as client:
        try:
            r = await client.delete(
                f"{base_url}/api/v3/order",
                params=params,
                headers={"X-MBX-APIKEY": api_key},
                timeout=15,
            )
        except Exception as exc:
            log.error("Spot cancel order error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.get("/open-orders")
async def get_open_orders(symbol: str | None = Query(default=None, description="Optional: BTCUSDT")):
    api_key, secret_key, base_url = _spot_config()
    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="Binance API keys not configured")

    params = {"timestamp": int(time.time() * 1000)}
    if symbol:
        params["symbol"] = symbol.upper()
    signed = _sign(params, secret_key)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{base_url}/api/v3/openOrders",
                params=signed,
                headers={"X-MBX-APIKEY": api_key},
                timeout=15,
            )
        except Exception as exc:
            log.error("Spot open orders error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.get("/order")
async def get_order_status(
    symbol: str = Query(..., description="Example: BTCUSDT"),
    order_id: int = Query(..., description="Binance orderId"),
):
    api_key, secret_key, base_url = _spot_config()
    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="Binance API keys not configured")

    params = _sign(
        {"symbol": symbol.upper(), "orderId": order_id, "timestamp": int(time.time() * 1000)},
        secret_key,
    )
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{base_url}/api/v3/order",
                params=params,
                headers={"X-MBX-APIKEY": api_key},
                timeout=15,
            )
        except Exception as exc:
            log.error("Spot order status error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()
