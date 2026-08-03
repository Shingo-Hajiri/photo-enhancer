import io
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_credentials(credentials_path: str, token_path: str) -> Credentials:
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
    return creds


def build_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


def find_or_create_folder(service, name: str, parent_id: Optional[str] = None) -> str:
    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    response = service.files().list(q=query, fields="files(id, name)").execute()
    files = response.get("files", [])
    if files:
        return files[0]["id"]
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    created = service.files().create(body=metadata, fields="id").execute()
    return created["id"]


def ensure_folder_structure(service, root_name: str, request_name: str, processed_name: str):
    root_id = find_or_create_folder(service, root_name)
    request_id = find_or_create_folder(service, request_name, parent_id=root_id)
    processed_id = find_or_create_folder(service, processed_name, parent_id=root_id)
    return request_id, processed_id


def list_image_files(service, folder_id: str) -> List[Dict[str, Any]]:
    query = f"'{folder_id}' in parents and trashed = false and mimeType contains 'image/'"
    response = service.files().list(
        q=query, fields="files(id, name, mimeType, createdTime)"
    ).execute()
    return response.get("files", [])


def download_file(service, file_id: str) -> bytes:
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def upload_file(service, folder_id: str, filename: str, content: bytes, mime_type: str = "image/jpeg") -> str:
    metadata = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
    created = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return created["id"]


def delete_file(service, file_id: str) -> None:
    service.files().delete(fileId=file_id).execute()


def filter_files_older_than(
    files: List[Dict[str, Any]], days: int, now: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    old_files = []
    for file in files:
        created = datetime.fromisoformat(file["createdTime"].replace("Z", "+00:00"))
        if created < cutoff:
            old_files.append(file)
    return old_files


class DriveClient:
    def __init__(self, service):
        self.service = service

    def list_image_files(self, folder_id: str) -> List[Dict[str, Any]]:
        return list_image_files(self.service, folder_id)

    def download_file(self, file_id: str) -> bytes:
        return download_file(self.service, file_id)

    def upload_file(self, folder_id: str, filename: str, content: bytes, mime_type: str = "image/jpeg") -> str:
        return upload_file(self.service, folder_id, filename, content, mime_type)

    def delete_file(self, file_id: str) -> None:
        delete_file(self.service, file_id)
