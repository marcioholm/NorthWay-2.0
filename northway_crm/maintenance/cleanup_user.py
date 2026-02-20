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
                    # Cancel Asaas Subscription if exists
                    if company.subscription_id:
                        from services.asaas_service import delete_subscription
                        try:
                            delete_subscription(company.subscription_id)
                            print(f"✅ Subscription {company.subscription_id} cancelled for company '{company.name}'.")
                        except Exception as asaas_e:
                            print(f"⚠️ Failed to cancel Asaas subscription: {asaas_e}")

                    db.session.delete(company)
                    print(f"Company '{company.name}' deleted (no other users).")
                else:
                    print(f"Company '{company.name}' kept (has {other_users} other users).")
        
        db.session.commit()
        print("Done.")
    else:
        print(f"User {email} not found.")
