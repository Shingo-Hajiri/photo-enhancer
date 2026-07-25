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
    assert DEFAULT_CONFIG.adaptive_bright_threshold == 165.0
    assert DEFAULT_CONFIG.adaptive_dark_threshold == 110.0
    assert DEFAULT_CONFIG.adaptive_min_strength == 0.15


def test_paths_point_inside_photo_enhancer_directory():
    assert DEFAULT_CONFIG.credentials_path.endswith("credentials/credentials.json")
    assert DEFAULT_CONFIG.token_path.endswith("credentials/token.json")
    assert DEFAULT_CONFIG.log_path.endswith("logs/photo_enhancer.log")
