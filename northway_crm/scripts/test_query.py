
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Transaction

def test():
    with app.app_context():
        print("Querying one transaction...")
        try:
            tx = Transaction.query.first()
            print(f"Got: {tx}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test()
