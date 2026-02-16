from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize Limiter without app (Factory Pattern)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)
