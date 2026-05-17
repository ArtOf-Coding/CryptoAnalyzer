"""
Crypto Trading Analyst - Main Cron Job
Runs every 30 minutes: fetches prices, makes AI predictions, tracks P&L
"""

import os
import json
import time
import logging
import requests
import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from gdrive_upload import upload_to_drive
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ─────────────── CONFIG ──────────────────────────────────────────────────────
COINSWITCH_API_KEY    = os.environ.get("COINSWITCH_API_KEY", "")
COINSWITCH_SECRET_KEY = os.environ.get("COINSWITCH_SECRET_KEY", "")
HF_API_TOKEN          = os.environ.get("HF_API_TOKEN", "")        # HuggingFace token
GDRIVE_ENABLED        = bool(os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON", ""))  # auto-enabled when secret is set

# Coins to track (CoinSwitch symbol format)
COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX"]

EXCEL_FILE  = Path("trade_tracker.xlsx")
LOG_FILE    = Path("logs/trader.log")
STATE_FILE  = Path("last_predictions.json")

# CoinSwitch base URL
CS_BASE = "https://coinswitch.co/trade/api/v2"

# HuggingFace Inference API – CryptoGemma-4B
# Using: google/gemma-3-1b-it (free) or NousResearch/CryptoGemma-4B if published
# Falls back to gemma-2-2b-it which is freely available
HF_MODEL   = "google/gemma-2-2b-it"   # Change to CryptoGemma-4B when available on HF Hub
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# ─────────────── LOGGING ─────────────────────────────────────────────────────
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  1.  COINSWITCH API
# ═══════════════════════════════════════════════════════════════════════════════

def _cs_headers(method: str, endpoint: str, payload: dict) -> dict:
    """Generate CoinSwitch HMAC-signed headers."""
    ts = str(int(time.time() * 1000))
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True) if payload else ""
    sign_str = f"{method}{endpoint}{ts}{payload_str}"
    signature = hmac.new(
        COINSWITCH_SECRET_KEY.encode(), sign_str.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-AUTH-APIKEY": COINSWITCH_API_KEY,
        "X-AUTH-SIGNATURE": signature,
        "X-AUTH-TIMESTAMP": ts,
    }


def fetch_prices() -> dict[str, float]:
    """
    Fetch current INR prices for all tracked coins via CoinSwitch.
    Falls back to CoinGecko (no key needed) if CoinSwitch creds absent.
    """
    if COINSWITCH_API_KEY and COINSWITCH_SECRET_KEY:
        return _fetch_prices_coinswitch()
    log.warning("No CoinSwitch credentials – using CoinGecko fallback")
    return _fetch_prices_coingecko()


def _fetch_prices_coinswitch() -> dict[str, float]:
    prices = {}
    endpoint = "/coins/INR"
    try:
        headers = _cs_headers("GET", endpoint, {})
        resp = requests.get(CS_BASE + endpoint, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        sym_map = {item["symbol"].upper(): float(item["price"]) for item in data}
        for coin in COINS:
            prices[coin] = sym_map.get(coin, 0.0)
        log.info(f"CoinSwitch prices fetched: {prices}")
    except Exception as e:
        log.error(f"CoinSwitch fetch failed: {e}")
        prices = _fetch_prices_coingecko()
    return prices


_GECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
    "SOL": "solana",  "XRP": "ripple",   "DOGE": "dogecoin",
    "ADA": "cardano", "AVAX": "avalanche-2",
}

def _fetch_prices_coingecko() -> dict[str, float]:
    ids = ",".join(_GECKO_IDS[c] for c in COINS)
    # Try demo API first (free, higher rate limits)
    for base in [
        "https://api.coingecko.com/api/v3",
        "https://pro-api.coingecko.com/api/v3",
    ]:
        try:
            url = f"{base}/simple/price?ids={ids}&vs_currencies=inr"
            headers = {}
            if base.startswith("https://pro") and os.environ.get("COINGECKO_API_KEY"):
                headers["x-cg-pro-api-key"] = os.environ["COINGECKO_API_KEY"]
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            prices = {}
            for coin, gecko_id in _GECKO_IDS.items():
                prices[coin] = data.get(gecko_id, {}).get("inr", 0.0)
            log.info(f"CoinGecko prices: {prices}")
            return prices
        except Exception as e:
            log.warning(f"CoinGecko {base} failed: {e}")
    # Final fallback: use Binance public API (no key needed)
    return _fetch_prices_binance_inr()


_BINANCE_PAIRS = {
    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "BNB": "BNBUSDT",
    "SOL": "SOLUSDT", "XRP": "XRPUSDT", "DOGE": "DOGEUSDT",
    "ADA": "ADAUSDT", "AVAX": "AVAXUSDT",
}
_USD_TO_INR_FALLBACK = 83.5


def _fetch_prices_binance_inr() -> dict[str, float]:
    prices = {c: 0.0 for c in COINS}
    try:
        usd_inr = _USD_TO_INR_FALLBACK
        try:
            fx = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=8)
            usd_inr = fx.json().get("rates", {}).get("INR", _USD_TO_INR_FALLBACK)
        except Exception:
            pass
        resp = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=15)
        resp.raise_for_status()
        data = {item["symbol"]: float(item["price"]) for item in resp.json()}
        for coin, sym in _BINANCE_PAIRS.items():
            prices[coin] = round(data.get(sym, 0.0) * usd_inr, 2)
        log.info(f"Binance->INR prices (rate={usd_inr}): {prices}")
    except Exception as e:
        log.error(f"All price APIs failed: {e}")
    return prices


def fetch_24h_stats() -> dict[str, dict]:
    """Fetch 24-h change% and volume for richer AI context."""
    stats = {c: {"change_24h": 0.0, "volume_24h": 0.0} for c in COINS}
    try:
        ids = ",".join(_GECKO_IDS[c] for c in COINS)
        url = (
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={ids}&vs_currencies=inr"
            f"&include_24hr_change=true&include_24hr_vol=true"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for coin, gid in _GECKO_IDS.items():
            entry = data.get(gid, {})
            stats[coin] = {
                "change_24h": round(entry.get("inr_24h_change", 0.0), 2),
                "volume_24h": round(entry.get("inr_24h_vol", 0.0), 2),
            }
    except Exception as e:
        log.warning(f"24h stats fetch failed: {e}")
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
#  2.  AI DECISION VIA CRYPTOGEMMA / HF INFERENCE API
# ═══════════════════════════════════════════════════════════════════════════════

def build_prompt(prices: dict, stats: dict, prev_preds: dict) -> str:
    lines = ["You are a crypto trading analyst. Analyze the following data and give a BUY, SELL, or HOLD recommendation for each coin. Reply ONLY with a JSON object like: {\"BTC\": \"BUY\", \"ETH\": \"HOLD\", ...}\n"]
    lines.append("Current market data (prices in INR):")
    for coin in COINS:
        prev = prev_preds.get(coin, {})
        prev_action = prev.get("action", "N/A")
        prev_price  = prev.get("price", 0)
        change = stats[coin]["change_24h"]
        vol    = stats[coin]["volume_24h"]
        lines.append(
            f"  {coin}: ₹{prices[coin]:,.2f}  |  24h chg: {change:+.2f}%  "
            f"|  24h vol: ₹{vol:,.0f}  |  last_pred: {prev_action} @ ₹{prev_price:,.2f}"
        )
    lines.append("\nRespond with only the JSON object. No explanation.")
    return "\n".join(lines)


def get_ai_decisions(prices: dict, stats: dict, prev_preds: dict) -> dict[str, str]:
    prompt = build_prompt(prices, stats, prev_preds)
    decisions = {c: "HOLD" for c in COINS}  # safe default

    if not HF_API_TOKEN:
        log.warning("No HF_API_TOKEN – using rule-based fallback")
        return _rule_based_decisions(stats)

    headers = {"Authorization": f"Bearer {HF_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.3,
            "do_sample": True,
            "return_full_text": False,
        },
    }
    try:
        resp = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 503:
            log.warning("HF model loading – retrying in 20s")
            time.sleep(20)
            resp = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        raw = resp.json()
        text = raw[0]["generated_text"] if isinstance(raw, list) else raw.get("generated_text", "")
        # Extract JSON block
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(text[start:end])
            for coin in COINS:
                action = str(parsed.get(coin, "HOLD")).upper()
                decisions[coin] = action if action in ("BUY", "SELL", "HOLD") else "HOLD"
        log.info(f"AI decisions: {decisions}")
    except Exception as e:
        log.error(f"HF API error: {e} – using rule-based fallback")
        decisions = _rule_based_decisions(stats)

    return decisions


def _rule_based_decisions(stats: dict) -> dict[str, str]:
    """Simple momentum rule: buy on strong up, sell on strong down, else hold."""
    decisions = {}
    for coin in COINS:
        ch = stats[coin]["change_24h"]
        if ch > 3.0:
            decisions[coin] = "BUY"
        elif ch < -3.0:
            decisions[coin] = "SELL"
        else:
            decisions[coin] = "HOLD"
    return decisions


# ═══════════════════════════════════════════════════════════════════════════════
#  3.  STATE PERSISTENCE  (previous predictions)
# ═══════════════════════════════════════════════════════════════════════════════

def load_prev_predictions() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_predictions(predictions: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(predictions, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
#  4.  EXCEL TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

HEADERS = [
    "Timestamp", "Coin", "Price_INR", "24h_Change_%", "24h_Volume_INR",
    "AI_Action", "Confidence",
    "Prev_Action", "Prev_Price_INR", "Price_Change_%",
    "Outcome",    "PnL_%",
    "Cumulative_Correct", "Accuracy_%",
]

_HEADER_COLOR  = "1F3864"  # dark navy
_BUY_COLOR     = "C6EFCE"  # green tint
_SELL_COLOR    = "FFCCCC"  # red tint
_HOLD_COLOR    = "FFEB9C"  # yellow tint
_WIN_COLOR     = "00B050"
_LOSS_COLOR    = "FF0000"
_HEADER_FONT   = Font(bold=True, color="FFFFFF", name="Arial", size=10)
_CELL_FONT     = Font(name="Arial", size=10)
_CENTER        = Alignment(horizontal="center", vertical="center", wrap_text=True)
_THIN          = Side(style="thin", color="BFBFBF")
_BORDER        = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

COL_WIDTHS = [20, 7, 16, 14, 20, 12, 12, 12, 16, 14, 12, 10, 18, 12]


def _ensure_workbook() -> openpyxl.Workbook:
    if EXCEL_FILE.exists():
        return openpyxl.load_workbook(EXCEL_FILE)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Trade Log"

    # Header row
    for col, (hdr, width) in enumerate(zip(HEADERS, COL_WIDTHS), 1):
        cell = ws.cell(row=1, column=col, value=hdr)
        cell.font = _HEADER_FONT
        cell.fill = PatternFill("solid", fgColor=_HEADER_COLOR)
        cell.alignment = _CENTER
        cell.border = _BORDER
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    # Summary sheet
    ws2 = wb.create_sheet("Summary")
    ws2["A1"] = "Crypto AI Trader – Performance Dashboard"
    ws2["A1"].font = Font(bold=True, size=14, color=_HEADER_COLOR, name="Arial")
    _add_summary_formulas(ws2)

    wb.save(EXCEL_FILE)
    return wb


def _add_summary_formulas(ws):
    labels = [
        ("B3", "Total Trades"),   ("C3", "=COUNTA('Trade Log'!A2:A10000)"),
        ("B4", "BUY signals"),    ("C4", "=COUNTIF('Trade Log'!F2:F10000,\"BUY\")"),
        ("B5", "SELL signals"),   ("C5", "=COUNTIF('Trade Log'!F2:F10000,\"SELL\")"),
        ("B6", "HOLD signals"),   ("C6", "=COUNTIF('Trade Log'!F2:F10000,\"HOLD\")"),
        ("B7", "Wins"),           ("C7", "=COUNTIF('Trade Log'!K2:K10000,\"WIN\")"),
        ("B8", "Losses"),         ("C8", "=COUNTIF('Trade Log'!K2:K10000,\"LOSS\")"),
        ("B9", "Overall Accuracy"), ("C9", '=IF(C3=0,0,C7/C3)'),
        ("B10","Avg PnL %"),      ("C10","=IF(C3=0,0,AVERAGE('Trade Log'!L2:L10000))"),
    ]
    for cell_addr, val in labels:
        ws[cell_addr] = val
        ws[cell_addr].font = Font(name="Arial", size=10, bold=("B" in cell_addr))
    ws["C9"].number_format = "0.00%"
    ws["C10"].number_format = "0.00%"


def _outcome_and_pnl(action: str, prev_price: float, curr_price: float):
    """Determine WIN/LOSS/NEUTRAL and P&L %."""
    if prev_price <= 0 or action not in ("BUY", "SELL"):
        return "NEUTRAL", 0.0
    pnl = ((curr_price - prev_price) / prev_price) * 100
    if action == "BUY":
        outcome = "WIN" if pnl > 0 else "LOSS"
    else:  # SELL
        outcome = "WIN" if pnl < 0 else "LOSS"
        pnl = -pnl  # from seller perspective
    return outcome, round(pnl, 4)


def append_to_excel(
    ts: str,
    coin: str,
    price: float,
    stats_row: dict,
    action: str,
    prev: dict,
    cum_correct: int,
    total_rows: int,
):
    wb = _ensure_workbook()
    ws = wb["Trade Log"]
    next_row = ws.max_row + 1

    prev_action = prev.get("action", "")
    prev_price  = prev.get("price", 0.0)
    price_chg   = round(((price - prev_price) / prev_price) * 100, 4) if prev_price > 0 else 0.0
    outcome, pnl = _outcome_and_pnl(prev_action, prev_price, price)

    if outcome == "WIN":
        cum_correct += 1

    accuracy = round((cum_correct / total_rows) * 100, 2) if total_rows > 0 else 0.0

    row_data = [
        ts, coin, price,
        stats_row["change_24h"], stats_row["volume_24h"],
        action, "AI",
        prev_action, prev_price, price_chg,
        outcome, pnl,
        cum_correct, accuracy,
    ]

    for col, val in enumerate(row_data, 1):
        cell = ws.cell(row=next_row, column=col, value=val)
        cell.font = _CELL_FONT
        cell.alignment = _CENTER
        cell.border = _BORDER

        # Row tinting based on action
        if col == 6:  # AI_Action
            clr = {"BUY": _BUY_COLOR, "SELL": _SELL_COLOR, "HOLD": _HOLD_COLOR}.get(action, "FFFFFF")
            cell.fill = PatternFill("solid", fgColor=clr)
        if col == 11:  # Outcome
            if val == "WIN":
                cell.font = Font(name="Arial", size=10, bold=True, color=_WIN_COLOR)
            elif val == "LOSS":
                cell.font = Font(name="Arial", size=10, bold=True, color=_LOSS_COLOR)

    wb.save(EXCEL_FILE)
    log.info(f"  Logged {coin}: {action} | prev={prev_action} | outcome={outcome} | pnl={pnl:.2f}%")
    return cum_correct


# ═══════════════════════════════════════════════════════════════════════════════
#  5.  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run():
    log.info("=" * 60)
    log.info("Crypto Trader Cron – starting run")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Step 1: Fetch market data
    prices = fetch_prices()
    stats  = fetch_24h_stats()

    # Step 2: Load previous predictions
    prev_preds = load_prev_predictions()

    # Step 3: Get AI decisions
    decisions = get_ai_decisions(prices, stats, prev_preds)

    # Step 4: Write to Excel & compute outcomes
    wb = _ensure_workbook()
    ws = wb["Trade Log"]
    total_so_far = ws.max_row - 1  # excluding header
    wb.close()

    # Re-load to count cumulative wins
    if EXCEL_FILE.exists():
        df = pd.read_excel(EXCEL_FILE, sheet_name="Trade Log")
        cum_correct = int(df["Cumulative_Correct"].iloc[-1]) if len(df) > 0 else 0
    else:
        cum_correct = 0

    for i, coin in enumerate(COINS):
        price  = prices.get(coin, 0.0)
        action = decisions.get(coin, "HOLD")
        prev   = prev_preds.get(coin, {})
        total_so_far += 1
        cum_correct = append_to_excel(
            ts, coin, price, stats[coin], action, prev, cum_correct, total_so_far
        )

    # Step 5: Save current round as "previous predictions"
    new_preds = {
        coin: {"action": decisions[coin], "price": prices[coin], "ts": ts}
        for coin in COINS
    }
    save_predictions(new_preds)

    # Step 6: Upload to Google Drive (if credentials present)
    if GDRIVE_ENABLED:
        log.info("Uploading to Google Drive...")
        url = upload_to_drive(EXCEL_FILE)
        if url:
            log.info(f"✅  Google Drive: {url}")
        else:
            log.warning("Google Drive upload failed – file kept locally.")
    else:
        log.info("GDRIVE_SERVICE_ACCOUNT_JSON not set – skipping Drive upload.")

    log.info("Run complete. Excel updated.")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
