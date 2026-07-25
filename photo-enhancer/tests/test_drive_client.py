from datetime import datetime, timezone
from unittest.mock import MagicMock

from drive_client import (
    find_or_create_folder,
    ensure_folder_structure,
    list_image_files,
    download_file,
    upload_file,
    delete_file,
    filter_files_older_than,
    DriveClient,
)


def make_service_with_list_result(files):
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {"files": files}
    return service


def test_find_or_create_folder_returns_existing_id():
    service = make_service_with_list_result([{"id": "existing-id", "name": "加工依頼"}])
    folder_id = find_or_create_folder(service, "加工依頼", parent_id="root-id")
    assert folder_id == "existing-id"
    service.files.return_value.create.assert_not_called()


def test_find_or_create_folder_creates_when_missing():
    service = make_service_with_list_result([])
    service.files.return_value.create.return_value.execute.return_value = {"id": "new-id"}
    folder_id = find_or_create_folder(service, "加工依頼", parent_id="root-id")
    assert folder_id == "new-id"
    service.files.return_value.create.assert_called_once()


def test_ensure_folder_structure_creates_root_and_children():
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {"files": []}
    service.files.return_value.create.return_value.execute.side_effect = [
        {"id": "root-id"},
        {"id": "request-id"},
        {"id": "processed-id"},
    ]
    request_id, processed_id = ensure_folder_structure(service, "Instagram画像加工", "加工依頼", "加工済み")
    assert request_id == "request-id"
    assert processed_id == "processed-id"


def test_list_image_files_filters_by_folder_and_returns_files():
    files = [{"id": "f1", "name": "a.jpg", "mimeType": "image/jpeg", "createdTime": "2026-07-01T00:00:00Z"}]
    service = make_service_with_list_result(files)
    result = list_image_files(service, "folder-id")
    assert result == files
    _, kwargs = service.files.return_value.list.call_args
    assert "folder-id" in kwargs["q"]
    assert "image/" in kwargs["q"]


def test_download_file_returns_bytes(monkeypatch):
    service = MagicMock()
    service.files.return_value.get_media.return_value = "media-request"

    class FakeDownloader:
        def __init__(self, buffer, request):
            self.buffer = buffer
            self.request = request

        def next_chunk(self):
            self.buffer.write(b"chunk-data")
            return None, True

    monkeypatch.setattr("drive_client.MediaIoBaseDownload", FakeDownloader)
    result = download_file(service, "file-id")
    assert result == b"chunk-data"
    service.files.return_value.get_media.assert_called_once_with(fileId="file-id")


def test_upload_file_calls_create_with_correct_metadata():
    service = MagicMock()
    service.files.return_value.create.return_value.execute.return_value = {"id": "uploaded-id"}
    result_id = upload_file(service, "folder-id", "photo.jpg", b"binary-content")
    assert result_id == "uploaded-id"
    _, kwargs = service.files.return_value.create.call_args
    assert kwargs["body"]["name"] == "photo.jpg"
    assert kwargs["body"]["parents"] == ["folder-id"]


def test_delete_file_calls_delete_with_file_id():
    service = MagicMock()
    delete_file(service, "file-id")
    service.files.return_value.delete.assert_called_once_with(fileId="file-id")


def test_filter_files_older_than_returns_only_old_files():
    now = datetime(2026, 7, 25, tzinfo=timezone.utc)
    files = [
        {"id": "old", "createdTime": "2026-07-10T00:00:00Z"},
        {"id": "recent", "createdTime": "2026-07-24T00:00:00Z"},
    ]
    result = filter_files_older_than(files, days=7, now=now)
    ids = [f["id"] for f in result]
    assert ids == ["old"]


def test_drive_client_wraps_functions():
    service = make_service_with_list_result([{"id": "f1", "name": "a.jpg"}])
    client = DriveClient(service)
    result = client.list_image_files("folder-id")
    assert result == [{"id": "f1", "name": "a.jpg"}]
