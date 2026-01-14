from app import create_app
from models import db, ContractTemplate, Company

app = create_app()

with app.app_context():
    company = Company.query.first()
    if company:
        # Check if attachment exists
        exists = ContractTemplate.query.filter_by(company_id=company.id, type='attachment', name="Anexo I - Tabela de Valores").first()
        
        if not exists:
            content = """
            <h3>ANEXO I - TABELA DE VALORES E CONDIÇÕES</h3>
            <p>Este anexo é parte integrante do contrato firmado em {{data_contrato}}.</p>
            <table border="1" cellpadding="5" cellspacing="0" style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="background-color: #f0f0f0;"><strong>Descrição</strong></td>
                    <td style="background-color: #f0f0f0;"><strong>Valor</strong></td>
                </tr>
                <tr>
                    <td>Valor de Implantação</td>
                    <td>R$ {{valor_implantacao}}</td>
                </tr>
                <tr>
                    <td>Mensalidade</td>
                    <td>R$ {{valor_parcela}}</td>
                </tr>
                <tr>
                    <td>Total do Contrato (12 meses)</td>
                    <td>R$ {{valor_total_contrato}} (Estimado)</td>
                </tr>
            </table>
            <p><strong>Condições de Pagamento:</strong> {{forma_pagamento}}, com vencimento todo dia {{dia_vencimento}}.</p>
            """
            
            attachment = ContractTemplate(
                company_id=company.id,
                name="Anexo I - Tabela de Valores",
                type='attachment',
                content=content,
                active=True
            )
            db.session.add(attachment)
            db.session.commit()
            print(f"Attachment seeded for {company.name}")
        else:
            print("Attachment already exists.")
    else:
        print("No company found.")
