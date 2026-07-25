import logging

from orchestrator import process_new_images, cleanup_old_processed


class FakeDriveClient:
    def __init__(self):
        self.folders = {}
        self.deleted_ids = []
        self.uploaded = []

    def seed_folder(self, folder_id, files):
        self.folders[folder_id] = files

    def list_image_files(self, folder_id):
        return [
            {"id": f["id"], "name": f["name"], "createdTime": f["createdTime"]}
            for f in self.folders.get(folder_id, [])
        ]

    def download_file(self, file_id):
        for files in self.folders.values():
            for f in files:
                if f["id"] == file_id:
                    return f["content"]
        raise ValueError(f"file not found: {file_id}")

    def upload_file(self, folder_id, filename, content, mime_type="image/jpeg"):
        new_id = f"{folder_id}-{filename}"
        self.folders.setdefault(folder_id, []).append(
            {"id": new_id, "name": filename, "createdTime": "2026-07-25T00:00:00Z", "content": content}
        )
        self.uploaded.append((folder_id, filename, content))
        return new_id

    def delete_file(self, file_id):
        self.deleted_ids.append(file_id)
        for files in self.folders.values():
            files[:] = [f for f in files if f["id"] != file_id]


def make_logger():
    logger = logging.getLogger("test-orchestrator")
    logger.addHandler(logging.NullHandler())
    return logger


def test_process_new_images_uploads_enhances_and_deletes_original():
    client = FakeDriveClient()
    client.seed_folder(
        "request",
        [{"id": "req-1", "name": "photo1.jpg", "createdTime": "2026-07-25T00:00:00Z", "content": b"raw-bytes"}],
    )

    def fake_enhance(content, config):
        return b"enhanced-" + content

    processed_count, error_count = process_new_images(
        client, "request", "processed", config=object(), enhance_fn=fake_enhance, logger=make_logger()
    )

    assert processed_count == 1
    assert error_count == 0
    assert client.deleted_ids == ["req-1"]
    assert client.uploaded == [("processed", "photo1.jpg", b"enhanced-raw-bytes")]


def test_process_new_images_keeps_original_when_enhance_fails():
    client = FakeDriveClient()
    client.seed_folder(
        "request",
        [{"id": "req-1", "name": "broken.jpg", "createdTime": "2026-07-25T00:00:00Z", "content": b"raw-bytes"}],
    )

    def failing_enhance(content, config):
        raise ValueError("加工失敗")

    processed_count, error_count = process_new_images(
        client, "request", "processed", config=object(), enhance_fn=failing_enhance, logger=make_logger()
    )

    assert processed_count == 0
    assert error_count == 1
    assert client.deleted_ids == []
    assert client.uploaded == []


def test_cleanup_old_processed_deletes_only_files_older_than_retention():
    from datetime import datetime, timezone

    client = FakeDriveClient()
    client.seed_folder(
        "processed",
        [
            {"id": "old", "name": "old.jpg", "createdTime": "2026-07-10T00:00:00Z", "content": b"x"},
            {"id": "recent", "name": "recent.jpg", "createdTime": "2026-07-24T00:00:00Z", "content": b"y"},
        ],
    )
    now = datetime(2026, 7, 25, tzinfo=timezone.utc)

    deleted_count = cleanup_old_processed(client, "processed", retention_days=7, logger=make_logger(), now=now)

    assert deleted_count == 1
    assert client.deleted_ids == ["old"]
