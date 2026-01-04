import pytest
try:
    from PIL import Image
    from core.vision.avatar_hash import compute_avatar_phash, crop_avatar_roi, compute_avatar_hash_from_frame
except ImportError:
    pytest.skip("Pillow/imagehash not available", allow_module_level=True)

def make_test_img(size=(64, 64), rect=None):
    img = Image.new('RGB', size, 'white')
    if rect:
        x, y, w, h = rect
        for i in range(x, x + w):
            for j in range(y, y + h):
                img.putpixel((i, j), (0, 0, 0))
    return img

def test_phash_identical():
    img1 = make_test_img(rect=(16, 16, 32, 32))
    img2 = make_test_img(rect=(16, 16, 32, 32))
    h1 = compute_avatar_phash(img1)
    h2 = compute_avatar_phash(img2)
    assert h1 == h2

def test_phash_different():
    img1 = make_test_img(rect=(16, 16, 32, 32))
    img3 = make_test_img(rect=(24, 24, 32, 32))
    h1 = compute_avatar_phash(img1)
    h3 = compute_avatar_phash(img3)
    assert h1 != h3

def test_crop_avatar_roi():
    frame = Image.new('RGB', (200, 100), 'white')
    roi = {"x":0.35,"y":0.20,"w":0.30,"h":0.55}
    cropped = crop_avatar_roi(frame, roi)
    assert cropped.size[0] > 0 and cropped.size[1] > 0

def test_compute_avatar_hash_from_frame():
    frame = make_test_img(rect=(10, 10, 20, 20))
    roi = {"x":0.1,"y":0.1,"w":0.5,"h":0.5}
    h = compute_avatar_hash_from_frame(frame, roi)
    assert isinstance(h, str) or h is None
