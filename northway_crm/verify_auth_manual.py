import requests
import sys

# Since this is a Flask app using templates/sessions, verifying headless is a bit tricky without a proper test client or selenium.
# However, we can use the python requests `Session` to simulate a browser.

# We will try to register a new user and see if it succeeds.
# Since we need a unique email, we'll generate one.

import random
import string

def random_string(length=10):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

email = f"test_{random_string()}@northway.com"
password = "TestPassword123!"
name = f"Test User {random_string(5)}"
company_name = f"Test Company {random_string(5)}"

print(f"Attempting to register with:")
print(f"Email: {email}")
print(f"Password: {password}")

# Local server URL
BASE_URL = "http://127.0.0.1:5000"

# Note: The server must be running for this to work.
# I will output the instructions to run the server if this fails, or I might try to run the server in background.
# But for now, I'll assume I can't easily hit the running server if I haven't started it. 
# Wait, I haven't started the server yet in this session.
# I should probably start the server in background.

print("\n(Note: This script assumes the server is running on port 5000. If not, it will fail.)")
