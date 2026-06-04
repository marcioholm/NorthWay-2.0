"""
NorthWay CRM — Constantes globais
Centraliza todos os status, canais e tipos usados no sistema.
Importar daqui em vez de usar strings literais nos arquivos de rotas e models.

Uso:
    from constants import ProspectingStatus, IntentStatus, LeadChannel
    lead.prospecting_status = ProspectingStatus.NOVO
    if lead.intent_status in IntentStatus.HOT:
        ...
"""


class ProspectingStatus:
    """
    Status de PROCESSO — onde o lead está na cadência de automação.
    Não confundir com IntentStatus (intenção do lead).
    """
    NOVO                  = 'novo'
    EM_EXECUCAO           = 'em_execucao'
    AGUARDANDO_APROVACAO  = 'aguardando_aprovacao'
    PENDING_APPROVAL      = 'pending_approval'
    CONTATADO             = 'contatado'
    SENT                  = 'sent'
    APPROVED              = 'approved'
    RESPONDEU             = 'respondeu'
    INTERESSADO           = 'interessado'
    REUNIAO               = 'reuniao'
    CLIENTE               = 'cliente'
    SEM_RESPOSTA          = 'sem_resposta'
    PAUSADO               = 'pausado'
    DESCARTADO            = 'descartado'
    ERRO                  = 'erro'
    FAILED                = 'failed'

    BLOCKED = {
        EM_EXECUCAO, AGUARDANDO_APROVACAO, PENDING_APPROVAL,
        INTERESSADO, REUNIAO, CLIENTE,
        DESCARTADO, PAUSADO, ERRO, FAILED
    }

    APPROVAL_PENDING = {AGUARDANDO_APROVACAO, PENDING_APPROVAL}

    CONTACTED = {CONTATADO, SENT, APPROVED}

    TERMINAL = {CLIENTE, SEM_RESPOSTA, DESCARTADO, ERRO, FAILED}

    FUNNEL_ORDER = {
        NOVO: 0,
        EM_EXECUCAO: 1,
        AGUARDANDO_APROVACAO: 2,
        PENDING_APPROVAL: 2,
        CONTATADO: 3,
        SENT: 3,
        APPROVED: 3,
        RESPONDEU: 4,
        INTERESSADO: 5,
        REUNIAO: 6,
        CLIENTE: 7,
        SEM_RESPOSTA: 4,
        PAUSADO: 1,
        DESCARTADO: 0,
        ERRO: 0,
        FAILED: 0,
    }

    @classmethod
    def can_advance(cls, current: str, target: str) -> bool:
        return cls.FUNNEL_ORDER.get(target, 0) > cls.FUNNEL_ORDER.get(current, 0)


class IntentStatus:
    INTERESSADO       = 'interessado'
    PEDIU_PRECO       = 'pediu_preco'
    PEDIU_MATERIAL    = 'pediu_material'
    JA_TEM_AGENCIA    = 'ja_tem_agencia'
    AGORA_NAO         = 'agora_nao'
    SEM_INTERESSE     = 'sem_interesse'
    DUVIDA            = 'duvida'
    REUNIAO           = 'reuniao'
    CLIENTE           = 'cliente'

    HOT = {INTERESSADO, PEDIU_PRECO, PEDIU_MATERIAL, REUNIAO, CLIENTE}

    COLD = {SEM_INTERESSE, JA_TEM_AGENCIA}

    NEUTRAL = {AGORA_NAO, DUVIDA}

    ALL = HOT | COLD | NEUTRAL

    @classmethod
    def classify(cls, intent: str) -> str:
        if intent in cls.HOT:
            return 'hot'
        if intent in cls.COLD:
            return 'cold'
        return 'neutral'


class LeadChannel:
    WHATSAPP = 'whatsapp'
    EMAIL    = 'email'
    AMBOS    = 'ambos'

    ALL = {WHATSAPP, EMAIL, AMBOS}


class MessageStatus:
    PENDENTE              = 'pendente'
    AGUARDANDO_APROVACAO  = 'aguardando_aprovacao'
    PENDING_APPROVAL      = 'pending_approval'
    ENVIADA               = 'enviada'
    SENT                  = 'sent'
    REJEITADA             = 'rejeitada'
    ERRO                  = 'erro'
    FAILED                = 'failed'

    APPROVAL_PENDING = {AGUARDANDO_APROVACAO, PENDING_APPROVAL, PENDENTE}
    SENT_OK          = {ENVIADA, SENT}
    FAILED_STATES    = {ERRO, FAILED}


class MessageType:
    OUTBOUND = 'outbound'
    INBOUND  = 'inbound'


class CampaignStatus:
    RASCUNHO  = 'rascunho'
    ATIVA     = 'ativa'
    PAUSADA   = 'pausada'
    CONCLUIDA = 'concluida'

    ACTIVE_STATES = {ATIVA}


class AIProvider:
    OPENAI    = 'openai'
    ANTHROPIC = 'anthropic'
    GOOGLE    = 'google'
    GROQ      = 'groq'

    DEFAULT_MODELS = {
        OPENAI:    'gpt-4o-mini',
        ANTHROPIC: 'claude-haiku-4-5-20251001',
        GOOGLE:    'gemini-1.5-flash',
        GROQ:      'llama-3.3-70b-versatile',
    }

    @classmethod
    def from_model_name(cls, model_name: str) -> str:
        model = model_name.lower()
        if 'gpt' in model or 'o1' in model or 'o3' in model:
            return cls.OPENAI
        if 'claude' in model:
            return cls.ANTHROPIC
        if 'gemini' in model:
            return cls.GOOGLE
        if 'llama' in model or 'mixtral' in model or 'groq' in model:
            return cls.GROQ
        return cls.OPENAI


class IntegrationProvider:
    EVOLUTION_API      = 'evolution_api'
    WHATSAPP_BUSINESS  = 'whatsapp_business'
    SMTP               = 'smtp'
    SENDGRID           = 'sendgrid'


class NotificationType:
    LEAD_REPLIED   = 'lead_replied'
    CAMPAIGN_END   = 'campaign_end'
    LEAD_HOT       = 'lead_hot'
    WATCHDOG_RESET = 'watchdog_reset'
