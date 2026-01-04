import logging
from typing import Optional, Dict
try:
    from PIL import Image
    import imagehash
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    imagehash = None

def compute_avatar_phash(img: 'Image.Image', size: int = 64) -> Optional[str]:
    if not PIL_AVAILABLE or img is None:
        return None
    try:
        img = img.convert('RGB').resize((size, size), Image.LANCZOS)
        h = imagehash.phash(img)
        return str(h)
    except Exception as e:
        logging.debug(f"compute_avatar_phash failed: {e}")
        return None

def crop_avatar_roi(frame: 'Image.Image', roi: Dict[str, float]) -> Optional['Image.Image']:
    if not PIL_AVAILABLE or frame is None or not roi:
        return None
    try:
        w, h = frame.size
        x = max(0, min(w, int(w * roi.get('x', 0.0))))
        y = max(0, min(h, int(h * roi.get('y', 0.0))))
        cw = max(1, min(w - x, int(w * roi.get('w', 1.0))))
        ch = max(1, min(h - y, int(h * roi.get('h', 1.0))))
        return frame.crop((x, y, x + cw, y + ch))
    except Exception as e:
        logging.debug(f"crop_avatar_roi failed: {e}")
        return None

def compute_avatar_hash_from_frame(frame: 'Image.Image', roi: Dict[str, float], size: int = 64) -> Optional[str]:
    if not PIL_AVAILABLE or frame is None:
        return None
    try:
        cropped = crop_avatar_roi(frame, roi)
        if cropped is None:
            return None
        return compute_avatar_phash(cropped, size=size)
    except Exception as e:
        logging.debug(f"compute_avatar_hash_from_frame failed: {e}")
        return None
