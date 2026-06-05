import logging

logger = logging.getLogger(__name__)

SEGMENT_KEYWORDS = {
    'assessoria de marketing': [
        'marketing', 'agencia', 'agência', 'social media', 'midia social', 'mídia social',
        'trafego pago', 'tráfego pago', 'publicidade', 'propaganda', 'branding',
        'comunicacao', 'comunicação', 'marketing digital', 'midia digital', 'mídia digital',
        'seo', 'gestao de trafego', 'gestão de tráfego', 'geracao de lead', 'geração de lead',
        'inbound', 'outbound', 'performance', 'growth', 'conteudo', 'conteúdo',
        'criacao de site', 'criação de site', 'loja virtual', 'ecommerce', 'e-commerce',
        'anuncio', 'anúncio', 'impulsionar', 'redes sociais'
    ],
    'energia solar': [
        'energia solar', 'solar', 'fotovoltaica', 'fotovoltaico', 'placas solares',
        'painel solar', 'inversor solar', 'energia limpa', 'energia renovavel',
        'energia renovável', 'sistema solar', 'geracao solar', 'geração solar',
        'usina solar', 'kit solar', 'instalacao solar', 'instalação solar',
        'telhado solar', 'energia sustentavel', 'energia sustentável'
    ],
    'clinica estética': [
        'estética', 'estetica', 'clinica estética', 'clinica estetica', 'harmonização',
        'harmonizacao', 'botox', 'dermatologia', 'esteticista', 'cosmiatria',
        'tratamento estetico', 'tratamento estético', 'procedimento estetico',
        'procedimento estético', 'laser', 'depilacao', 'depilação', 'pele', 'beleza',
        'beleza estetica', 'beleza estética', 'corpo', 'massagem', 'estetica corporal',
        'estética corporal', 'estetica facial', 'estética facial', 'preenchimento',
        'bioestimulador', 'toxina botulínica', 'toxina botulinica', 'lipocavitação',
        'lipocavitacao', 'carboxiterapia', 'corporal', 'facial', 'emagrecimento',
        'drenagem linfatica', 'drenagem linfática'
    ],
    'academia': [
        'academia', 'fitness', 'musculação', 'musculacao', 'treinamento', 'crossfit',
        'studio', 'ginastica', 'ginástica', 'personal trainer', 'treino funcional',
        'funcional', 'pilates', 'yoga', 'ioga', 'spinning', 'bike indoor', 'jit',
        'arte marcial', 'luta', 'judo', 'jiu-jitsu', 'jiu jitsu', 'karate', 'karatê',
        'capoeira', 'dança', 'danca', 'natacao', 'natação', 'hidroginastica',
        'hidroginástica', 'saude', 'saúde', 'bem-estar', 'esporte', 'atividade fisica',
        'atividade física', 'pesos', 'halterofilismo', 'cross training', 'muay thai',
        'boxe', 'alongamento', 'musculacao feminina', 'musculação feminina'
    ],
    'farmacia': [
        'farmácia', 'farmacia', 'drogaria', 'medicamentos', 'farma', 'drogasil',
        'drogasil', 'pague menos', 'extrafarma', 'saude', 'farmácia de manipulação',
        'farmacia de manipulacao', 'manipulação', 'manipulacao', 'remedio', 'remédio',
        'farmacêutico', 'farmaceutico', 'produtos farmacêuticos', 'produtos farmaceuticos',
        'cosmeticos', 'cosméticos', 'perfumaria', 'higiene', 'bem-estar', 'suplemento',
        'genérico', 'generico', 'farmacia popular', 'farmácia popular', 'drogamed',
        'drogaria sao paulo', 'drogaria são paulo', 'panvel'
    ],
}

DEFAULT_KEYWORDS = []


def build_lead_text(place):
    parts = [
        place.get('name', ''),
        place.get('category', ''),
        place.get('description', ''),
        place.get('website', ''),
        place.get('types', []),
    ]
    text_parts = []
    for p in parts:
        if isinstance(p, list):
            text_parts.extend(str(x) for x in p)
        elif p:
            text_parts.append(str(p))
    return ' '.join(text_parts).lower()


def is_segment_match(place, target_segment):
    if not target_segment:
        return True

    text = build_lead_text(place)
    segment = target_segment.strip().lower()

    keywords = SEGMENT_KEYWORDS.get(segment, [segment])

    return any(keyword in text for keyword in keywords)
