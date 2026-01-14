from app import create_app
from models import db, User, Company, Pipeline, PipelineStage, ROLE_ADMIN, LEAD_STATUS_NEW, LEAD_STATUS_IN_PROGRESS, LEAD_STATUS_WON
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # 1. Company
    company = Company.query.first()
    if not company:
        company = Company(name="Northway", primary_color="#fa0102", secondary_color="#111827")
        db.session.add(company)
        db.session.commit()
        print(f"Created default company: {company.name}")
    
    # 2. Pipeline
    pipeline = Pipeline.query.first()
    if not pipeline:
        pipeline = Pipeline(name="Funil Padrão", company_id=company.id)
        db.session.add(pipeline)
        db.session.commit()
        
        # Stages
        stages = [
            ("Descoberta", 1),
            ("Qualificação", 2),
            ("Proposta", 3),
            ("Negociação", 4),
            ("Fechamento", 5)
        ]
        for name, order in stages:
            stage = PipelineStage(name=name, order=order, pipeline_id=pipeline.id, company_id=company.id)
            db.session.add(stage)
        db.session.commit()
        print(f"Created default pipeline: {pipeline.name}")

    # 3. User
    user = User.query.filter_by(email="admin@northway.com").first()
    if not user:
        user = User(
            name="Admin User",
            email="admin@northway.com",
            password_hash=generate_password_hash("123456"),
            role=ROLE_ADMIN,
            company_id=company.id
        )
        db.session.add(user)
        db.session.commit()
        print("User admin@northway.com created.")
    else:
        user.password_hash = generate_password_hash("123456")
        db.session.commit()
        print("User admin@northway.com updated.")

    # 4. Associate User with All Pipelines
    all_pipelines = Pipeline.query.filter_by(company_id=company.id).all()
    for p in all_pipelines:
        if p not in user.allowed_pipelines:
            user.allowed_pipelines.append(p)
    
    db.session.commit()
    print("Admin user associated with all pipelines.")
