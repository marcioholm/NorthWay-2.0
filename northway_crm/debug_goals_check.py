from app import create_app, db
from models import Goal, User
from datetime import datetime

app = create_app()

with app.app_context():
    print("--- DEBUGGING GOALS ---")
    year = datetime.now().year
    # Determine the first company id (assuming single tenant or first one)
    # Or just list all goals
    goals = Goal.query.all()
    print(f"Total Goals in DB: {len(goals)}")
    
    for g in goals:
        u_name = "Global"
        if g.user_id:
            u = User.query.get(g.user_id)
            u_name = u.name if u else f"User {g.user_id}"
            
        print(f"ID: {g.id} | Company: {g.company_id} | Year: {g.year} | Month: {g.month} | Type: {g.type} | Target: {g.target_amount} | MinNew: {g.min_new_sales} | User: {u_name}")
    print("-----------------------")
