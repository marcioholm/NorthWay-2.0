import pytest
from services.crepi_service import calcular_nivel


@pytest.mark.parametrize("p,i,nivel,contingencia", [
    (0, 8, 'nao_avaliado', False),
    (5, 0, 'nao_avaliado', False),
    (3, 4, 'baixo', False),     # 12
    (4, 4, 'medio', False),     # 16
    (5, 8, 'medio', False),     # 40 continua médio
    (6, 7, 'critico', False),   # 42
    (10, 4, 'medio', False),    # certo, mas moderado
    (2, 10, 'medio', True),     # catastrófico pouco provável -> plano B
    (1, 9, 'medio', True),
    (3, 9, 'critico', False),   # catastrófico com P >= 3
    (3, 10, 'critico', False),
])
def test_calcular_nivel(p, i, nivel, contingencia):
    n, score, c = calcular_nivel(p, i)
    assert n == nivel
    assert score == p * i
    assert c is contingencia


def test_calcular_nivel_limita_valores_fora_da_escala():
    n, score, _ = calcular_nivel(15, '3')
    assert score == 30 and n == 'medio'
    assert calcular_nivel(None, 'x')[0] == 'nao_avaliado'


def test_save_e_get_premissas_com_plano_de_tratamento(auth_client, app):
    from models import db, Client, CREPIDiagnostico
    client, user, company = auth_client
    with app.app_context():
        target = Client(company_id=company.id, account_manager_id=user.id, name="Cliente CREPI", email="crepi@example.com")
        db.session.add(target)
        db.session.flush()
        diag = CREPIDiagnostico(client_id=target.id, projeto="Projeto teste")
        db.session.add(diag)
        db.session.commit()
        client_id, diag_id = target.id, diag.id

    payload = {"premissas": [
        {"nome": "WhatsApp banido", "categoria": "Operacional", "probabilidade": 2, "impacto": 10,
         "decisao": "Ter número reserva configurado",  # nome antigo do campo continua aceito
         "responsavel": "Adriana", "prazo": "2026-11-15", "gatilho": "Aviso de restrição da Meta",
         "status": "em_tratamento", "probabilidade_residual": 1, "impacto_residual": 6},
        {"nome": "Agenda de corte", "probabilidade": 7, "impacto": 7, "status": "invalido"},
    ]}
    r = client.post(f"/api/clients/{client_id}/crepi/{diag_id}/premises/save", json=payload)
    assert r.status_code == 200 and r.get_json()["success"]

    data = client.get(f"/crepi/{diag_id}").get_json()["data"]["premissas"]
    a, b = data
    assert a["nivel"] == "medio" and a["contingencia_obrigatoria"] is True
    assert a["decisao_consultor"] == "Ter número reserva configurado"
    assert a["responsavel"] == "Adriana" and a["prazo"] == "2026-11-15"
    assert a["status"] == "em_tratamento"
    assert a["score_residual"] == 6 and a["nivel_residual"] == "baixo"
    assert b["nivel"] == "critico" and b["status"] == "aberta"
    assert b["score_residual"] is None

    lst = client.get(f"/api/clients/{client_id}/crepi/list").get_json()["data"][0]
    assert lst["critical_count"] == 1 and lst["medium_count"] == 1
