# Google Drive Setup Guide (Free, ~5 minutes)

This guide gets your `trade_tracker.xlsx` auto-uploaded to your Google Drive
after every 30-minute cron run — for free, using a Google Service Account.

---

## Step 1 — Create a Google Cloud Project (free)

1. Go to → https://console.cloud.google.com/
2. Click **"Select a project"** → **"New Project"**
3. Name it anything, e.g. `crypto-trader`
4. Click **Create**

---

## Step 2 — Enable the Google Drive API

1. In your new project, go to:
   **APIs & Services → Library**
2. Search for **"Google Drive API"**
3. Click it → **Enable**

---

## Step 3 — Create a Service Account

1. Go to: **IAM & Admin → Service Accounts**
2. Click **"+ Create Service Account"**
3. Name: `crypto-trader-bot` → **Create and Continue**
4. Role: skip (click **Continue** → **Done**)

---

## Step 4 — Download the JSON Key

1. Click your new service account email
2. Go to **Keys** tab → **Add Key → Create new key**
3. Choose **JSON** → **Create**
4. A `.json` file downloads to your computer — **keep this safe!**

The file looks like:
```json
{
  "type": "service_account",
  "project_id": "crypto-trader-xxxxx",
  "private_key_id": "...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "client_email": "crypto-trader-bot@crypto-trader-xxxxx.iam.gserviceaccount.com",
  ...
}
```

---

## Step 5 — Share a Drive Folder with the Service Account

1. Go to **Google Drive** → create a folder, e.g. `Crypto Trader Logs`
2. Right-click the folder → **Share**
3. Paste the **client_email** from your JSON file
   (looks like `crypto-trader-bot@....iam.gserviceaccount.com`)
4. Give it **Editor** access → **Send**
5. Copy the **folder ID** from the URL:
   `https://drive.google.com/drive/folders/` **`THIS_IS_YOUR_FOLDER_ID`**

---

## Step 6 — Add Secrets to GitHub

Go to your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name                    | Value                                            |
|-------------------------------|--------------------------------------------------|
| `GDRIVE_SERVICE_ACCOUNT_JSON` | Paste the **entire contents** of the JSON file   |
| `GDRIVE_FOLDER_ID`            | The folder ID from Step 5 (e.g. `1aBcDeFgHiJ...`) |
| `HF_API_TOKEN`                | Your HuggingFace token                           |

> **Tip**: Open the JSON file in a text editor, Select All, Copy — paste directly into the secret value box. GitHub handles multi-line secrets fine.

---

## Step 7 — Done! ✅

On the next run (or trigger it manually via Actions → Run workflow),
the script will:
1. Fetch prices & run AI analysis
2. Update `trade_tracker.xlsx` locally
3. Upload/overwrite it in your Drive folder
4. Log the Drive URL in the Actions run output

The file stays at the same Drive URL every time (it updates in-place),
so you can bookmark it or share it with others.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `GDRIVE_SERVICE_ACCOUNT_JSON not set` | Check the secret name exactly matches |
| `403 Forbidden` on Drive | Make sure you shared the folder with the service account email |
| File appears in root Drive, not folder | Double-check `GDRIVE_FOLDER_ID` secret is set correctly |
| `ModuleNotFoundError: google` | Ensure `requirements.txt` includes `google-api-python-client` |
