import os

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError as e:
    raise ImportError("Flask-Limiter is required for rate limiting but is not installed. Please install 'flask-limiter'.") from e

try:
    from flask_wtf.csrf import CSRFProtect
except ImportError as e:
    raise ImportError("Flask-WTF is required for CSRF protection but is not installed. Please install 'Flask-WTF'.") from e

storage_uri = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["5000 per day", "1000 per hour"],
    storage_uri=storage_uri,
    strategy="fixed-window"
)

csrf = CSRFProtect()
