"""
Google Drive uploader using OAuth2 (personal Google account).
Works with regular Google Drive — no Shared Drive needed.

First run: opens browser to authenticate and saves token.json
Subsequent runs: uses saved token automatically (no browser needed).
"""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

OAUTH_CREDS_FILE = Path("oauth_credentials.json")
TOKEN_FILE       = Path("token.json")
SCOPES           = ["https://www.googleapis.com/auth/drive.file"]


def _get_oauth_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None

    # Load saved token if exists
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # If no valid token, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check if running in GitHub Actions (no browser)
            if os.environ.get("GITHUB_ACTIONS"):
                # Load token from environment variable
                token_json = os.environ.get("GDRIVE_OAUTH_TOKEN", "")
                if not token_json:
                    raise ValueError(
                        "GDRIVE_OAUTH_TOKEN secret not set in GitHub Actions. "
                        "Run locally first to generate token.json, then add its "
                        "contents as the GDRIVE_OAUTH_TOKEN secret."
                    )
                creds = Credentials.from_authorized_user_info(
                    json.loads(token_json), SCOPES
                )
            else:
                # Local: open browser for one-time auth
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(OAUTH_CREDS_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0)

        # Save token for future runs
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        log.info(f"Token saved to {TOKEN_FILE}")

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_existing_file(service, filename: str, folder_id: str) -> str | None:
    query = f"name = '{filename}' and trashed = false"
    if folder_id:
        query += f" and '{folder_id}' in parents"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def upload_to_drive(local_path: Path, drive_filename: str = "trade_tracker.xlsx") -> str:
    folder_id = os.environ.get("GDRIVE_FOLDER_ID", "")

    try:
        service = _get_oauth_service()
        from googleapiclient.http import MediaFileUpload

        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        media = MediaFileUpload(str(local_path), mimetype=mime, resumable=True)

        existing_id = _find_existing_file(service, drive_filename, folder_id or None)

        if existing_id:
            file = (
                service.files()
                .update(fileId=existing_id, media_body=media, fields="id, webViewLink")
                .execute()
            )
            log.info(f"Google Drive: updated (id={existing_id})")
        else:
            metadata = {"name": drive_filename}
            if folder_id:
                metadata["parents"] = [folder_id]
            file = (
                service.files()
                .create(body=metadata, media_body=media, fields="id, webViewLink")
                .execute()
            )
            log.info(f"Google Drive: created (id={file['id']})")

        url = file.get("webViewLink", f"https://drive.google.com/file/d/{file['id']}/view")
        log.info(f"Google Drive URL: {url}")
        return url

    except Exception as e:
        log.error(f"Google Drive upload failed: {e}")
        return ""