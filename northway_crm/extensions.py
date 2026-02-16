try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:
    # Fallback if Limiter is not installed
    class Limiter:
        def __init__(self, *args, **kwargs): pass
        def init_app(self, app): pass
        def limit(self, *args, **kwargs):
            def decorator(f): return f
            return decorator
    def get_remote_address(): return "127.0.0.1"

# Initialize Limiter without app (Factory Pattern)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)
