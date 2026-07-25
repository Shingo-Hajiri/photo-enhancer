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
    adaptive_bright_threshold: float = 165.0
    adaptive_dark_threshold: float = 110.0
    adaptive_min_strength: float = 0.15
    retention_days: int = 7
    run_times: List[str] = field(default_factory=lambda: ["22:00", "23:30"])
    credentials_path: str = os.path.join(BASE_DIR, "credentials", "credentials.json")
    token_path: str = os.path.join(BASE_DIR, "credentials", "token.json")
    log_path: str = os.path.join(BASE_DIR, "logs", "photo_enhancer.log")


DEFAULT_CONFIG = Config()
