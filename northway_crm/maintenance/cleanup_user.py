from app import create_app
from models import db, User, Company

app = create_app()

with app.app_context():
    email = "marciogholmm@gmail.com"
    user = User.query.filter_by(email=email).first()
    
    if user:
        print(f"Found user: {user.name} ({user.email})")
        company_id = user.company_id
        
        # Delete User
        db.session.delete(user)
        print(f"User {email} deleted.")
        
        if company_id:
            company = Company.query.get(company_id)
            if company:
                # Check if other users are in this company
                other_users = User.query.filter(User.company_id == company_id, User.id != user.id).count()
                if other_users == 0:
                    db.session.delete(company)
                    print(f"Company '{company.name}' deleted (no other users).")
                else:
                    print(f"Company '{company.name}' kept (has {other_users} other users).")
        
        db.session.commit()
        print("Done.")
    else:
        print(f"User {email} not found.")
