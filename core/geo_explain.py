"""Lightweight geo explanation utilities for ALERT messages.

Provides a small set of coastal reference points for Japan and a simple
haversine-based estimator to produce distance-based explanatory chunks.
"""
import math
from typing import List, Tuple, Dict, Any

# A modest set of representative coastal points in Japan (label, lat, lon)
COAST_POINTS_JP: List[Tuple[str, float, float]] = [
    ("Choshi", 35.7219, 140.8640),
    ("Shimizu", 35.0164, 138.4911),
    ("Nagoya Port", 35.1376, 136.9054),
    ("Osaka Bay", 34.6863, 135.5200),
    ("Kochi Coast", 33.5597, 133.5311),
    ("Kagoshima Port", 31.5966, 130.5571),
    ("Hakodate", 41.7687, 140.7288),
    ("Sendai Coast", 38.2682, 140.8694),
    ("Chiba Coast", 35.6074, 140.1069),
    ("Wakayama", 34.2257, 135.1675),
    ("Niigata Coast", 37.9162, 139.0364),
    ("Naha", 26.2124, 127.6792),
]

R_EARTH_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two lat/lon points in kilometers."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
    return R_EARTH_KM * c


def estimate_coast_distance_km(user_lat: float, user_lon: float) -> float:
    """Estimate distance to nearest coast point from COAST_POINTS_JP (km)."""
    best = None
    for label, lat, lon in COAST_POINTS_JP:
        d = haversine_km(user_lat, user_lon, lat, lon)
        if best is None or d < best:
            best = d
    return float(best) if best is not None else float('inf')


def pick_coast_distance_km(user_loc: Dict[str, Any], lat: float, lon: float) -> tuple[float, str]:
    """Return (distance_km, src) where src is 'override' or 'estimate' or 'none'.

    Prefers explicit user_loc['coast_distance_km'] when set; otherwise falls back to estimate using lat/lon.
    """
    if user_loc is None:
        return (float('inf'), 'none')
    cd = user_loc.get('coast_distance_km', None)
    if cd is not None:
        try:
            return (float(cd), 'override')
        except Exception:
            return (float('inf'), 'none')
    # fall back to estimate if lat/lon provided
    if 'lat' in user_loc and 'lon' in user_loc:
        try:
            d = estimate_coast_distance_km(float(user_loc['lat']), float(user_loc['lon']))
            return (float(d), 'estimate')
        except Exception:
            return (float('inf'), 'none')
    return (float('inf'), 'none')


def build_geo_chunks_for_alert(ev: Dict[str, Any], cfg_user_loc: Dict[str, Any], confidence: float, glitch: float) -> List[Dict[str, Any]]:
    """Return a list of v1.2 speech_plan chunks (dicts) describing distance/terrain advice for tsunami alerts.

    Minimal behavior:
    - If ev['type'] != 'tsunami' and severity < 9: return []
    - If cfg_user_loc contains coast_distance_km, use it with higher confidence
    - Else if lat/lon present, estimate distance using COAST_POINTS_JP and haversine
    - Else return a fallback general advice (non-distance-specific)

    Each chunk is of the form {id,type,text,pause_ms,osc,confidence_tag}
    osc should keep N_State=ALERT and N_Look/N_Arousal tuned for urgency.
    """
    typ = (ev or {}).get('type', '')
    severity = int((ev or {}).get('severity', 0))
    if typ != 'tsunami' and severity < 9:
        return []

    user_loc = cfg_user_loc or {}
    # base OSC urgency
    n_state = "ALERT"
    n_arousal = max(confidence, 0.85)
    n_valence = min(0.0, -0.35)
    n_look = 0.95

    chunks = []
    cid = 1

    # Use explicit coast distance if provided
    coast_dist = user_loc.get('coast_distance_km')
    used_mode = 'explicit' if coast_dist is not None else 'est'

    if coast_dist is None and 'lat' in user_loc and 'lon' in user_loc:
        try:
            lat = float(user_loc.get('lat'))
            lon = float(user_loc.get('lon'))
            coast_dist = estimate_coast_distance_km(lat, lon)
            used_mode = 'estimate'
        except Exception:
            coast_dist = None
            used_mode = 'none'

    if coast_dist is not None and coast_dist != float('inf'):
        # produce phrasing with assumptions
        d = float(coast_dist)
        # action suggestion depends on distance
        if d <= 5.0:
            action_phrase = "海が近いようです。今すぐ高い場所へ移動してください。"
        elif d <= 20.0:
            action_phrase = "海から離れることを検討してください。安全な高台へ移動が望ましいです。"
        else:
            action_phrase = "すぐに海から離れる必要はないかもしれませんが、続報を確認してください。"

        chunks.append({
            'id': f'g{cid}',
            'type': 'say',
            'text': f"（仮定だけど）海岸までだいたい {d:.0f}km くらい。",
            'pause_ms': 160,
            'osc': {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": 0.45, "N_Look": n_look},
            'confidence_tag': ('med' if used_mode == 'explicit' else 'low'),
        })
        cid += 1
        chunks.append({
            'id': f'g{cid}',
            'type': 'say',
            'text': action_phrase,
            'pause_ms': 160,
            'osc': {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": 0.6, "N_Look": n_look},
            'confidence_tag': ('med' if used_mode == 'explicit' else 'low'),
        })
        cid += 1
        chunks.append({
            'id': f'g{cid}',
            'type': 'disclaimer',
            'text': "これは代表点からの概算です。正確な位置で変わります。",
            'pause_ms': 180,
            'osc': {"N_State": n_state, "N_Arousal": 0.4, "N_Valence": n_valence, "N_Gesture": 0.2, "N_Look": n_look},
            'confidence_tag': 'low',
        })
        cid += 1
        return chunks

    # fallback when no location info: general guidance with disclaimer
    chunks.append({
        'id': f'g{cid}',
        'type': 'say',
        'text': "場所が分からないので一般論をお伝えします。",
        'pause_ms': 140,
        'osc': {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": 0.45, "N_Look": n_look},
        'confidence_tag': 'low',
    })
    cid += 1
    chunks.append({
        'id': f'g{cid}',
        'type': 'say',
        'text': "海が近い場合は、すぐに高い場所へ移動してください。",
        'pause_ms': 160,
        'osc': {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": 0.6, "N_Look": n_look},
        'confidence_tag': 'low',
    })
    cid += 1
    chunks.append({
        'id': f'g{cid}',
        'type': 'disclaimer',
        'text': "これは一般的な助言です。公式の情報を確認してください。",
        'pause_ms': 180,
        'osc': {"N_State": n_state, "N_Arousal": 0.4, "N_Valence": n_valence, "N_Gesture": 0.2, "N_Look": n_look},
        'confidence_tag': 'low',
    })
    return chunks