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
    compute_correction_strength,
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


def test_compute_correction_strength_returns_min_strength_for_bright_image():
    image = np.full((10, 10, 3), 220, dtype=np.uint8)
    strength = compute_correction_strength(image, DEFAULT_CONFIG)
    assert strength == DEFAULT_CONFIG.adaptive_min_strength


def test_compute_correction_strength_returns_full_strength_for_dark_image():
    image = np.full((10, 10, 3), 40, dtype=np.uint8)
    strength = compute_correction_strength(image, DEFAULT_CONFIG)
    assert strength == 1.0


def test_compute_correction_strength_interpolates_for_mid_brightness_image():
    image = np.full((10, 10, 3), 137, dtype=np.uint8)
    strength = compute_correction_strength(image, DEFAULT_CONFIG)
    assert DEFAULT_CONFIG.adaptive_min_strength < strength < 1.0


def test_enhance_image_alters_bright_image_less_than_dark_image():
    bright_image = np.full((30, 30, 3), 200, dtype=np.uint8)
    dark_image = np.full((30, 30, 3), 60, dtype=np.uint8)

    bright_result = enhance_image(bright_image, DEFAULT_CONFIG)
    dark_result = enhance_image(dark_image, DEFAULT_CONFIG)

    bright_delta = np.abs(bright_result.astype(np.int16) - bright_image.astype(np.int16)).mean()
    dark_delta = np.abs(dark_result.astype(np.int16) - dark_image.astype(np.int16)).mean()

    assert bright_delta < dark_delta


def test_enhance_image_alters_well_lit_photo_less_than_fixed_strength_pipeline():
    rng = np.random.default_rng(42)
    # Non-flat, warm-toned bright image: B lower than G/R (like a real bakery photo),
    # with per-pixel variation so auto_white_balance / auto_level are not no-ops.
    bright_image = np.clip(
        rng.normal(loc=[150, 175, 190], scale=10, size=(40, 40, 3)),
        0,
        255,
    ).astype(np.uint8)

    def fixed_strength_pipeline(image_bgr, config):
        result = auto_white_balance(image_bgr)
        result = auto_level(result)
        result = gamma_correct(result, config.gamma)
        result = boost_saturation(result, config.saturation_boost)
        result = apply_clahe(result, config.clahe_clip_limit)
        return result

    adaptive_result = enhance_image(bright_image, DEFAULT_CONFIG)
    fixed_result = fixed_strength_pipeline(bright_image, DEFAULT_CONFIG)

    adaptive_delta = np.abs(adaptive_result.astype(np.int16) - bright_image.astype(np.int16)).mean()
    fixed_delta = np.abs(fixed_result.astype(np.int16) - bright_image.astype(np.int16)).mean()

    assert adaptive_delta < fixed_delta


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
