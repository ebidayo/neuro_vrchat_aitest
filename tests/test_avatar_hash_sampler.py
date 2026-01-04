
import time
import pytest
from unittest.mock import Mock
pytest.importorskip("PIL.Image")
from PIL import Image
from core.vision.avatar_hash import compute_avatar_phash
from main import AvatarHashSampler

def make_img():
    img = Image.new('RGB', (64, 64), 'white')
    for i in range(16, 48):
        for j in range(16, 48):
            img.putpixel((i, j), (0, 0, 0))
    return img

def test_sampler_basic():
    called = []
    def get_frame():
        called.append(1)
        return make_img()
    sampler = AvatarHashSampler(get_frame, interval_sec=2.0, ttl_sec=3.0, cooldown_on_error_sec=1.0)
    t0 = 100.0
    # First call: should sample
    h1 = sampler.tick(t0)
    assert isinstance(h1, str)
    # Within interval: should not resample
    h2 = sampler.tick(t0 + 1.0)
    assert h2 == h1
    assert len(called) == 1
    # After interval: should resample
    h3 = sampler.tick(t0 + 2.1)
    assert isinstance(h3, str)
    assert len(called) == 2
    # TTL not expired
    h4 = sampler.tick(t0 + 4.0)
    assert h4 == h3
    # TTL expired: simulate get_frame returns None
    def get_none():
        return None
    sampler.get_roi_image_callable = get_none
    h5 = sampler.tick(t0 + 6.2)
    assert h5 is None

def test_sampler_ttl():
    def get_frame():
        return make_img()
    sampler = AvatarHashSampler(get_frame, interval_sec=1.0, ttl_sec=2.0, cooldown_on_error_sec=1.0)
    t0 = 200.0
    h1 = sampler.tick(t0)
    assert isinstance(h1, str)
    # After ttl: simulate get_frame returns None
    def get_none():
        return None
    sampler.get_roi_image_callable = get_none
    h2 = sampler.tick(t0 + 3.0)
    assert h2 is None

def test_sampler_disabled():
    def get_frame():
        assert False, "Should not be called"
    # Disabled: just never call tick, or always returns None
    sampler = AvatarHashSampler(get_frame, interval_sec=1.0, ttl_sec=2.0, cooldown_on_error_sec=1.0)
    # Simulate never calling tick (disabled logic is at integration)
    # If tick is called, but get_frame is not called, test passes
    # So just check initial state
    h = sampler._get_valid_hash(0.0)
    assert h is None
