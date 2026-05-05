"""
TradingView webhook → Telegram alerts.
Run from repo root: uvicorn webhook.app:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
# Optional override when deployed next to this package only:
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from routes.futures import router as futures_router
from routes.spot import router as spot_router

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("webhook")

app = FastAPI(title="TradingView webhook")
app.include_router(futures_router)
app.include_router(spot_router)


async def send_telegram(text: str) -> None:
    
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured. Skipping alert.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            log.error("Telegram error: %s %s", r.status_code, r.text)
        else:
            log.info("Telegram message sent")


def format_signal(data: dict) -> str:
    print("--------------------------------")
    print("webhook data",data)
    side = str(data.get("side", "")).upper()
    symbol = data.get("symbol", "BTCUSDT")
    price = data.get("price", "N/A")
    sl = data.get("sl", "N/A")
    tp = data.get("tp", "N/A")
    interval = data.get("interval", "N/A")
    order_id = data.get("order_id", "")
    ts = data.get("time", "")
    emoji = "🟢" if side in ("BUY", "LONG") else "🔴"
    return (
        f"{emoji} <b>Signal</b>\n"
        f"Pair: {symbol}\n"
        f"Side: {side}\n"
        f"Entry: {price}\n"
        f"SL: {sl}\n"
        f"TP: {tp}\n"
        f"TF: {interval}\n"
        f"Order: {order_id}\n"
        f"Time: {ts}"
    )


def verify_secret(request: Request) -> None:
    if request.query_params.get("secret", "") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/webhook")
async def webhook(request: Request, _: None = Depends(verify_secret)):
    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    log.info("Webhook payload: %s", data)
    
    await send_telegram(str(data))
    await send_telegram(format_signal(data))
    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "tradingview-webhook"}
