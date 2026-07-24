# Instagram投稿用画像 自動加工ツール Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google Driveの「加工依頼」フォルダに入れた写真を自動で明るさ・彩度・露出補正し、「加工済み」フォルダに出力するローカルPythonツールを作る。

**Architecture:** ローカル(Mac)で動くPythonスクリプト群。Google Drive API(OAuth)でファイルの一覧・ダウンロード・アップロード・削除を行い、Pillow/OpenCV(+pillow-heif)で画像を加工する。launchdが1日2回(22:00/23:30)スクリプトを起動し、手動実行も可能。

**Tech Stack:** Python 3, OpenCV(opencv-python), NumPy, Pillow, pillow-heif, google-api-python-client, google-auth-oauthlib, pytest

## Global Constraints

- コストゼロ: クラウド課金API・サブスクリプションは使わない。処理はすべてローカル、Google Drive APIは無料枠内
- 加工は「自然な見栄え」を目指す。背景変更等のAI生成的な加工は行わない
- 入力: JPEG/HEIC対応。出力: JPEGに統一
- 彩度ブースト初期値: 1.15倍(パラメータとして変更可能)
- 「加工済み」フォルダの安全ネット自動削除: 作成から7日経過後
- 実行スケジュール: 毎日22:00・23:30(launchd) + 手動実行コマンド
- エラー時は元画像を絶対に削除しない。ログに記録し、`.company/secretary/todos/YYYY-MM-DD.md` に通知を追記する
- コードは `photo-enhancer/` ディレクトリに置く(このリポジトリ直下、`.company/` の外)

---

### Task 1: プロジェクト雛形・設定モジュール

**Files:**
- Create: `photo-enhancer/requirements.txt`
- Create: `photo-enhancer/pytest.ini`
- Create: `photo-enhancer/config.py`
- Test: `photo-enhancer/tests/test_config.py`
- Modify: `.gitignore`(リポジトリ直下)

**Interfaces:**
- Produces: `config.Config`(dataclass)、`config.DEFAULT_CONFIG`(インスタンス)。フィールド: `request_folder_name: str`, `processed_folder_name: str`, `root_folder_name: str`, `saturation_boost: float`, `gamma: float`, `clahe_clip_limit: float`, `retention_days: int`, `run_times: List[str]`, `credentials_path: str`, `token_path: str`, `log_path: str`

- [ ] **Step 1: ディレクトリと設定ファイルの雛形を作る**

```bash
mkdir -p photo-enhancer/tests photo-enhancer/credentials photo-enhancer/logs
```

`photo-enhancer/requirements.txt`:
```
opencv-python>=4.9,<5
numpy>=1.26,<2
Pillow>=10.0,<11
pillow-heif>=0.15,<1
google-api-python-client>=2.100,<3
google-auth-httplib2>=0.2,<1
google-auth-oauthlib>=1.2,<2
pytest>=8.0,<9
```

`photo-enhancer/pytest.ini`:
```ini
[pytest]
pythonpath = .
```

- [ ] **Step 2: 失敗するテストを書く**

`photo-enhancer/tests/test_config.py`:
```python
from config import DEFAULT_CONFIG


def test_default_config_matches_spec_values():
    assert DEFAULT_CONFIG.saturation_boost == 1.15
    assert DEFAULT_CONFIG.gamma == 1.2
    assert DEFAULT_CONFIG.clahe_clip_limit == 1.5
    assert DEFAULT_CONFIG.retention_days == 7
    assert DEFAULT_CONFIG.run_times == ["22:00", "23:30"]
    assert DEFAULT_CONFIG.request_folder_name == "加工依頼"
    assert DEFAULT_CONFIG.processed_folder_name == "加工済み"
    assert DEFAULT_CONFIG.root_folder_name == "Instagram画像加工"


def test_paths_point_inside_photo_enhancer_directory():
    assert DEFAULT_CONFIG.credentials_path.endswith("credentials/credentials.json")
    assert DEFAULT_CONFIG.token_path.endswith("credentials/token.json")
    assert DEFAULT_CONFIG.log_path.endswith("logs/photo_enhancer.log")
```

- [ ] **Step 3: テストを実行し、失敗を確認する**

Run: `cd photo-enhancer && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && pytest tests/test_config.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'config'`)

- [ ] **Step 4: config.py を実装する**

`photo-enhancer/config.py`:
```python
import os
from dataclasses import dataclass, field
from typing import List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass(frozen=True)
class Config:
    request_folder_name: str = "加工依頼"
    processed_folder_name: str = "加工済み"
    root_folder_name: str = "Instagram画像加工"
    saturation_boost: float = 1.15
    gamma: float = 1.2
    clahe_clip_limit: float = 1.5
    retention_days: int = 7
    run_times: List[str] = field(default_factory=lambda: ["22:00", "23:30"])
    credentials_path: str = os.path.join(BASE_DIR, "credentials", "credentials.json")
    token_path: str = os.path.join(BASE_DIR, "credentials", "token.json")
    log_path: str = os.path.join(BASE_DIR, "logs", "photo_enhancer.log")


DEFAULT_CONFIG = Config()
```

- [ ] **Step 5: テストを実行し、成功を確認する**

Run: `pytest tests/test_config.py -v`
Expected: PASS(2 passed)

- [ ] **Step 6: .gitignore を更新する**

`.gitignore`に追記(既存の内容は保持):
```
photo-enhancer/venv/
photo-enhancer/credentials/*.json
photo-enhancer/logs/*.log
**/__pycache__/
```

- [ ] **Step 7: コミット**

```bash
cd /Users/hajirishingo/Desktop/dev/sweets-cc-company
git add .gitignore photo-enhancer/requirements.txt photo-enhancer/pytest.ini photo-enhancer/config.py photo-enhancer/tests/test_config.py
git commit -m "feat(photo-enhancer): add project scaffolding and config module"
```

---

### Task 2: 画像加工パイプライン(image_processor.py)

**Files:**
- Create: `photo-enhancer/image_processor.py`
- Test: `photo-enhancer/tests/test_image_processor.py`

**Interfaces:**
- Consumes: `config.Config`(Task 1で定義済みの `saturation_boost`, `gamma`, `clahe_clip_limit`)
- Produces: `load_image(path: str) -> numpy.ndarray`, `save_image_jpeg(image_bgr: numpy.ndarray, path: str, quality: int = 92) -> None`, `auto_white_balance(image_bgr) -> numpy.ndarray`, `auto_level(image_bgr, clip_percent: float = 1.0) -> numpy.ndarray`, `gamma_correct(image_bgr, gamma: float) -> numpy.ndarray`, `boost_saturation(image_bgr, factor: float) -> numpy.ndarray`, `apply_clahe(image_bgr, clip_limit: float) -> numpy.ndarray`, `enhance_image(image_bgr, config) -> numpy.ndarray`, `enhance_image_bytes(content: bytes, config) -> bytes`

- [ ] **Step 1: 失敗するテストを書く**

`photo-enhancer/tests/test_image_processor.py`:
```python
import numpy as np
import cv2
from PIL import Image

from config import DEFAULT_CONFIG
from image_processor import (
    auto_white_balance,
    auto_level,
    gamma_correct,
    boost_saturation,
    apply_clahe,
    enhance_image,
    enhance_image_bytes,
    load_image,
    save_image_jpeg,
)


def test_auto_white_balance_corrects_color_cast():
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[:, :, 0] = 200
    image[:, :, 1] = 100
    image[:, :, 2] = 100
    result = auto_white_balance(image)
    means = [np.mean(result[:, :, c]) for c in range(3)]
    assert max(means) - min(means) < (200 - 100) / 2


def test_auto_level_stretches_low_contrast_image():
    image = np.full((10, 10, 3), 120, dtype=np.uint8)
    image[0, 0] = [100, 100, 100]
    image[9, 9] = [150, 150, 150]
    result = auto_level(image)
    assert result.max() > 200
    assert result.min() < 50


def test_gamma_correct_brightens_dark_image():
    image = np.full((10, 10, 3), 50, dtype=np.uint8)
    result = gamma_correct(image, gamma=1.5)
    assert result.mean() > image.mean()


def test_boost_saturation_increases_mean_saturation():
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[:, :, 2] = 180
    image[:, :, 1] = 120
    image[:, :, 0] = 60
    before_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    before_sat = before_hsv[:, :, 1].mean()
    result = boost_saturation(image, factor=1.15)
    after_hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
    after_sat = after_hsv[:, :, 1].mean()
    assert after_sat > before_sat


def test_apply_clahe_does_not_change_image_shape_or_dtype():
    image = np.random.randint(0, 255, (20, 20, 3), dtype=np.uint8)
    result = apply_clahe(image, clip_limit=1.5)
    assert result.shape == image.shape
    assert result.dtype == image.dtype


def test_enhance_image_pipeline_runs_end_to_end():
    image = np.random.randint(20, 100, (30, 30, 3), dtype=np.uint8)
    result = enhance_image(image, DEFAULT_CONFIG)
    assert result.shape == image.shape
    assert result.dtype == np.uint8


def test_enhance_image_bytes_returns_valid_jpeg():
    image = np.random.randint(20, 200, (30, 30, 3), dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    result_bytes = enhance_image_bytes(encoded.tobytes(), DEFAULT_CONFIG)
    decoded = cv2.imdecode(np.frombuffer(result_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape == image.shape


def test_load_image_reads_jpeg_as_bgr_array(tmp_path):
    pil_image = Image.new("RGB", (5, 5), color=(10, 20, 30))
    path = tmp_path / "sample.jpg"
    pil_image.save(path, format="JPEG")
    result = load_image(str(path))
    assert result.shape == (5, 5, 3)


def test_save_image_jpeg_writes_readable_file(tmp_path):
    image = np.random.randint(0, 255, (10, 10, 3), dtype=np.uint8)
    path = tmp_path / "out.jpg"
    save_image_jpeg(image, str(path))
    reloaded = cv2.imread(str(path))
    assert reloaded is not None
    assert reloaded.shape == image.shape
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `pytest tests/test_image_processor.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'image_processor'`)

- [ ] **Step 3: image_processor.py を実装する**

`photo-enhancer/image_processor.py`:
```python
import io

import numpy as np
import cv2
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()


def load_image(path: str) -> np.ndarray:
    pil_image = Image.open(path).convert("RGB")
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def save_image_jpeg(image_bgr: np.ndarray, path: str, quality: int = 92) -> None:
    cv2.imwrite(path, image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])


def auto_white_balance(image_bgr: np.ndarray) -> np.ndarray:
    result = image_bgr.astype(np.float32)
    mean_b = np.mean(result[:, :, 0])
    mean_g = np.mean(result[:, :, 1])
    mean_r = np.mean(result[:, :, 2])
    mean_gray = (mean_b + mean_g + mean_r) / 3.0
    result[:, :, 0] *= mean_gray / max(mean_b, 1e-6)
    result[:, :, 1] *= mean_gray / max(mean_g, 1e-6)
    result[:, :, 2] *= mean_gray / max(mean_r, 1e-6)
    return np.clip(result, 0, 255).astype(np.uint8)


def auto_level(image_bgr: np.ndarray, clip_percent: float = 1.0) -> np.ndarray:
    result = np.zeros_like(image_bgr)
    for c in range(3):
        channel = image_bgr[:, :, c]
        low, high = np.percentile(channel, [clip_percent, 100 - clip_percent])
        if high <= low:
            result[:, :, c] = channel
            continue
        stretched = (channel.astype(np.float32) - low) * 255.0 / (high - low)
        result[:, :, c] = np.clip(stretched, 0, 255).astype(np.uint8)
    return result


def gamma_correct(image_bgr: np.ndarray, gamma: float) -> np.ndarray:
    inv_gamma = 1.0 / gamma
    table = np.array([(i / 255.0) ** inv_gamma * 255 for i in range(256)]).astype(np.uint8)
    return cv2.LUT(image_bgr, table)


def boost_saturation(image_bgr: np.ndarray, factor: float) -> np.ndarray:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def apply_clahe(image_bgr: np.ndarray, clip_limit: float) -> np.ndarray:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    merged = cv2.merge((l_enhanced, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def enhance_image(image_bgr: np.ndarray, config) -> np.ndarray:
    result = auto_white_balance(image_bgr)
    result = auto_level(result)
    result = gamma_correct(result, config.gamma)
    result = boost_saturation(result, config.saturation_boost)
    result = apply_clahe(result, config.clahe_clip_limit)
    return result


def enhance_image_bytes(content: bytes, config) -> bytes:
    array = np.frombuffer(content, dtype=np.uint8)
    image_bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image_bgr is None:
        pil_image = Image.open(io.BytesIO(content)).convert("RGB")
        image_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    enhanced = enhance_image(image_bgr, config)
    success, buffer = cv2.imencode(".jpg", enhanced, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not success:
        raise ValueError("JPEGエンコードに失敗しました")
    return buffer.tobytes()
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `pytest tests/test_image_processor.py -v`
Expected: PASS(9 passed)

- [ ] **Step 5: コミット**

```bash
git add photo-enhancer/image_processor.py photo-enhancer/tests/test_image_processor.py
git commit -m "feat(photo-enhancer): add image enhancement pipeline"
```

---

### Task 3: Google Drive クライアント(drive_client.py)

**Files:**
- Create: `photo-enhancer/drive_client.py`
- Test: `photo-enhancer/tests/test_drive_client.py`

**Interfaces:**
- Produces: `get_credentials(credentials_path: str, token_path: str) -> Credentials`, `build_service(creds) -> Resource`, `find_or_create_folder(service, name: str, parent_id: Optional[str] = None) -> str`, `ensure_folder_structure(service, root_name: str, request_name: str, processed_name: str) -> tuple[str, str]`, `list_image_files(service, folder_id: str) -> list[dict]`, `download_file(service, file_id: str) -> bytes`, `upload_file(service, folder_id: str, filename: str, content: bytes, mime_type: str = "image/jpeg") -> str`, `delete_file(service, file_id: str) -> None`, `filter_files_older_than(files: list[dict], days: int, now: Optional[datetime] = None) -> list[dict]`, `class DriveClient`(list_image_files/download_file/upload_file/delete_file をラップ)
- Consumes(Task 4以降): `DriveClient` インスタンスのメソッド群

- [ ] **Step 1: 失敗するテストを書く**

`photo-enhancer/tests/test_drive_client.py`:
```python
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
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `pytest tests/test_drive_client.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'drive_client'`)

- [ ] **Step 3: drive_client.py を実装する**

`photo-enhancer/drive_client.py`:
```python
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
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `pytest tests/test_drive_client.py -v`
Expected: PASS(9 passed)

- [ ] **Step 5: コミット**

```bash
git add photo-enhancer/drive_client.py photo-enhancer/tests/test_drive_client.py
git commit -m "feat(photo-enhancer): add Google Drive client wrapper"
```

---

### Task 4: 加工オーケストレーション・ログ・TODO通知

**Files:**
- Create: `photo-enhancer/orchestrator.py`
- Create: `photo-enhancer/logger_util.py`
- Test: `photo-enhancer/tests/test_orchestrator.py`
- Test: `photo-enhancer/tests/test_logger_util.py`

**Interfaces:**
- Consumes: Task 3の `DriveClient`(list_image_files/download_file/upload_file/delete_file)、Task 2の `enhance_image_bytes(content, config) -> bytes`、Task 3の `filter_files_older_than`
- Produces: `process_new_images(drive_client, request_folder_id, processed_folder_id, config, enhance_fn, logger) -> tuple[int, int]`(processed_count, error_count)、`cleanup_old_processed(drive_client, processed_folder_id, retention_days, logger, now=None) -> int`(deleted_count)、`setup_logger(log_path: str) -> logging.Logger`、`append_todo_notification(todos_dir: str, message: str, today: date = None) -> None`

- [ ] **Step 1: 失敗するテストを書く(orchestrator)**

`photo-enhancer/tests/test_orchestrator.py`:
```python
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
```

`photo-enhancer/tests/test_logger_util.py`:
```python
from logger_util import setup_logger, append_todo_notification


def test_setup_logger_writes_to_file(tmp_path):
    log_path = tmp_path / "app.log"
    logger = setup_logger(str(log_path))
    logger.info("テストメッセージ")
    for handler in logger.handlers:
        handler.flush()
    assert log_path.exists()
    assert "テストメッセージ" in log_path.read_text(encoding="utf-8")


def test_append_todo_notification_creates_file_when_missing(tmp_path):
    from datetime import date

    todos_dir = tmp_path / "todos"
    append_todo_notification(str(todos_dir), "エラーが発生しました", today=date(2026, 7, 25))
    todo_file = todos_dir / "2026-07-25.md"
    assert todo_file.exists()
    assert "エラーが発生しました" in todo_file.read_text(encoding="utf-8")


def test_append_todo_notification_appends_to_existing_file(tmp_path):
    from datetime import date

    todos_dir = tmp_path / "todos"
    todos_dir.mkdir()
    todo_file = todos_dir / "2026-07-25.md"
    todo_file.write_text("# 既存の内容\n- [ ] 既存タスク\n", encoding="utf-8")

    append_todo_notification(str(todos_dir), "エラーが発生しました", today=date(2026, 7, 25))

    content = todo_file.read_text(encoding="utf-8")
    assert "既存タスク" in content
    assert "エラーが発生しました" in content
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `pytest tests/test_orchestrator.py tests/test_logger_util.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: orchestrator.py と logger_util.py を実装する**

`photo-enhancer/orchestrator.py`:
```python
import os

from drive_client import filter_files_older_than


def process_new_images(drive_client, request_folder_id, processed_folder_id, config, enhance_fn, logger):
    files = drive_client.list_image_files(request_folder_id)
    processed_count = 0
    error_count = 0
    for file in files:
        file_id = file["id"]
        name = file["name"]
        try:
            content = drive_client.download_file(file_id)
            enhanced_bytes = enhance_fn(content, config)
            new_name = os.path.splitext(name)[0] + ".jpg"
            drive_client.upload_file(processed_folder_id, new_name, enhanced_bytes)
            drive_client.delete_file(file_id)
            processed_count += 1
        except Exception as exc:
            error_count += 1
            logger.error(f"加工失敗: {name} ({exc})")
    return processed_count, error_count


def cleanup_old_processed(drive_client, processed_folder_id, retention_days, logger, now=None):
    files = drive_client.list_image_files(processed_folder_id)
    old_files = filter_files_older_than(files, retention_days, now)
    deleted_count = 0
    for file in old_files:
        drive_client.delete_file(file["id"])
        deleted_count += 1
    if deleted_count:
        logger.info(f"安全ネット削除: {deleted_count}件")
    return deleted_count
```

`photo-enhancer/logger_util.py`:
```python
import os
from datetime import date


def setup_logger(log_path: str):
    import logging

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger("photo_enhancer")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def append_todo_notification(todos_dir: str, message: str, today: date = None) -> None:
    today = today or date.today()
    os.makedirs(todos_dir, exist_ok=True)
    todo_path = os.path.join(todos_dir, f"{today.isoformat()}.md")
    if not os.path.exists(todo_path):
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write(f'---\ndate: "{today.isoformat()}"\ntype: daily\n---\n\n# {today.isoformat()}\n\n## メモ・振り返り\n- {message}\n')
        return
    with open(todo_path, "a", encoding="utf-8") as f:
        f.write(f"- {message}\n")
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `pytest tests/test_orchestrator.py tests/test_logger_util.py -v`
Expected: PASS(6 passed)

- [ ] **Step 5: コミット**

```bash
git add photo-enhancer/orchestrator.py photo-enhancer/logger_util.py photo-enhancer/tests/test_orchestrator.py photo-enhancer/tests/test_logger_util.py
git commit -m "feat(photo-enhancer): add orchestration, logging and TODO notification"
```

---

### Task 5: CLIエントリポイント・launchd・README

**Files:**
- Create: `photo-enhancer/main.py`
- Create: `photo-enhancer/com.sweets.photoenhancer.plist`
- Create: `photo-enhancer/README.md`
- Test: `photo-enhancer/tests/test_main.py`
- Test: `photo-enhancer/tests/test_plist.py`

**Interfaces:**
- Consumes: Task 3の `get_credentials`, `build_service`, `ensure_folder_structure`, `DriveClient`。Task 2の `enhance_image_bytes`。Task 4の `process_new_images`, `cleanup_old_processed`, `setup_logger`, `append_todo_notification`。Task 1の `DEFAULT_CONFIG`
- Produces: `main.main() -> None`(CLIエントリポイント)

- [ ] **Step 1: 失敗するテストを書く**

`photo-enhancer/tests/test_main.py`:
```python
import main as main_module


def test_main_runs_pipeline_and_reports_counts(monkeypatch):
    calls = []

    monkeypatch.setattr(main_module, "get_credentials", lambda *a, **k: "creds")
    monkeypatch.setattr(main_module, "build_service", lambda creds: "service")
    monkeypatch.setattr(
        main_module, "ensure_folder_structure",
        lambda service, root, req, proc: ("request-id", "processed-id"),
    )

    def fake_process_new_images(drive_client, request_id, processed_id, config, enhance_fn, logger):
        calls.append(("process", request_id, processed_id))
        return 2, 0

    def fake_cleanup(drive_client, processed_id, retention_days, logger):
        calls.append(("cleanup", processed_id, retention_days))
        return 1

    monkeypatch.setattr(main_module, "process_new_images", fake_process_new_images)
    monkeypatch.setattr(main_module, "cleanup_old_processed", fake_cleanup)

    notified = []
    monkeypatch.setattr(
        main_module, "append_todo_notification",
        lambda todos_dir, message: notified.append(message),
    )

    main_module.main()

    assert ("process", "request-id", "processed-id") in calls
    assert ("cleanup", "processed-id", main_module.DEFAULT_CONFIG.retention_days) in calls
    assert notified == []


def test_main_notifies_todo_on_errors(monkeypatch):
    monkeypatch.setattr(main_module, "get_credentials", lambda *a, **k: "creds")
    monkeypatch.setattr(main_module, "build_service", lambda creds: "service")
    monkeypatch.setattr(
        main_module, "ensure_folder_structure",
        lambda service, root, req, proc: ("request-id", "processed-id"),
    )
    monkeypatch.setattr(main_module, "process_new_images", lambda *a, **k: (1, 2))
    monkeypatch.setattr(main_module, "cleanup_old_processed", lambda *a, **k: 0)

    notified = []
    monkeypatch.setattr(
        main_module, "append_todo_notification",
        lambda todos_dir, message: notified.append(message),
    )

    main_module.main()

    assert len(notified) == 1
    assert "エラー" in notified[0]
```

`photo-enhancer/tests/test_plist.py`:
```python
import plistlib
from pathlib import Path


def test_launchd_plist_is_valid_and_scheduled_correctly():
    plist_path = Path(__file__).parent.parent / "com.sweets.photoenhancer.plist"
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["Label"] == "com.sweets.photoenhancer"
    intervals = data["StartCalendarInterval"]
    assert len(intervals) == 2
    times = sorted((entry["Hour"], entry["Minute"]) for entry in intervals)
    assert times == [(22, 0), (23, 30)]
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `pytest tests/test_main.py tests/test_plist.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'main'` / `FileNotFoundError`)

- [ ] **Step 3: main.py, plist, README を実装する**

`photo-enhancer/main.py`:
```python
import os

from config import DEFAULT_CONFIG
from drive_client import get_credentials, build_service, ensure_folder_structure, DriveClient
from image_processor import enhance_image_bytes
from orchestrator import process_new_images, cleanup_old_processed
from logger_util import setup_logger, append_todo_notification


def main():
    config = DEFAULT_CONFIG
    logger = setup_logger(config.log_path)
    logger.info("photo-enhancer 実行開始")

    creds = get_credentials(config.credentials_path, config.token_path)
    service = build_service(creds)
    drive_client = DriveClient(service)

    request_folder_id, processed_folder_id = ensure_folder_structure(
        service, config.root_folder_name, config.request_folder_name, config.processed_folder_name
    )

    processed_count, error_count = process_new_images(
        drive_client, request_folder_id, processed_folder_id, config, enhance_image_bytes, logger
    )
    deleted_count = cleanup_old_processed(
        drive_client, processed_folder_id, config.retention_days, logger
    )

    logger.info(f"完了: 加工{processed_count}件 / エラー{error_count}件 / 安全ネット削除{deleted_count}件")

    if error_count > 0:
        company_todos_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", ".company", "secretary", "todos"
        )
        append_todo_notification(
            company_todos_dir,
            f"【photo-enhancer】画像加工でエラーが{error_count}件発生しました。ログ({config.log_path})を確認してください。",
        )


if __name__ == "__main__":
    main()
```

`photo-enhancer/com.sweets.photoenhancer.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sweets.photoenhancer</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/hajirishingo/Desktop/dev/sweets-cc-company/photo-enhancer/venv/bin/python3</string>
        <string>/Users/hajirishingo/Desktop/dev/sweets-cc-company/photo-enhancer/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/hajirishingo/Desktop/dev/sweets-cc-company/photo-enhancer</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>22</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>23</integer>
            <key>Minute</key>
            <integer>30</integer>
        </dict>
    </array>
    <key>StandardOutPath</key>
    <string>/Users/hajirishingo/Desktop/dev/sweets-cc-company/photo-enhancer/logs/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/hajirishingo/Desktop/dev/sweets-cc-company/photo-enhancer/logs/launchd.err.log</string>
</dict>
</plist>
```

`photo-enhancer/README.md`:
```markdown
# photo-enhancer

Google Driveの「加工依頼」フォルダに入れた写真を自動で明るさ・彩度・露出補正し、「加工済み」フォルダに出力するツール。

## セットアップ

### 1. Python環境

\`\`\`bash
cd photo-enhancer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
\`\`\`

### 2. Google Drive APIのOAuth認証情報を作成

1. [Google Cloud Console](https://console.cloud.google.com/)で新しいプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」で **Google Drive API** を有効化
3. 「認証情報」→「認証情報を作成」→「OAuthクライアントID」→アプリケーションの種類は **デスクトップアプリ**
4. 作成したクライアントIDの認証情報をJSONでダウンロードし、`photo-enhancer/credentials/credentials.json` として保存

### 3. 初回実行(トークン発行)

\`\`\`bash
source venv/bin/activate
python3 main.py
\`\`\`

初回はブラウザが開くのでGoogleアカウントでログインし、アクセスを許可してください。`credentials/token.json` が自動生成されます。以降はブラウザ操作なしで動きます。

Google Driveに「Instagram画像加工」フォルダ(配下に「加工依頼」「加工済み」)が自動で作成されます。

## 使い方

- 「加工依頼」フォルダにスマホ/Driveアプリから写真をアップロードする
- 通常は1日2回(22:00・23:30)自動実行される
- 急ぎのときは手動実行:

\`\`\`bash
cd photo-enhancer
source venv/bin/activate
python3 main.py
\`\`\`

## 自動実行(launchd)の登録

\`\`\`bash
cp com.sweets.photoenhancer.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sweets.photoenhancer.plist
\`\`\`

停止する場合:

\`\`\`bash
launchctl unload ~/Library/LaunchAgents/com.sweets.photoenhancer.plist
\`\`\`

## ログ・エラー通知

- 実行ログ: `logs/photo_enhancer.log`
- 加工エラーが発生した場合、`.company/secretary/todos/YYYY-MM-DD.md` に通知が追記される
- 加工に失敗した画像は「加工依頼」フォルダに残るので、そのまま次回再試行される

## 設定の変更

`config.py` の `Config` クラスで彩度ブースト量・ガンマ値・安全ネット削除日数などを調整できる。
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `pytest tests/test_main.py tests/test_plist.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: 全テストを通しで実行する**

Run: `pytest -v`
Expected: PASS(全テスト成功)

- [ ] **Step 6: コミット**

```bash
git add photo-enhancer/main.py photo-enhancer/com.sweets.photoenhancer.plist photo-enhancer/README.md photo-enhancer/tests/test_main.py photo-enhancer/tests/test_plist.py
git commit -m "feat(photo-enhancer): add CLI entry point, launchd schedule and setup docs"
```

---

### Task 6: 開発部門の新設とドキュメント連携

**Files:**
- Create: `.company/engineering/CLAUDE.md`
- Create: `.company/engineering/docs/photo-enhancer.md`
- Modify: `.company/CLAUDE.md`
- Modify: `.company/marketing/content-seeds.md`

**Interfaces:**
- なし(ドキュメントのみ。自動テストは対象外)

- [ ] **Step 1: 開発部門のCLAUDE.mdを作成する**

`.company/engineering/CLAUDE.md`:
```markdown
# 開発

## 役割
技術ドキュメント、設計書、デバッグログを管理する。

## ルール
- 技術ドキュメントは `docs/topic-name.md`
- デバッグログは `debug-log/YYYY-MM-DD-issue-name.md`
- デバッグのステータス: open → investigating → resolved → closed
- 設計書は必ず「概要」「設計・方針」「詳細」の構成にする
- バグ修正時は「再発防止」セクションを必ず記入
- 技術的な意思決定は secretary/notes/ に意思決定ログとして残す

## フォルダ構成
- `docs/` - 技術ドキュメント・設計書
- `debug-log/` - デバッグ・バグ調査ログ
```

- [ ] **Step 2: photo-enhancerの技術ドキュメントを作成する**

`.company/engineering/docs/photo-enhancer.md`:
```markdown
---
created: "2026-07-25"
topic: "photo-enhancer"
type: technical-doc
tags: [marketing, automation]
---

# photo-enhancer(Instagram投稿用画像自動加工ツール)

## 概要
Google Driveの「加工依頼」フォルダに入れた写真を自動で明るさ・彩度・露出補正し、「加工済み」フォルダに出力するローカルPythonツール。詳細設計は `docs/superpowers/specs/2026-07-25-photo-enhancer-design.md`、実装計画は `docs/superpowers/plans/2026-07-25-photo-enhancer.md` を参照。

## 設計・方針
- コード: `photo-enhancer/`(リポジトリ直下)
- 実行: launchdで毎日22:00・23:30 + 手動実行
- コスト: ゼロ(ローカル処理、Google Drive APIは無料枠)

## 詳細
セットアップ手順は `photo-enhancer/README.md` を参照。

## 参考
- 設計書: `docs/superpowers/specs/2026-07-25-photo-enhancer-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-25-photo-enhancer.md`
```

- [ ] **Step 3: .company/CLAUDE.md の組織構成・部署一覧を更新する**

`.company/CLAUDE.md` の組織構成ツリーに以下を追加:
```
└── engineering/
    ├── CLAUDE.md
    └── docs/
```

部署一覧テーブルに以下の行を追加:
```
| 開発 | engineering | 技術ドキュメント・設計書・デバッグログ管理。 |
```

- [ ] **Step 4: マーケティング側から参照を追記する**

`.company/marketing/content-seeds.md` の「SNS運用知見」セクション末尾に追記:
```
- 【2026-07-25】投稿画像の自動加工ツール(photo-enhancer)を開発。詳細は `.company/engineering/docs/photo-enhancer.md` 参照
```

- [ ] **Step 5: 内容を目視確認する**

Run: `cat .company/engineering/CLAUDE.md .company/engineering/docs/photo-enhancer.md`
Expected: 意図した内容が表示される

- [ ] **Step 6: コミット**

```bash
git add .company/engineering .company/CLAUDE.md .company/marketing/content-seeds.md
git commit -m "docs: add engineering department and photo-enhancer documentation"
```
