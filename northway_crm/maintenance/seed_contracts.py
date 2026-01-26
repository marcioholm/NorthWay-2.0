from app import create_app
from models import db, ContractTemplate, Company, User

app = create_app()

with app.app_context():
    # Find a company (assuming first one for now, or all companies)
    companies = Company.query.all()
    
    default_content = """
    <h1>CONTRATO DE PRESTAÇÃO DE SERVIÇOS</h1>
    <p><strong>CONTRATANTE:</strong> {{cliente_nome}}, inscrito no CPF/CNPJ sob nº {{cliente_documento}}, com endereço em {{cliente_endereco}}.</p>
    <p><strong>CONTRATADA:</strong> {{empresa_nome}}, inscrita no CNPJ sob nº {{empresa_documento}}.</p>
    
    <p>Pelo presente instrumento particular, as partes acima qualificadas têm, entre si, justo e contratado o seguinte:</p>
    
    <h3>1. DO OBJETO</h3>
    <p>O presente contrato tem por objeto a prestação de serviços de consultoria e gestão estratégica pela CONTRATADA à CONTRATANTE.</p>
    
    <h3>2. DA VIGÊNCIA</h3>
    <p>Este contrato entra em vigor na data de sua assinatura ({{data_contrato}}) e terá validade por prazo indeterminado.</p>
    
    <p>____________________________________________________</p>
    <p>{{cliente_nome}}</p>
    <p>____________________________________________________</p>
    <p>{{responsavel_nome}} ({{empresa_nome}})</p>
    """
    
    for company in companies:
        exists = ContractTemplate.query.filter_by(company_id=company.id, name="Contrato Padrão de Serviços").first()
        if not exists:
            template = ContractTemplate(
                company_id=company.id,
                name="Contrato Padrão de Serviços",
                content=default_content,
                active=True
            )
            db.session.add(template)
            print(f"Template created for company {company.name}")
    
    db.session.commit()
    print("Seeding complete.")
