from http.server import BaseHTTPRequestHandler
import json
import sys
import os

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        
        status = {
            "status": "alive",
            "python_version": sys.version,
            "cwd": os.getcwd(),
            "packages": {}
        }
        
        # Check Critical Packages
        packages = ['flask', 'sqlalchemy', 'psycopg2', 'werkzeug', 'dotenv', 'northway_crm']
        for pkg in packages:
            try:
                __import__(pkg)
                status["packages"][pkg] = "OK"
            except ImportError as e:
                status["packages"][pkg] = f"MISSING: {str(e)}"
            except Exception as e:
                status["packages"][pkg] = f"ERROR: {str(e)}"

        # Check Env Vars Presence (Masked)
        env_vars = {}
        for k in ['DATABASE_URL', 'SQLALCHEMY_DATABASE_URI', 'FLASK_APP']:
            val = os.environ.get(k)
            env_vars[k] = "SET" if val else "MISSING"
        status["env_vars"] = env_vars
        
        # Determine likely cause of crash
        if any("MISSING" in v for k,v in status["packages"].items()):
            status["diagnosis"] = "Missing Dependencies. Check requirements.txt or build logs."
        elif status["env_vars"]["DATABASE_URL"] == "MISSING" and status["env_vars"]["SQLALCHEMY_DATABASE_URI"] == "MISSING":
            status["diagnosis"] = "Missing Database URL. Check Vercel Environment Variables."
        else:
            status["diagnosis"] = "Environment seems OK. Issue likely in application logic (app factory)."
        
        try:
            response_json = json.dumps(status, indent=2)
            self.wfile.write(response_json.encode('utf-8'))
        except Exception as e:
            self.wfile.write(f"JSON Error: {e}".encode('utf-8'))
        return
