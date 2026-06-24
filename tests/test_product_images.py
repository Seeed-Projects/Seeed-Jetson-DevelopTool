from __future__ import annotations

import json
from pathlib import Path

import pytest

PRODUCT_IMAGES_FILE = (
    Path(__file__).resolve().parents[1]
    / "seeed_jetson_develop"
    / "data"
    / "product_images.json"
)


@pytest.fixture
def product_images() -> dict[str, dict]:
    return json.loads(PRODUCT_IMAGES_FILE.read_text(encoding="utf-8"))


def test_all_local_images_exist(product_images: dict[str, dict]) -> None:
    """每个 product 的 local_image 都必须真实存在，避免网络不好时图片空白。"""
    repo_root = PRODUCT_IMAGES_FILE.resolve().parents[2]
    missing: list[tuple[str, str]] = []
    for key, info in product_images.items():
        local_image = info.get("local_image", "")
        if not local_image:
            continue
        image_path = repo_root / local_image
        if not image_path.exists():
            missing.append((key, local_image))

    assert not missing, f"missing local images: {missing}"
