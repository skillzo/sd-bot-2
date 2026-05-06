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
ALLOWED_TELEGRAM_CHAT_IDS = {
    cid.strip()
    for cid in os.environ.get("ALLOWED_TELEGRAM_CHAT_IDS", "").split(",")
    if cid.strip()
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("webhook")

app = FastAPI(title="TradingView webhook")
app.include_router(futures_router)
app.include_router(spot_router)


async def send_telegram(text: str, chat_id: str | int | None = None) -> None:
    target_chat_id = str(chat_id or TELEGRAM_CHAT_ID).strip()
    if not TELEGRAM_TOKEN or not target_chat_id:
        log.warning("Telegram not configured. Skipping alert.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": target_chat_id, "text": text, "parse_mode": "HTML"}
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            log.error("Telegram error: %s %s", r.status_code, r.text)
        else:
            log.info("Telegram message sent")


def safe_calc_tp(entry, sl, side, rr=4.0):
    try:
        entry = float(entry)
        sl = float(sl)
        side = side.upper()

        if side in ("BUY", "LONG"):
            risk = entry - sl
            if risk <= 0:
                return "N/A"
            return round(entry + rr * risk, 2)

        elif side in ("SELL", "SHORT"):
            risk = sl - entry
            if risk <= 0:
                return "N/A"
            return round(entry - rr * risk, 2)

        return "N/A"
    except:
        return "N/A"


def format_signal(data: dict) -> str:
    print("--------------------------------")
    print("webhook data",data)
    side = str(data.get("side", "")).upper()
    symbol = data.get("symbol", "BTCUSDT")
    price = data.get("price", "N/A")
    sl = data.get("sl", "N/A")
    tp = data.get("tp", "N/A")
    interval = data.get("interval", "N/A")
    order_id = str(data.get("order_id", ""))
    ts = data.get("time", "")
    order_upper = order_id.upper()

    if side == "BE":
        # Break-even alert keeps long/short direction in order_id.
        if order_upper == "LONG":
            emoji = "🟢"
            display_side = "BE LONG"
        elif order_upper == "SHORT":
            emoji = "🔴"
            display_side = "BE SHORT"
        else:
            emoji = "🟡"
            display_side = "BE"
    else:
        emoji = "🟢" if side in ("BUY", "LONG") else "🔴"
        display_side = side

    # Example usage of safe_calc_tp
    calc_tp = safe_calc_tp(price, sl, side)

    return (
        f"{emoji} <b>Signal</b>\n"
        f"Pair: {symbol}\n"
        f"Side: {display_side}\n"
        f"Entry: {price}\n"
        f"SL: {sl}\n"
        f"TP: {calc_tp}\n"
        f"TF: {interval}\n"
        f"Order: {order_id}\n"
        f"Time: {ts}"
    )


def verify_secret(request: Request) -> None:
    if request.query_params.get("secret", "") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


def is_chat_allowed(chat_id: str) -> bool:
    if not ALLOWED_TELEGRAM_CHAT_IDS:
        # If allowlist empty, fallback to single TELEGRAM_CHAT_ID behavior.
        return chat_id == str(TELEGRAM_CHAT_ID).strip()
    return chat_id in ALLOWED_TELEGRAM_CHAT_IDS


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


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, _: None = Depends(verify_secret)):
    try:
        update = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", "")).strip()
    text = str(message.get("text", "")).strip()

    if not chat_id:
        return JSONResponse({"status": "ignored", "reason": "no_chat_id"})

    if not is_chat_allowed(chat_id):
        log.warning("Blocked Telegram chat_id=%s", chat_id)
        return JSONResponse({"status": "ignored", "reason": "chat_not_allowed"})

    if text == "/start":
        await send_telegram("Bot online. Chat allowed.", chat_id=chat_id)
    elif text == "/health":
        await send_telegram("ok", chat_id=chat_id)
    elif text:
        await send_telegram(f"Echo: {text}", chat_id=chat_id)

    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "tradingview-webhook"}
