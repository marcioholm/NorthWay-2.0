from app import create_app, db
from models import Task

app = create_app()
with app.app_context():
    tasks = Task.query.filter(Task.title.like('%Reconexão%')).all()
    if tasks:
        print(f"Found {len(tasks)} recovery tasks:")
        for t in tasks:
            print(f"- {t.title} (Lead ID: {t.lead_id}, Assigned: {t.assigned_to_id}, Status: {t.status})")
    else:
        print("No recovery tasks found.")
