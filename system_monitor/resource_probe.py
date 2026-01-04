import psutil
import subprocess
import logging

def probe_resources():
    """
    Returns:
        dict: {
            'cpu': 0.0-1.0 or None,
            'ram': 0.0-1.0 or None,
            'gpu': 0.0-1.0 or None,
            'vram': 0.0-1.0 or None,
        }
    Fail-soft: all exceptions are caught, None returned for failed metrics.
    """
    result = {'cpu': None, 'ram': None, 'gpu': None, 'vram': None}
    try:
        result['cpu'] = psutil.cpu_percent(interval=0.1) / 100.0
    except Exception as e:
        logging.debug(f"CPU probe failed: {e}")
    try:
        result['ram'] = psutil.virtual_memory().percent / 100.0
    except Exception as e:
        logging.debug(f"RAM probe failed: {e}")
    # Try nvidia-smi for GPU/VRAM
    try:
        smi = subprocess.run([
            'nvidia-smi',
            '--query-gpu=utilization.gpu,memory.used,memory.total',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, timeout=1)
        if smi.returncode == 0:
            line = smi.stdout.strip().split('\n')[0]
            gpu_util, mem_used, mem_total = [float(x) for x in line.split(',')]
            result['gpu'] = gpu_util / 100.0
            if mem_total > 0:
                result['vram'] = mem_used / mem_total
    except Exception as e:
        logging.debug(f"nvidia-smi probe failed: {e}")
    return result
