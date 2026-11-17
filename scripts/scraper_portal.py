#!/usr/bin/env python3
"""
NorthWay Prospector Portal (100% Português + Mapa Interativo + Google Meu Negócio)
Interface visual moderna para o Google Maps Scraper (porta 8080 -> motor Docker na porta 8081).
Não requer dependências externas além da biblioteca padrão do Python.
"""
import csv
import io
import json
import math
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORTAL_PORT", "8080"))
ENGINE_URL = os.environ.get("SCRAPER_ENGINE_URL", "http://localhost:8081")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "scraper_data")
HTML_FILE_PATH = os.path.join(os.path.dirname(__file__), "scraper_portal.html")
CONFIG_FILE_PATH = os.path.join(DATA_DIR, "portal_config.json")


def load_crm_config():
    cfg = {
        "crm_url": os.environ.get("NORTHWAY_CRM_URL", "https://crm.northwaycompany.com.br"),
        "crm_api_key": os.environ.get("NORTHWAY_CRM_API_KEY", ""),
        "default_pipeline_id": None,
        "default_stage_id": None,
    }
    if os.path.isfile(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    for k in ("crm_url", "crm_api_key", "default_pipeline_id", "default_stage_id"):
                        if saved.get(k) is not None and saved.get(k) != "":
                            cfg[k] = saved[k]
        except Exception:
            pass
    cfg["crm_url"] = str(cfg["crm_url"]).rstrip("/")
    return cfg


def save_crm_config(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    curr = load_crm_config()
    for k in ("crm_url", "crm_api_key", "default_pipeline_id", "default_stage_id"):
        if k in data:
            curr[k] = data[k]
    curr["crm_url"] = str(curr.get("crm_url") or "https://crm.northwaycompany.com.br").rstrip("/")
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(curr, f, ensure_ascii=False, indent=2)
    return curr


def ensure_memory_table():
    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, "jobs.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prospecting_memory (
            lead_key TEXT PRIMARY KEY,
            title TEXT,
            phone TEXT,
            status TEXT DEFAULT 'novo',
            crm_lead_id INTEGER,
            first_job_id TEXT,
            seen_count INTEGER DEFAULT 1,
            updated_at INTEGER DEFAULT (CAST(strftime('%s', 'now') AS INT))
        )
    """)
    conn.commit()
    conn.close()


def compute_lead_key(item):
    cid = str(item.get("cid") or item.get("place_id") or "").strip()
    if cid:
        return f"cid:{cid}"
    digits = re.sub(r"\D", "", str(item.get("phone") or ""))
    if len(digits) >= 10:
        return f"tel:{digits[-10:]}"
    title = re.sub(r"\s+", " ", str(item.get("title") or "").strip().lower())
    city = re.sub(r"\s+", " ", str(item.get("city") or "").strip().lower())
    return f"name:{title}|{city}"


def get_memory_map(keys):
    if not keys:
        return {}
    ensure_memory_table()
    db_path = os.path.join(DATA_DIR, "jobs.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in keys)
    cur.execute(
        f"SELECT lead_key, status, crm_lead_id, first_job_id, seen_count FROM prospecting_memory WHERE lead_key IN ({placeholders})",
        list(keys),
    )
    out = {}
    for lk, st, crm_id, first_job, seen_cnt in cur.fetchall():
        out[lk] = {
            "status": st or "novo",
            "crm_lead_id": crm_id,
            "first_job_id": first_job,
            "seen_count": seen_cnt or 1,
        }
    conn.close()
    return out


def record_seen_leads(leads, job_id):
    if not leads:
        return
    ensure_memory_table()
    db_path = os.path.join(DATA_DIR, "jobs.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for item in leads:
        lk = item.get("lead_key")
        if not lk:
            continue
        cur.execute("SELECT first_job_id, seen_count FROM prospecting_memory WHERE lead_key = ?", (lk,))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO prospecting_memory (lead_key, title, phone, status, first_job_id, seen_count) VALUES (?, ?, ?, 'novo', ?, 1)",
                (lk, item.get("title") or "", item.get("phone") or "", str(job_id)),
            )
        elif row[0] and str(row[0]) != str(job_id):
            cur.execute(
                "UPDATE prospecting_memory SET seen_count = seen_count + 1, updated_at = CAST(strftime('%s', 'now') AS INT) WHERE lead_key = ?",
                (lk,),
            )
    conn.commit()
    conn.close()


def mark_lead_memory(lead_key, status, crm_lead_id=None, title="", phone=""):
    ensure_memory_table()
    db_path = os.path.join(DATA_DIR, "jobs.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT lead_key FROM prospecting_memory WHERE lead_key = ?", (lead_key,))
    if cur.fetchone():
        if crm_lead_id is not None:
            cur.execute(
                "UPDATE prospecting_memory SET status = ?, crm_lead_id = ?, updated_at = CAST(strftime('%s', 'now') AS INT) WHERE lead_key = ?",
                (status, crm_lead_id, lead_key),
            )
        else:
            cur.execute(
                "UPDATE prospecting_memory SET status = ?, updated_at = CAST(strftime('%s', 'now') AS INT) WHERE lead_key = ?",
                (status, lead_key),
            )
    else:
        cur.execute(
            "INSERT INTO prospecting_memory (lead_key, title, phone, status, crm_lead_id) VALUES (?, ?, ?, ?, ?)",
            (lead_key, title, phone, status, crm_lead_id),
        )
    conn.commit()
    conn.close()


def compute_opportunity_score(item):
    """Calcula Score de Oportunidade Comercial (0..10) para abordagem NorthWay."""
    score = 0
    reasons = []

    site = (item.get("website") or "").lower()
    social_only_domains = ("instagram.com", "linktr.ee", "wa.me", "api.whatsapp.com", "facebook.com", "bit.ly")
    no_real_site = (not site) or any(d in site for d in social_only_domains)
    item["no_real_site"] = no_real_site
    if no_real_site:
        score += 3
        reasons.append("Sem site próprio" if not site else "Usa só rede social/link")

    rev_count = int(item.get("review_count") or 0)
    if rev_count < 20:
        score += 2
        reasons.append(f"Poucas avaliações ({rev_count})")
        if rev_count < 5:
            score += 1

    try:
        rating_val = float(item.get("review_rating")) if item.get("review_rating") else None
    except Exception:
        rating_val = None
    if rating_val is not None and rating_val < 4.3:
        score += 2
        reasons.append(f"Nota {rating_val:.1f} (< 4,3)")

    if item.get("whatsapp_url"):
        score += 2
        reasons.append("WhatsApp ativo")

    reviews = item.get("user_reviews") or []
    unanswered = any(not (r.get("reply_text_original") or r.get("ResponseFromOwnerText")) for r in reviews if isinstance(r, dict))
    if reviews and unanswered:
        score += 1
        reasons.append("Avaliações sem resposta")

    score = min(10, score)
    level = "quente" if score >= 7 else ("morno" if score >= 4 else "frio")
    item["opportunity_score"] = score
    item["opportunity_level"] = level
    item["opportunity_reasons"] = reasons


def ensure_drafts_table():
    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, "jobs.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prospecting_drafts (
            lead_key TEXT PRIMARY KEY,
            empresa TEXT,
            decisor TEXT,
            cargo TEXT,
            phone TEXT,
            whatsapp TEXT,
            email TEXT,
            cnpj TEXT,
            instagram TEXT,
            website TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            category TEXT,
            opportunity_score INTEGER DEFAULT 0,
            notes TEXT,
            status TEXT DEFAULT 'rascunho',
            updated_at INTEGER DEFAULT (CAST(strftime('%s', 'now') AS INT))
        )
    """)
    conn.commit()
    conn.close()


def list_drafts():
    ensure_drafts_table()
    db_path = os.path.join(DATA_DIR, "jobs.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM prospecting_drafts ORDER BY updated_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def upsert_draft(data):
    ensure_drafts_table()
    lk = (data.get("lead_key") or "").strip()
    if not lk:
        lk = compute_lead_key({"title": data.get("empresa"), "phone": data.get("phone"), "city": data.get("city")})
    db_path = os.path.join(DATA_DIR, "jobs.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT lead_key FROM prospecting_drafts WHERE lead_key = ?", (lk,))
    exists = cur.fetchone() is not None
    fields = (
        data.get("empresa") or "",
        data.get("decisor") or "",
        data.get("cargo") or "",
        data.get("phone") or "",
        data.get("whatsapp") or data.get("phone") or "",
        data.get("email") or "",
        data.get("cnpj") or "",
        data.get("instagram") or "",
        data.get("website") or "",
        data.get("address") or "",
        data.get("city") or "",
        data.get("state") or "",
        data.get("category") or "",
        int(data.get("opportunity_score") or 0),
        data.get("notes") or "",
        data.get("status") or "rascunho",
    )
    if exists:
        cur.execute("""
            UPDATE prospecting_drafts
            SET empresa=?, decisor=?, cargo=?, phone=?, whatsapp=?, email=?, cnpj=?, instagram=?,
                website=?, address=?, city=?, state=?, category=?, opportunity_score=?, notes=?, status=?,
                updated_at=CAST(strftime('%s', 'now') AS INT)
            WHERE lead_key=?
        """, fields + (lk,))
    else:
        cur.execute("""
            INSERT INTO prospecting_drafts (
                empresa, decisor, cargo, phone, whatsapp, email, cnpj, instagram,
                website, address, city, state, category, opportunity_score, notes, status, lead_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, fields + (lk,))
    conn.commit()
    conn.close()
    return lk


def delete_draft(lead_key=None, clear_sent=False):
    ensure_drafts_table()
    db_path = os.path.join(DATA_DIR, "jobs.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if clear_sent:
        cur.execute("DELETE FROM prospecting_drafts WHERE status = 'enviado_crm'")
    elif lead_key:
        cur.execute("DELETE FROM prospecting_drafts WHERE lead_key = ?", (lead_key,))
    conn.commit()
    conn.close()


def enrich_site_and_cnpj(site_url="", cnpj_input=""):
    """Extrai @instagram e CNPJ do site e consulta sócios (QSA) na BrasilAPI."""
    out = {"instagram": None, "cnpj": None, "razao_social": None, "socios": []}
    raw_cnpj = re.sub(r"\D", "", cnpj_input or "")

    if site_url and site_url.startswith("http"):
        try:
            req = urllib.request.Request(site_url, headers={"User-Agent": "Mozilla/5.0 NorthWayProspector/2.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                html = resp.read(180000).decode("utf-8", errors="ignore")
            ig = re.search(r"instagram\.com/([a-zA-Z0-9._]{2,30})", html, re.I)
            if ig and ig.group(1).lower() not in ("p", "reel", "explore", "stories", "share"):
                out["instagram"] = "@" + ig.group(1)
            if not raw_cnpj:
                m_cnpj = re.search(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b", html)
                if m_cnpj:
                    raw_cnpj = re.sub(r"\D", "", m_cnpj.group(1))
        except Exception:
            pass

    if len(raw_cnpj) == 14:
        out["cnpj"] = f"{raw_cnpj[:2]}.{raw_cnpj[2:5]}.{raw_cnpj[5:8]}/{raw_cnpj[8:12]}-{raw_cnpj[12:]}"
        try:
            req = urllib.request.Request(
                f"https://brasilapi.com.br/api/cnpj/v1/{raw_cnpj}",
                headers={"User-Agent": "NorthWayProspector/2.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                cdata = json.loads(resp.read().decode("utf-8"))
                out["razao_social"] = cdata.get("razao_social") or cdata.get("nome_fantasia")
                qsa = cdata.get("qsa") or []
                out["socios"] = [
                    {"nome": s.get("nome_socio"), "qualificacao": s.get("qualificacao_socio")}
                    for s in qsa if s.get("nome_socio")
                ][:5]
        except Exception:
            pass

    return out


def haversine_km(lat1, lon1, lat2, lon2):
    """Calcula a distância em quilômetros entre duas coordenadas geográficas."""
    try:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 1)
    except Exception:
        return None


def clean_emails(raw_email):
    """Filtra e-mails de telemetria/erros do Wix, Sentry, Webpack e lixo técnico."""
    if not raw_email:
        return ""
    emails = [e.strip() for e in str(raw_email).replace(";", ",").split(",") if e.strip()]
    cleaned = []
    bad_patterns = [
        "sentry", "wixpress", "noreply", "example.com", "domain.com",
        "webpack", "test@", "placeholder", "user@", "email@", "fake@"
    ]
    for e in emails:
        lower = e.lower()
        if any(b in lower for b in bad_patterns):
            continue
        if re.match(r"^[a-f0-9]{16,}@", lower):
            continue
        if "@" in e and "." in e.split("@")[-1]:
            cleaned.append(e)
    return ", ".join(cleaned)


def format_whatsapp(phone):
    """Converte telefone brasileiro em link direto do WhatsApp (wa.me)."""
    if not phone:
        return None, None
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) in (10, 11):
        full_digits = "55" + digits
    elif len(digits) in (12, 13) and digits.startswith("55"):
        full_digits = digits
    else:
        return phone, None
    return phone, f"https://wa.me/{full_digits}"


def parse_json_safely(val):
    if not val or not isinstance(val, str):
        return val
    try:
        return json.loads(val)
    except Exception:
        return None


def sanitize_lead(lead, center_lat=None, center_lon=None):
    """Enriquece e higieniza os campos do lead para uso comercial e exibição no Cartão Google Meu Negócio."""
    item = dict(lead)

    # Limpeza de E-mails
    raw_email = item.get("emails") or item.get("email") or ""
    item["emails"] = clean_emails(raw_email)

    # WhatsApp e Telefone
    raw_phone = item.get("phone") or ""
    display_phone, wa_link = format_whatsapp(raw_phone)
    item["phone"] = display_phone or ""
    item["whatsapp_url"] = wa_link

    # Extração de Endereço e Cidade Estruturados
    comp_raw = item.get("complete_address")
    city = item.get("city") or ""
    state = item.get("state") or ""
    borough = item.get("borough") or ""
    street = item.get("street") or ""
    postal_code = item.get("postal_code") or ""

    if comp_raw and isinstance(comp_raw, str):
        try:
            comp = json.loads(comp_raw)
            if isinstance(comp, dict):
                city = city or comp.get("city") or ""
                state = state or comp.get("state") or ""
                borough = borough or comp.get("borough") or ""
                street = street or comp.get("street") or ""
                postal_code = postal_code or comp.get("postal_code") or ""
        except Exception:
            pass

    item["city"] = city
    item["state"] = state
    item["borough"] = borough
    item["street"] = street
    item["postal_code"] = postal_code

    raw_addr = (item.get("address") or "").strip()
    if not raw_addr or (street and street.lower() not in raw_addr.lower()):
        city_state = " - ".join([p for p in (city, state) if p])
        addr_parts = [p for p in (street, borough, city_state, postal_code) if p]
        if addr_parts:
            raw_addr = ", ".join(addr_parts)
    item["address"] = raw_addr

    location_parts = [p for p in [borough, city, state] if p]
    item["location_summary"] = " · ".join(location_parts) if location_parts else raw_addr

    # Avaliações
    rating = item.get("rating") or item.get("review_rating")
    try:
        if rating is not None and str(rating).strip() not in ("", "None"):
            item["review_rating"] = f"{float(rating):.1f}"
        else:
            item["review_rating"] = None
    except Exception:
        item["review_rating"] = None

    review_count = item.get("reviews") or item.get("review_count")
    try:
        item["review_count"] = int(review_count) if review_count is not None and str(review_count).strip() not in ("", "None") else 0
    except Exception:
        item["review_count"] = 0

    # Categoria limpa
    cat = item.get("category") or item.get("main_category") or "Empresa"
    item["category"] = cat

    # Website
    site = item.get("website") or ""
    if site and not site.startswith("http"):
        site = "https://" + site
    item["website"] = site

    # Dados Oficiais Google Meu Negócio
    item["google_maps_url"] = item.get("link") or item.get("url") or ""
    item["thumbnail"] = item.get("thumbnail") or ""
    item["open_hours"] = parse_json_safely(item.get("open_hours"))
    item["about"] = parse_json_safely(item.get("about"))
    item["owner"] = parse_json_safely(item.get("owner"))

    # Avaliações de Usuários (Google Reviews)
    user_reviews = parse_json_safely(item.get("user_reviews"))
    if isinstance(user_reviews, list):
        item["user_reviews"] = user_reviews[:4]  # Envia as melhores avaliações
    else:
        item["user_reviews"] = []

    # Distância calculada em KM até o centro da busca
    item["distance_km"] = None
    try:
        lat = float(item.get("latitude") or item.get("lat"))
        lon = float(item.get("longitude") or item.get("lon") or item.get("longtitude"))
        item["latitude"] = lat
        item["longitude"] = lon
        if center_lat is not None and center_lon is not None:
            item["distance_km"] = haversine_km(center_lat, center_lon, lat, lon)
    except Exception:
        pass

    item["lead_key"] = compute_lead_key(item)
    compute_opportunity_score(item)

    return item


def get_html_content():
    if os.path.exists(HTML_FILE_PATH):
        with open(HTML_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Portal HTML não encontrado</h1>"


def get_job_center_coords(job_id):
    """Recupera latitude e longitude do job no banco SQLite jobs.db para calcular distâncias."""
    db_path = os.path.join(DATA_DIR, "jobs.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT data FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                data = json.loads(row[0])
                lat = float(data.get("lat"))
                lon = float(data.get("lon"))
                radius_km = (float(data.get("radius") or 35000)) / 1000.0
                return lat, lon, radius_km
        except Exception:
            pass
    return None, None, None


def delete_single_job(job_id):
    """Remove um job do SQLite local, arquivos em disco e tenta notificar o Docker engine."""
    deleted_any = False
    
    # 1. Remover do SQLite jobs.db
    db_path = os.path.join(DATA_DIR, "jobs.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            if cur.rowcount > 0:
                deleted_any = True
            conn.close()
        except Exception:
            pass

    # 2. Remover arquivos CSV e JSON em disco
    for ext in ("", ".csv", ".json"):
        fpath = os.path.join(DATA_DIR, os.path.basename(f"{job_id}{ext}"))
        if os.path.isfile(fpath):
            try:
                os.remove(fpath)
                deleted_any = True
            except Exception:
                pass

    # 3. Notificar o Docker engine na porta 8081 se estiver ativo
    try:
        req = urllib.request.Request(f"{ENGINE_URL}/api/v1/jobs/{job_id}", method="DELETE")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            pass
    except Exception:
        pass

    return deleted_any


def delete_batch_jobs(job_ids=None, delete_all=False):
    """Exclui múltiplos jobs selecionados ou limpa todo o histórico."""
    deleted_count = 0
    db_path = os.path.join(DATA_DIR, "jobs.db")

    if delete_all:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("SELECT id FROM jobs")
                all_ids = [r[0] for r in cur.fetchall()]
                cur.execute("DELETE FROM jobs")
                conn.commit()
                conn.close()
                deleted_count += len(all_ids)
                job_ids = all_ids
            except Exception:
                job_ids = []
        else:
            job_ids = []

        # Limpar todos os arquivos .csv e .json da pasta scraper_data
        if os.path.isdir(DATA_DIR):
            for fname in os.listdir(DATA_DIR):
                if fname.endswith((".csv", ".json")):
                    try:
                        os.remove(os.path.join(DATA_DIR, fname))
                    except Exception:
                        pass
        return {"success": True, "deleted": deleted_count, "all": True}

    if not job_ids:
        return {"success": True, "deleted": 0}

    for jid in job_ids:
        if delete_single_job(jid):
            deleted_count += 1

    return {"success": True, "deleted": deleted_count}


def set_job_status(job_id, new_status="canceled"):
    """Atualiza o status de um job no banco SQLite local."""
    db_path = os.path.join(DATA_DIR, "jobs.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("UPDATE jobs SET status = ?, updated_at = CAST(strftime('%s', 'now') AS INT) WHERE id = ?", (new_status, job_id))
            conn.commit()
            conn.close()
            return True
        except Exception:
            pass
    return False


class ScraperPortalHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path in ("/logo.png", "/static/img/northway_logo.png") or self.path.startswith("/static/"):
            logo_path = os.path.join(PROJECT_ROOT, "static", "img", "northway_logo.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
                return

        if self.path == "/" or self.path.startswith("/?"):
            raw = get_html_content().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        # Download do ZIP da Extensão Chrome (NorthWay Lead Copilot)
        if self.path == "/api/portal/download-extension":
            ext_dir = os.path.join(PROJECT_ROOT, "tools", "northway-copilot-extension")
            if not os.path.isdir(ext_dir):
                self._send_json({"error": "Diretório da extensão não encontrado"}, status=404)
                return

            mem_zip = io.BytesIO()
            with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(ext_dir):
                    for file in files:
                        if file.startswith("."):
                            continue
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, ext_dir)
                        zf.write(file_path, arcname)

            mem_zip.seek(0)
            zip_bytes = mem_zip.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="northway-lead-copilot.zip"')
            self.send_header("Content-Length", str(len(zip_bytes)))
            self.end_headers()
            self.wfile.write(zip_bytes)
            return

        if self.path == "/api/portal/jobs":
            jobs = []
            engine_online = False
            try:
                req = urllib.request.Request(f"{ENGINE_URL}/api/v1/jobs")
                with urllib.request.urlopen(req, timeout=6) as resp:
                    engine_online = True
                    raw_jobs = json.loads(resp.read().decode("utf-8")) or []
                    for j in raw_jobs:
                        jobs.append({
                            "id": j.get("ID") or j.get("id"),
                            "name": j.get("Name") or j.get("name") or "Extração",
                            "status": str(j.get("Status") or j.get("status") or "pending").lower(),
                        })
            except Exception:
                engine_online = False

            if not jobs and os.path.exists(os.path.join(DATA_DIR, "jobs.db")):
                try:
                    conn = sqlite3.connect(os.path.join(DATA_DIR, "jobs.db"))
                    cur = conn.cursor()
                    cur.execute("SELECT id, name, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 50")
                    for r in cur.fetchall():
                        jid, jname, jstatus, _ = r[0], r[1], str(r[2]).lower(), r[3]
                        # Se já existe arquivo CSV com dados em disco, destrava status 'working' para 'ok'
                        csv_path = os.path.join(DATA_DIR, f"{jid}.csv")
                        if jstatus == "working" and os.path.isfile(csv_path) and os.path.getsize(csv_path) > 100:
                            jstatus = "ok"
                            set_job_status(jid, "ok")
                        jobs.append({"id": jid, "name": jname, "status": jstatus})
                    conn.close()
                except Exception:
                    pass

            if os.path.isdir(DATA_DIR):
                existing_ids = {j["id"] for j in jobs}
                for fname in sorted(os.listdir(DATA_DIR), reverse=True):
                    if fname.endswith((".csv", ".json")) and fname not in existing_ids:
                        base_id = fname.rsplit(".", 1)[0]
                        if base_id not in existing_ids:
                            jobs.append({"id": fname, "name": f"Arquivo: {fname}", "status": "ok"})

            self._send_json({"engine_online": engine_online, "jobs": jobs})
            return

        # Status rápido e leve para polling em tempo real
        if self.path.startswith("/api/portal/jobs/") and self.path.endswith("/status"):
            job_id = urllib.parse.unquote(self.path.split("/api/portal/jobs/")[1].rsplit("/status", 1)[0])
            status = "working"
            count = 0

            # 1. Checa no Docker se online
            try:
                req = urllib.request.Request(f"{ENGINE_URL}/api/v1/jobs/{job_id}")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    dj = json.loads(resp.read().decode("utf-8"))
                    status = str(dj.get("Status") or dj.get("status") or "working").lower()
            except Exception:
                pass

            # 2. Checa se o arquivo CSV já existe em disco
            for cand in [job_id, f"{job_id}.csv"]:
                p = os.path.join(DATA_DIR, os.path.basename(cand))
                if os.path.isfile(p):
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as f:
                            lines = [ln for ln in f if ln.strip()]
                            if len(lines) > 1:
                                count = len(lines) - 1
                                status = "ok"
                    except Exception:
                        pass
                    break

            # 3. Checa no SQLite se ainda estiver pending/working
            if status == "working" and os.path.exists(os.path.join(DATA_DIR, "jobs.db")):
                try:
                    conn = sqlite3.connect(os.path.join(DATA_DIR, "jobs.db"))
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
                    row = cur.fetchone()
                    conn.close()
                    if row and row[0]:
                        status = str(row[0]).lower()
                except Exception:
                    pass

            self._send_json({"id": job_id, "status": status, "count": count})
            return

        # Cidades Oficiais do Brasil por UF (IBGE com cache local)
        if self.path.startswith("/api/portal/cities"):
            parsed_url = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed_url.query)
            uf = (qs.get("uf", ["PR"])[0]).upper().strip()
            
            cache_file = os.path.join(DATA_DIR, f"cities_{uf}.json")
            cities = []

            # 1. Checa cache local em disco
            if os.path.isfile(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cities = json.load(f)
                except Exception:
                    cities = []

            # 2. Se não estiver no cache, busca na API oficial do IBGE
            if not cities:
                try:
                    ibge_url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
                    req = urllib.request.Request(ibge_url, headers={"User-Agent": "NorthWayProspector/2.0"})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        cities = sorted([m.get("nome") for m in data if m.get("nome")])
                        if cities:
                            with open(cache_file, "w", encoding="utf-8") as f:
                                json.dump(cities, f, ensure_ascii=False)
                except Exception:
                    pass

            # 3. Fallback seguro se offline
            if not cities:
                fallback_map = {
                    "PR": ["Wenceslau Braz", "Curitiba", "Londrina", "Maringá", "Ponta Grossa", "Cascavel", "Foz do Iguaçu", "São José dos Pinhais", "Colombo", "Guarapuava", "Paranaguá", "Apucarana", "Toledo", "Araucária", "Pinhais", "Campo Largo", "Arapongas", "Almirante Tamandaré", "Umuarama", "Piraquara", "Cambé", "Fazenda Rio Grande", "Sarandi", "Fazenda Rio Grande", "Joaquim Távora", "Tomazina", "Santana do Itararé", "Siqueira Campos"],
                    "SP": ["São Paulo", "Guarulhos", "Campinas", "São Bernardo do Campo", "Santo André", "Osasco", "São José dos Campos", "Ribeirão Preto", "Sorocaba", "Santos", "Mauá", "São José do Rio Preto", "Mogi das Cruzes", "Diadema", "Jundiaí", "Piracicaba", "Carapicuíba", "Bauru", "Itaquaquecetuba", "São Vicente"],
                    "MG": ["Belo Horizonte", "Uberlândia", "Contagem", "Juiz de Fora", "Betim", "Montes Claros", "Ribeirão das Neves", "Uberaba", "Governador Valadares", "Ipatinga", "Sete Lagoas", "Divinópolis", "Santa Luzia", "Ibirité", "Poços de Caldas", "Patos de Minas", "Pouso Alegre", "Curvelo", "Corinto", "Diamantina"]
                }
                cities = fallback_map.get(uf, ["Capital", "Interior"])

            self._send_json({"uf": uf, "cities": cities, "count": len(cities)})
            return

        if self.path == "/api/portal/crm/config":
            cfg = load_crm_config()
            masked = ("***" + cfg["crm_api_key"][-6:]) if cfg.get("crm_api_key") else ""
            self._send_json({
                "crm_url": cfg["crm_url"],
                "has_api_key": bool(cfg.get("crm_api_key")),
                "api_key_masked": masked,
                "default_pipeline_id": cfg.get("default_pipeline_id"),
                "default_stage_id": cfg.get("default_stage_id"),
            })
            return

        if self.path == "/api/portal/crm/pipelines":
            cfg = load_crm_config()
            if not cfg.get("crm_api_key"):
                self._send_json({"success": False, "error": "Configure a API Key do CRM primeiro."}, status=400)
                return
            try:
                req = urllib.request.Request(
                    f"{cfg['crm_url']}/api/v1/pipelines",
                    headers={"X-API-Key": cfg["crm_api_key"]},
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._send_json(data)
            except urllib.error.HTTPError as e:
                self._send_json({"success": False, "error": f"CRM retornou HTTP {e.code}"}, status=e.code)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=502)
            return

        if self.path == "/api/portal/drafts":
            self._send_json({"success": True, "drafts": list_drafts()})
            return

        if self.path == "/api/portal/drafts/export":
            drafts = list_drafts()
            buf = io.StringIO()
            writer = csv.writer(buf, delimiter=";")
            writer.writerow([
                "Empresa", "Decisor", "Cargo", "Telefone", "WhatsApp",
                "E-mail", "CNPJ", "Instagram", "Site", "Endereço",
                "Cidade", "UF", "Categoria", "Score", "Status", "Observações"
            ])
            for d in drafts:
                writer.writerow([
                    d.get("empresa") or "",
                    d.get("decisor") or "",
                    d.get("cargo") or "",
                    d.get("phone") or "",
                    d.get("whatsapp") or "",
                    d.get("email") or "",
                    d.get("cnpj") or "",
                    d.get("instagram") or "",
                    d.get("website") or "",
                    d.get("address") or "",
                    d.get("city") or "",
                    d.get("state") or "",
                    d.get("category") or "",
                    d.get("opportunity_score") or 0,
                    d.get("status") or "rascunho",
                    d.get("notes") or "",
                ])
            csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="northway-fila-prospeccao.csv"')
            self.send_header("Content-Length", str(len(csv_bytes)))
            self.end_headers()
            self.wfile.write(csv_bytes)
            return

        if self.path.startswith("/api/portal/enrich/site"):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            site_url = qs.get("url", [""])[0]
            cnpj_in = qs.get("cnpj", [""])[0]
            res = enrich_site_and_cnpj(site_url=site_url, cnpj_input=cnpj_in)
            self._send_json({"success": True, **res})
            return

        if self.path.startswith("/api/portal/jobs/") and self.path.endswith("/leads"):
            job_id = urllib.parse.unquote(self.path.split("/api/portal/jobs/")[1].rsplit("/leads", 1)[0])
            content = None
            is_json = job_id.lower().endswith(".json")

            center_lat, center_lon, job_radius_km = get_job_center_coords(job_id)

            for cand in [job_id, f"{job_id}.csv", f"{job_id}.json"]:
                p = os.path.join(DATA_DIR, os.path.basename(cand))
                if os.path.isfile(p):
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    is_json = p.lower().endswith(".json")
                    break

            if content is None:
                try:
                    req = urllib.request.Request(f"{ENGINE_URL}/api/v1/jobs/{job_id}/download")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        content = resp.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass

            leads = []
            if content:
                if is_json:
                    try:
                        parsed = json.loads(content)
                        raw_leads = parsed if isinstance(parsed, list) else (parsed.get("results") or [parsed])
                    except Exception:
                        raw_leads = []
                        for line in content.splitlines():
                            if line.strip():
                                try:
                                    raw_leads.append(json.loads(line.strip()))
                                except Exception:
                                    pass
                else:
                    delim = ";" if content.count(";") > content.count(",") else ","
                    raw_leads = list(csv.DictReader(io.StringIO(content), delimiter=delim))

                leads = [sanitize_lead(r, center_lat, center_lon) for r in raw_leads]
                record_seen_leads(leads, job_id)
                mem_map = get_memory_map([l["lead_key"] for l in leads])
                for l in leads:
                    mem = mem_map.get(l["lead_key"], {})
                    l["memory_status"] = mem.get("status", "novo")
                    l["crm_lead_id"] = mem.get("crm_lead_id")
                    l["seen_count"] = mem.get("seen_count", 1)
                    l["is_duplicate_across_jobs"] = (mem.get("first_job_id") is not None and str(mem.get("first_job_id")) != str(job_id))

            self._send_json({
                "leads": leads,
                "count": len(leads),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "radius_km": job_radius_km
            })
            return

        # Proxy /api/v1/* to ENGINE_URL or local download
        if self.path.startswith("/api/v1/"):
            if self.path.endswith("/download"):
                job_id = urllib.parse.unquote(self.path.split("/api/v1/jobs/")[1].rsplit("/download", 1)[0])
                local_path = None
                for cand in [job_id, f"{job_id}.csv"]:
                    p = os.path.join(DATA_DIR, os.path.basename(cand))
                    if os.path.isfile(p):
                        local_path = p
                        break
                if local_path and os.path.isfile(local_path):
                    with open(local_path, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(local_path)}"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

            try:
                req = urllib.request.Request(f"{ENGINE_URL}{self.path}")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read()
                    self.send_response(resp.status)
                    for k, v in resp.getheaders():
                        if k.lower() not in ("transfer-encoding", "content-encoding", "content-length"):
                            self.send_header(k, v)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except Exception as e:
                self._send_json({"error": str(e)}, status=502)
            return

        self.send_error(404)

    def do_POST(self):
        # Exclusão em Lote
        if self.path == "/api/portal/crm/config":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            saved = save_crm_config(payload)
            self._send_json({"success": True, "crm_url": saved["crm_url"], "has_api_key": bool(saved.get("crm_api_key"))})
            return

        if self.path == "/api/portal/leads/mark":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            lk = payload.get("lead_key")
            st = payload.get("status") or "novo"
            if not lk:
                self._send_json({"success": False, "error": "lead_key obrigatório"}, status=400)
                return
            mark_lead_memory(lk, st, title=payload.get("title", ""), phone=payload.get("phone", ""))
            self._send_json({"success": True, "lead_key": lk, "status": st})
            return

        if self.path == "/api/portal/drafts/save":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            lk = upsert_draft(payload)
            self._send_json({"success": True, "lead_key": lk})
            return

        if self.path == "/api/portal/drafts/delete":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            delete_draft(lead_key=payload.get("lead_key"), clear_sent=bool(payload.get("clear_sent")))
            self._send_json({"success": True})
            return

        if self.path == "/api/portal/crm/send":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            cfg = load_crm_config()
            if not cfg.get("crm_api_key"):
                self._send_json({"success": False, "error": "Configure a API Key do CRM antes de enviar."}, status=400)
                return

            leads_to_send = payload.get("leads") or []
            pipeline_id = payload.get("pipeline_id") or cfg.get("default_pipeline_id")
            stage_id = payload.get("pipeline_stage_id") or cfg.get("default_stage_id")

            created, duplicates, errors = 0, 0, 0
            for item in leads_to_send:
                empresa_nome = item.get("empresa") or item.get("title") or "Empresa sem nome"
                decisor_nome = (item.get("decisor") or "").strip()
                cargo_nome = (item.get("cargo") or "").strip()
                ig = (item.get("instagram") or "").strip()
                custom_notes = (item.get("notes") or "").strip()
                desc_parts = [
                    f"Empresa: {empresa_nome}",
                    f"Decisor: {decisor_nome}" + (f" ({cargo_nome})" if cargo_nome else "") if decisor_nome else None,
                    f"Instagram: {ig}" if ig else None,
                    f"Observações: {custom_notes}" if custom_notes else None,
                    f"Score Oportunidade: {item.get('opportunity_score', 0)}/10 ({', '.join(item.get('opportunity_reasons') or [])})",
                    f"Categoria: {item.get('category') or 'Empresa'}",
                    f"Avaliações Google: {item.get('review_rating') or '-'} ({item.get('review_count') or 0})" if item.get("review_rating") or item.get("review_count") else None,
                    f"Site: {item.get('website') or 'Não informado'}",
                    f"Google Maps: {item.get('google_maps_url') or ''}" if item.get("google_maps_url") else None,
                ]
                raw_mail = item.get("email") or item.get("emails") or ""
                first_mail = raw_mail.split(",")[0].strip() or None
                lead_body = {
                    "name": decisor_nome or empresa_nome,
                    "legal_name": empresa_nome,
                    "phone": item.get("phone") or "",
                    "whatsapp": item.get("whatsapp") or item.get("phone") or "",
                    "email": first_mail,
                    "website": item.get("website") or None,
                    "address": item.get("address") or None,
                    "city": item.get("city") or None,
                    "state": item.get("state") or None,
                    "cnpj": item.get("cnpj") or None,
                    "pipeline_id": int(pipeline_id) if pipeline_id else None,
                    "pipeline_stage_id": int(stage_id) if stage_id else None,
                    "source": "Google Maps Prospector",
                    "description": "\n".join([p for p in desc_parts if p]),
                    "dedupe": True,
                }
                try:
                    req = urllib.request.Request(
                        f"{cfg['crm_url']}/api/v1/leads",
                        data=json.dumps(lead_body).encode("utf-8"),
                        headers={"Content-Type": "application/json", "X-API-Key": cfg["crm_api_key"]},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        r_data = json.loads(resp.read().decode("utf-8"))
                        crm_id = (r_data.get("data") or {}).get("id")
                        if r_data.get("duplicate"):
                            duplicates += 1
                        else:
                            created += 1
                        if item.get("lead_key"):
                            mark_lead_memory(item["lead_key"], "enviado_crm", crm_lead_id=crm_id, title=empresa_nome, phone=item.get("phone", ""))
                            # Atualiza rascunho se existir na fila
                            ensure_drafts_table()
                            db_path = os.path.join(DATA_DIR, "jobs.db")
                            conn = sqlite3.connect(db_path)
                            conn.execute("UPDATE prospecting_drafts SET status = 'enviado_crm' WHERE lead_key = ?", (item["lead_key"],))
                            conn.commit()
                            conn.close()
                except Exception:
                    errors += 1

            self._send_json({
                "success": True,
                "created": created,
                "duplicates": duplicates,
                "errors": errors,
            })
            return

        if self.path == "/api/portal/jobs/batch-delete":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            job_ids = payload.get("ids") or []
            delete_all = bool(payload.get("all"))
            res = delete_batch_jobs(job_ids=job_ids, delete_all=delete_all)
            self._send_json(res)
            return

        # Cancelar ou Destravar Pesquisa Presa
        if self.path == "/api/portal/jobs/cancel":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            job_id = payload.get("id")
            if job_id:
                set_job_status(job_id, "canceled")
                try:
                    req = urllib.request.Request(f"{ENGINE_URL}/api/v1/jobs/{job_id}", method="DELETE")
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        pass
                except Exception:
                    pass
                self._send_json({"success": True, "id": job_id, "status": "canceled"})
            else:
                self._send_json({"error": "ID não informado"}, status=400)
            return

        if self.path.startswith("/api/v1/"):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b""
            try:
                req = urllib.request.Request(
                    f"{ENGINE_URL}{self.path}",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_body = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp_body)))
                    self.end_headers()
                    self.wfile.write(resp_body)
            except urllib.error.HTTPError as e:
                err_body = e.read()
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err_body)
            except Exception as e:
                self._send_json({"error": str(e)}, status=502)
            return
        self.send_error(404)

    def do_DELETE(self):
        # Exclusão individual de Job (trabalha local e com proxy simultâneo)
        if self.path.startswith("/api/v1/jobs/") or self.path.startswith("/api/portal/jobs/"):
            prefix = "/api/v1/jobs/" if self.path.startswith("/api/v1/jobs/") else "/api/portal/jobs/"
            job_id = urllib.parse.unquote(self.path.split(prefix, 1)[1].split("/", 1)[0])
            deleted = delete_single_job(job_id)
            self._send_json({"success": True, "id": job_id, "deleted": deleted})
            return

        self.send_error(404)


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    server = HTTPServer(("0.0.0.0", PORT), ScraperPortalHandler)
    print(f"✅ NorthWay Prospector Portal (PT-BR + Mapa + GMB) ativo em http://localhost:{PORT}")
    server.serve_forever()
