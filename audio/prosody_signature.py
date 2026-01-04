def prosody_signature(valence, interest, arousal, digits=2):
    """
    Deterministically stringify prosody params for cache keying.
    Rounds to 'digits' decimal places, returns a string.
    """
    try:
        v = round(float(valence), digits)
        i = round(float(interest), digits)
        a = round(float(arousal), digits)
        return f"v{v}_i{i}_a{a}"
    except Exception:
        return "v0_i0_a0"