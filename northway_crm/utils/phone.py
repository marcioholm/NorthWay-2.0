import re

def normalize_phone(phone):
    """
    Limpa caracteres não numéricos e remove sufixos como @s.whatsapp.net
    """
    if not phone:
        return ""
    # Remove suffix if any
    phone = str(phone).split('@')[0]
    # Remove non-numeric characters
    return re.sub(r'\D', '', phone)

def phone_variants(phone):
    """
    Gera array de variações (com/sem 55, com/sem 9º dígito).
    """
    base = normalize_phone(phone)
    if not base:
        return []

    # Se começar com 55 e tiver 12 ou 13 dígitos, retira o 55
    if base.startswith('55') and len(base) > 11:
        national = base[2:]
    else:
        national = base

    variants = set()
    variants.add(base) # original normalizado
    variants.add(national)
    variants.add('55' + national)

    # Se o número nacional tem DDD + 9 dígitos (11 dígitos, ex: 42999896358)
    if len(national) == 11 and national[2] == '9':
        # Versão sem o 9 (10 dígitos)
        without_9 = national[:2] + national[3:]
        variants.add(without_9)
        variants.add('55' + without_9)
    
    # Se o número nacional tem DDD + 8 dígitos (10 dígitos, ex: 429896358)
    elif len(national) == 10:
        # Versão com o 9
        with_9 = national[:2] + '9' + national[2:]
        variants.add(with_9)
        variants.add('55' + with_9)

    return list(variants)
