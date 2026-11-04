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

    if comp_raw and isinstance(comp_raw, str):
        try:
            comp = json.loads(comp_raw)
            if isinstance(comp, dict):
                city = city or comp.get("city") or ""
                state = state or comp.get("state") or ""
                borough = borough or comp.get("borough") or ""
                street = street or comp.get("street") or ""
        except Exception:
            pass

    item["city"] = city
    item["state"] = state
    item["borough"] = borough
    item["street"] = street

    location_parts = [p for p in [borough, city, state] if p]
    item["location_summary"] = " · ".join(location_parts) if location_parts else (item.get("address") or "")

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

    def _send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
