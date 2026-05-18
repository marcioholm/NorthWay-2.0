
import os
import sys
from sqlalchemy import text

# Add the project root to sys.path
sys.path.append('/Users/Marci.Holm/Applications/NorthWay-2.0/northway_crm')

from app import create_app
from models import db, User, Company

app = create_app()

with app.app_context():
    print("--- User & Company Audit ---")
    users = User.query.all()
    for u in users:
        company_name = u.company.name if u.company else "NO COMPANY"
        print(f"ID: {u.id} | Name: {u.name} | Email: {u.email} | Company: {company_name} (ID: {u.company_id})")
    print("---------------------------")
