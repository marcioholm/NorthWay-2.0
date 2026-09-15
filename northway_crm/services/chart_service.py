"""Calendar buckets shared by SQL aggregation and dashboard labels."""
from datetime import datetime, timedelta
from sqlalchemy import cast, Integer, String, func
from models import db, Lead, Client, get_now_br

SPANS = {'monthly': 1, 'bimonthly': 2, 'quarterly': 3,
         'semiannual': 6, 'annual': 12, 'all_time': 1}
WINDOWS = {'today': 0, 'last_7_days': 7, 'daily': 30, 'weekly': 84,
           'monthly': 365, 'bimonthly': 730, 'quarterly': 730,
           'semiannual': 1095, 'annual': 1825}


def bucket_key(value, period):
    if period == 'today':
        return value.strftime('%Y-%m-%d-%H'), value.strftime('%H:00')
    if period in ('daily', 'last_7_days'):
        return value.strftime('%Y-%m-%d'), value.strftime('%d/%m')
    if period == 'weekly':
        start = value - timedelta(days=value.weekday())
        return start.strftime('%Y-%m-%d'), start.strftime('%d/%m/%Y')
    span = SPANS[period]
    month = ((value.month - 1) // span) * span + 1
    label = str(value.year) if span == 12 else f'{month:02d}/{value.year}'
    return f'{value.year:04d}-{month:02d}', label


def sql_bucket(column, period):
    sqlite = db.engine.dialect.name == 'sqlite'
    if period in SPANS:
        year = cast(func.extract('year', column), Integer)
        month = cast(func.floor((func.extract('month', column) - 1) / SPANS[period]), Integer) * SPANS[period] + 1
        if sqlite:
            return func.printf('%04d-%02d', year, month)
        return func.concat(cast(year, String), '-', func.lpad(cast(month, String), 2, '0'))
    if period == 'weekly':
        return (func.date(column, 'weekday 0', '-6 days') if sqlite else
                func.to_char(func.date_trunc('week', column), 'YYYY-MM-DD'))
    fmt = '%Y-%m-%d-%H' if period == 'today' else '%Y-%m-%d'
    return func.strftime(fmt, column) if sqlite else func.to_char(column, 'YYYY-MM-DD-HH24' if period == 'today' else 'YYYY-MM-DD')


def chart_data(company_id, period):
    if period not in WINDOWS and period != 'all_time':
        raise ValueError('Período inválido')
    now = get_now_br()
    if period == 'all_time':
        oldest_lead = db.session.query(func.min(Lead.created_at)).filter_by(company_id=company_id).scalar()
        oldest_client = db.session.query(func.min(Client.start_date)).filter_by(company_id=company_id).scalar()
        candidates = [v for v in (oldest_lead, datetime.combine(oldest_client, datetime.min.time()) if oldest_client else None) if v]
        start = min(candidates) if candidates else now
    else:
        start = (now - timedelta(days=WINDOWS[period])).replace(hour=0, minute=0, second=0, microsecond=0)
    buckets = {}
    cursor = start
    while cursor <= now:
        key, label = bucket_key(cursor, period)
        buckets.setdefault(key, {'label': label, 'leads': 0, 'sales': 0})
        cursor += timedelta(hours=1) if period == 'today' else timedelta(days=1)
    for model, column, field in ((Lead, Lead.created_at, 'leads'), (Client, Client.start_date, 'sales')):
        expr = sql_bucket(column, period)
        query = db.session.query(expr, func.count(model.id)).filter(model.company_id == company_id)
        lower = start if model is Lead else start.date()
        upper = now if model is Lead else now.date()
        for key, count in query.filter(column >= lower, column <= upper).group_by(expr).all():
            if key in buckets:
                buckets[key][field] = count
    ordered = [buckets[k] for k in sorted(buckets)]
    return {'labels': [b['label'] for b in ordered],
            'leads': [b['leads'] for b in ordered], 'sales': [b['sales'] for b in ordered]}
