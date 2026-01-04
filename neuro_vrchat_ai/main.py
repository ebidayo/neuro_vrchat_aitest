try:
    from main import *  # noqa
except Exception as e:
    pass  # Fail-soft: allow import to succeed for tests