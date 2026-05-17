# 🪙 Crypto AI Trader — Free Cron Job

Runs every **30 minutes**, fetches live crypto prices, asks an AI model (CryptoGemma / Gemma-2) for BUY/SELL/HOLD decisions, and tracks every prediction vs. actual outcome in a formatted Excel sheet.

---

## 📁 File Structure

```
crypto_trader/
├── main.py                          # Core script (fetch → AI → Excel)
├── requirements.txt                 # Python deps
├── .env.example                     # Environment variable template
├── run_local.sh                     # Quick local test
├── last_predictions.json            # Auto-created: previous round state
├── trade_tracker.xlsx               # Auto-created: Excel trade log
├── logs/trader.log                  # Auto-created: run logs
└── .github/
    └── workflows/
        └── trader.yml               # GitHub Actions cron (FREE)
```

---

## 🆓 Free Deployment — GitHub Actions (Recommended)

GitHub Actions gives you **2,000 free minutes/month** on public repos (or unlimited if the repo stays public). A 30-min cron job uses ~1,440 min/month — well within the free quota.

### Step-by-step

1. **Create a GitHub repo** (public is free + unlimited; private is fine too):
   ```
   https://github.com/new
   ```

2. **Push this code:**
   ```bash
   git init
   git add .
   git commit -m "initial"
   git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
   git push -u origin main
   ```

3. **Add secrets** (Settings → Secrets and variables → Actions → New secret):

   | Secret Name            | Value                           | Required? |
   |------------------------|---------------------------------|-----------|
   | `HF_API_TOKEN`         | Your HuggingFace token          | ✅ Yes     |
   | `COINSWITCH_API_KEY`   | CoinSwitch Pro API key          | Optional  |
   | `COINSWITCH_SECRET_KEY`| CoinSwitch secret key           | Optional  |

   > **Without CoinSwitch keys** → prices fall back to free CoinGecko API (no key needed).

4. The workflow file at `.github/workflows/trader.yml` activates automatically.  
   You can also trigger it manually: **Actions tab → Crypto AI Trader → Run workflow**.

5. **Download the Excel file** after each run:  
   Actions tab → select a run → Artifacts → `trade-log-NNN.zip`

---

## 🤗 HuggingFace — Free AI Inference

### Get a free token
1. Sign up at [huggingface.co](https://huggingface.co/join)  
2. Go to [Settings → Access Tokens](https://huggingface.co/settings/tokens)  
3. Create a **Read** token (free)

### Model used
The script uses **`google/gemma-2-2b-it`** by default — freely available on the HF Inference API.

### Switch to CryptoGemma-4B (when available)
If/when `CryptoGemma-4B` is published on HuggingFace Hub, just change one line in `main.py`:

```python
HF_MODEL = "your-org/CryptoGemma-4B"   # ← change this line
```

### HF Inference API limits (free tier)
| Limit            | Value                 |
|------------------|-----------------------|
| Requests/hour    | ~30–100 (varies)      |
| Max tokens out   | Configurable          |
| Cost             | **Free**              |

If rate-limited, the script auto-falls back to a simple momentum rule engine.

---

## 🔑 CoinSwitch API (Optional)

If you want to use CoinSwitch's official API:
1. Sign up at [pro.coinswitch.co](https://pro.coinswitch.co)
2. Generate API keys in the developer portal
3. Add them as GitHub secrets (see above)

**Without CoinSwitch keys**, the script uses the free [CoinGecko API](https://www.coingecko.com/api) which requires no registration and supports all 8 coins.

---

## 📊 Excel Output — `trade_tracker.xlsx`

### Sheet 1: Trade Log
| Column              | Description                                  |
|---------------------|----------------------------------------------|
| Timestamp           | UTC time of the run                          |
| Coin                | Symbol (BTC, ETH, …)                         |
| Price_INR           | Current price in ₹                           |
| 24h_Change_%        | 24-hour % change                             |
| 24h_Volume_INR      | 24-hour trading volume in ₹                  |
| AI_Action           | BUY / SELL / HOLD from AI                    |
| Confidence          | "AI" or "RULE" (fallback)                    |
| Prev_Action         | Action decided in the previous run           |
| Prev_Price_INR      | Price at time of previous decision           |
| Price_Change_%      | % change since last run                      |
| Outcome             | WIN / LOSS / NEUTRAL vs. previous prediction |
| PnL_%               | Profit & Loss % for that trade               |
| Cumulative_Correct  | Running count of correct predictions         |
| Accuracy_%          | Overall accuracy so far                      |

### Sheet 2: Summary Dashboard
Auto-calculated formulas for total trades, accuracy %, average P&L, and signal breakdown.

---

## 🖥️ Run Locally

```bash
# 1. Clone / copy files
cd crypto_trader

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install deps
pip install -r requirements.txt

# 4. Set env vars
cp .env.example .env
# Edit .env with your tokens

# 5. Run once
bash run_local.sh
# or: python main.py

# 6. Schedule locally with cron (Linux/Mac)
crontab -e
# Add: */30 * * * * cd /path/to/crypto_trader && bash run_local.sh
```

---

## 🆓 Alternative Free Platforms

| Platform               | Free Tier                        | How                                           |
|------------------------|----------------------------------|-----------------------------------------------|
| **GitHub Actions**     | 2000 min/mo (public: unlimited)  | `.github/workflows/trader.yml` ← **recommended** |
| **Railway.app**        | $5 credit/mo, ~500 hrs           | Deploy as a Python service, use `schedule` lib |
| **Render.com**         | 750 hrs/mo free                  | Cron jobs natively supported                  |
| **Replit**             | Always-on with Replit Core        | Use `schedule` library in Python              |
| **PythonAnywhere**     | 1 scheduled task free            | Free plan, set task to run every 30 min       |

---

## ⚠️ Disclaimer

This tool is for **educational and research purposes only**.  
It does **not** place real trades. All AI predictions are experimental.  
Crypto markets are highly volatile. Past prediction accuracy does not guarantee future results.
