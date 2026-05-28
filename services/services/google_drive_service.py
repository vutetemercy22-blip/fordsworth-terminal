from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from services.config_service import BASE_DIR


SCOPES = ["https://www.googleapis.com/auth/drive.file"]

DEFAULT_CREDENTIALS_PATH = BASE_DIR / "credentials" / "google_service_account.json"


def credentials_file_exists() -> bool:
    return DEFAULT_CREDENTIALS_PATH.exists()


def build_drive_service():
    """
    Build Google Drive service using a service-account JSON file.
    """
    if not DEFAULT_CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Google credentials file not found: {DEFAULT_CREDENTIALS_PATH}"
        )

    credentials = service_account.Credentials.from_service_account_file(
        DEFAULT_CREDENTIALS_PATH,
        scopes=SCOPES,
    )

    return build("drive", "v3", credentials=credentials)


def create_drive_folder(folder_name: str) -> str:
    """
    Create a folder in Google Drive and return its folder ID.
    """
    service = build_drive_service()

    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }

    folder = service.files().create(
        body=file_metadata,
        fields="id",
    ).execute()

    return folder["id"]


def upload_file_to_drive(
    local_file_path: Path,
    folder_id: Optional[str] = None,
) -> dict:
    """
    Upload a local file to Google Drive.
    If folder_id is supplied, upload into that Drive folder.
    """
    service = build_drive_service()

    if not local_file_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_file_path}")

    file_metadata = {
        "name": local_file_path.name,
    }

    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaFileUpload(
        str(local_file_path),
        resumable=True,
    )

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name, webViewLink",
    ).execute()

    return uploaded_file


def list_recent_drive_files(limit: int = 10) -> list[dict]:
    """
    List recent files uploaded or visible to the service account.
    """
    service = build_drive_service()

    results = service.files().list(
        pageSize=limit,
        orderBy="modifiedTime desc",
        fields="files(id, name, mimeType, modifiedTime, webViewLink)",
    ).execute()

    return results.get("files", [])