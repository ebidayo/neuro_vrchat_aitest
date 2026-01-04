from tts_style_bert_vits2 import prosody_from_scalars

import hashlib
def maybe_prefetch_next_chunk(tts, chunks, idx, scalars, cfg, logger):
    if not (cfg.get('tts.enabled', False) and cfg.get('tts.prefetch', False)):
        return
    if not (tts and hasattr(tts, 'is_available') and tts.is_available()):
        return
    if idx+1 >= len(chunks):
        return
    next_chunk = chunks[idx+1]
    chunk_id = getattr(next_chunk, 'id', None)
    if not chunk_id:
        text = getattr(next_chunk, 'text', None) or (next_chunk.get('text','') if isinstance(next_chunk, dict) else '')
        chunk_id = hashlib.sha1((text+":"+str(idx+1)).encode("utf-8")).hexdigest()[:12]
    try:
        tts.prefetch(getattr(next_chunk, 'text', None) or (next_chunk.get('text','') if isinstance(next_chunk, dict) else ''), prosody_from_scalars(scalars), chunk_id=chunk_id)
    except Exception:
        pass
