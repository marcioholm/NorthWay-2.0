
from app import create_app
from models import EmailLog, User

app = create_app()

with app.app_context():
    print("--- Last 5 Email Logs ---")
    logs = EmailLog.query.order_by(EmailLog.created_at.desc()).limit(5).all()
    if not logs:
        print("No logs found.")
    for log in logs:
        print(f"[{log.created_at}] To: {log.email_to} | Subject: {log.subject} | Status: {log.status} | Error: {log.error_message}")
