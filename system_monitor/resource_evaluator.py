def evaluate_resource_state(metrics):
    """
    Pure function. Input: metrics dict with keys 'cpu', 'ram', 'gpu', 'vram' (0.0-1.0 or None)
    Output: dict with 'danger' (0.0-1.0), 'dominant' (cpu|ram|gpu|vram|None)
    Deterministic, clamps, fail-soft.
    """
    def clamp(x):
        try:
            return max(0.0, min(1.0, float(x)))
        except Exception:
            return 0.0
    vals = {k: clamp(metrics.get(k)) if metrics.get(k) is not None else 0.0 for k in ('cpu','ram','gpu','vram')}
    # Danger: max(cpu, ram*0.9, gpu, vram)
    danger = max(vals['cpu'], vals['ram']*0.9, vals['gpu'], vals['vram'])
    # Dominant: which is highest (if all 0, None)
    dominant = None
    maxval = 0.0
    for k in ('cpu','ram','gpu','vram'):
        if vals[k] > maxval:
            maxval = vals[k]
            dominant = k
    if maxval == 0.0:
        dominant = None
    return {'danger': clamp(danger), 'dominant': dominant}
