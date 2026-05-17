"""
Google Drive uploader – uploads/updates trade_tracker.xlsx in a
designated Drive folder using a Service Account (no OAuth flow needed).

Setup (one-time, free):
  1. Go to https://console.cloud.google.com/
  2. Create a project → Enable "Google Drive API"
  3. IAM & Admin → Service Accounts → Create → Download JSON key
  4. Share your target Drive folder with the service account email
  5. Store the JSON key content as the GitHub secret GDRIVE_SERVICE_ACCOUNT_JSON
  6. Optionally set GDRIVE_FOLDER_ID to a specific folder ID (defaults to root)
"""

import io
import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

# ── Lazy-import: only needed at upload time ──────────────────────────────────
def _get_drive_service():
    """Build and return an authenticated Google Drive service object."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "google-api-python-client and google-auth are required.\n"
            "Run: pip install google-api-python-client google-auth"
        )

    creds_json = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON", "")
    if not creds_json:
        raise ValueError("GDRIVE_SERVICE_ACCOUNT_JSON env var is not set.")

    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/drive.file"]
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_existing_file(service, filename: str, folder_id: str | None) -> str | None:
    """Return the Drive file ID if a file with this name already exists in the folder."""
    query = f"name = '{filename}' and trashed = false"
    if folder_id:
        query += f" and '{folder_id}' in parents"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def upload_to_drive(local_path: Path, drive_filename: str = "trade_tracker.xlsx") -> str:
    """
    Upload or update the Excel file on Google Drive.
    Returns the public (or shareable) URL of the file.
    """
    folder_id = os.environ.get("GDRIVE_FOLDER_ID", "")  # optional; root if empty

    try:
        service = _get_drive_service()

        from googleapiclient.http import MediaFileUpload

        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        media = MediaFileUpload(str(local_path), mimetype=mime, resumable=True)

        existing_id = _find_existing_file(service, drive_filename, folder_id or None)

        if existing_id:
            # Update existing file (keeps same ID and sharing settings)
            file = (
                service.files()
                .update(fileId=existing_id, media_body=media, fields="id, webViewLink")
                .execute()
            )
            log.info(f"Google Drive: updated existing file (id={existing_id})")
        else:
            # Create new file
            metadata = {"name": drive_filename}
            if folder_id:
                metadata["parents"] = [folder_id]
            file = (
                service.files()
                .create(body=metadata, media_body=media, fields="id, webViewLink")
                .execute()
            )
            log.info(f"Google Drive: created new file (id={file['id']})")

        url = file.get("webViewLink", f"https://drive.google.com/file/d/{file['id']}/view")
        log.info(f"Google Drive URL: {url}")
        return url

    except Exception as e:
        log.error(f"Google Drive upload failed: {e}")
        return ""
