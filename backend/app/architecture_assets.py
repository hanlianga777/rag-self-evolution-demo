"""Two local overview images, stored outside the repository."""

import os
from pathlib import Path


ASSET_DIR = Path(__file__).resolve().parents[1] / "data" / "architecture"
FORMATS = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}


def image_format(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None


def asset_path(slot: str) -> Path | None:
    for extension in FORMATS:
        path = ASSET_DIR / f"{slot}.{extension}"
        if path.is_file():
            return path
    return None


def save_asset(slot: str, data: bytes) -> Path:
    extension = image_format(data)
    if not extension or len(data) > 10 * 1024 * 1024:
        raise ValueError("仅支持不超过 10 MB 的 PNG、JPG 或 WebP 图片")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    staged = ASSET_DIR / f".{slot}.upload"
    staged.write_bytes(data)
    destination = ASSET_DIR / f"{slot}.{extension}"
    os.replace(staged, destination)
    for other in FORMATS:
        if other != extension:
            (ASSET_DIR / f"{slot}.{other}").unlink(missing_ok=True)
    return destination


def delete_asset(slot: str) -> None:
    for extension in FORMATS:
        (ASSET_DIR / f"{slot}.{extension}").unlink(missing_ok=True)
