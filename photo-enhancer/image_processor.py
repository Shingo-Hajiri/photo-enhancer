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
