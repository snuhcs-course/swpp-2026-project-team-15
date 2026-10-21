"""US02/04: the published synthetic input selects the documented original fixture."""

from app.config import SERVER_DIR
from app.vision.providers import FixtureVisionProvider
from app.vision.service import to_candidates


def test_synthetic_demo_input_selects_original_garlic_and_egg_fixture():
    image = SERVER_DIR.parent / "server/fixtures/demo/mock-photo.png"
    assert image.read_bytes().startswith(b"\x89PNG")
    provider = FixtureVisionProvider(SERVER_DIR / "fixtures/vision")
    candidates = to_candidates(provider.detect(image.read_bytes(), "image/png"))
    assert {row.name for row in candidates} == {"다진마늘", "달걀"}
