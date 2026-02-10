from flask import Flask, request
import os
import time

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def migrate_standalone(path):
    # Retrieve DB URI from Enum
    db_uri = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
    
    if not db_uri:
        return "ERROR: Could not find DATABASE_URL or SQLALCHEMY_DATABASE_URI in env.", 500

    action = request.args.get('action', 'status')
    results = []
    
    results.append("<h1>Standalone Migration Tool</h1>")
    results.append(f"<p>DB URI Found (Masked): {db_uri.split('@')[-1] if '@' in db_uri else '...'}</p>")
    
    try:
        from sqlalchemy import create_engine, text
        
        # Create Engine
        engine = create_engine(db_uri)
        
        # Test Connection
        start = time.time()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        elapsed = time.time() - start
        results.append(f"<p style='color:green'>Connection Successful ({elapsed:.4f}s)</p>")
        
        if action == 'status':
            results.append("<h3>Status: Ready</h3>")
            results.append("<p>Click below to execute migration:</p>")
            results.append(f"<a href='?action=execute'><button>EXECUTE MIGRATION</button></a>")
            return "".join(results)
            
        if action == 'execute':
            results.append("<h3>Executing Migration...</h3>")
            is_postgres = 'postgres' in db_uri or 'psycopg' in db_uri
            
            queries = []
            if is_postgres: 
                 queries = [
                    # Drive Folder Template
                    """CREATE TABLE IF NOT EXISTS drive_folder_template (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES company(id),
                        name VARCHAR(100) NOT NULL,
                        structure_json TEXT NOT NULL,
                        is_default BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );""",
                    
                    # Columns with IF NOT EXISTS (Postgres 9.6+)
                    "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                    "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_score FLOAT;",
                    "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_stars FLOAT;",
                    "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_classification VARCHAR(50);",
                    "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_date TIMESTAMP WITH TIME ZONE;",
                    "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_pillars JSONB;",
                    
                    "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                    "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_score FLOAT;",
                    "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_stars FLOAT;",
                    "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_classification VARCHAR(50);",
                    "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_date TIMESTAMP WITH TIME ZONE;",
                    "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_pillars JSONB;",
                    
                    "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                    "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS stars FLOAT;",
                    "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS classification VARCHAR(100);",
                    
                    "ALTER TABLE interaction ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                    "ALTER TABLE task ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                    
                    "ALTER TABLE company ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '{}';",
                    
                    """CREATE TABLE IF NOT EXISTS tenant_integration (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES company(id),
                        service VARCHAR(50) NOT NULL,
                        access_token TEXT,
                        refresh_token_encrypted TEXT,
                        token_expiry_at TIMESTAMP,
                        status VARCHAR(20) DEFAULT 'connected',
                        last_error TEXT,
                        config_json JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );"""
                ]
            else:
                 results.append("<p>Using SQLite Fallback queries</p>")
                 queries = [
                    """CREATE TABLE IF NOT EXISTS drive_folder_template (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL REFERENCES company(id),
                        name VARCHAR(100) NOT NULL,
                        structure_json TEXT NOT NULL,
                        is_default BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );""",
                     """CREATE TABLE IF NOT EXISTS tenant_integration (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL REFERENCES company(id),
                        service VARCHAR(50) NOT NULL,
                        access_token TEXT,
                        refresh_token_encrypted TEXT,
                        token_expiry_at TIMESTAMP,
                        status VARCHAR(20) DEFAULT 'connected',
                        last_error TEXT,
                        config_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );""",
                    "ALTER TABLE lead ADD COLUMN diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                    "ALTER TABLE company ADD COLUMN features TEXT DEFAULT '{}';"
                ]

            with engine.connect() as conn:
                for q in queries:
                    try:
                        conn.execute(text(q))
                        results.append(f"<div style='color:green'>SUCCESS: {q[:30]}...</div>")
                    except Exception as e:
                        msg = str(e).lower()
                        if "already exists" in msg or "duplicate column" in msg:
                            results.append(f"<div style='color:orange'>SKIPPED (Exists): {q[:30]}...</div>")
                        else:
                            results.append(f"<div style='color:red'>ERROR: {q[:30]}... {str(e)}</div>")
                try:
                    conn.commit()
                    results.append("<h3><b>FINAL COMMIT SUCCESSFUL</b></h3>")
                except Exception as commit_e:
                     results.append(f"<h3><b>FINAL COMMIT FAILED: {commit_e}</b></h3>")

            return "".join(results)

    except Exception as e:
        import traceback
        return f"<h1>Fatal Error</h1><pre>{traceback.format_exc()}</pre>", 500

if __name__ == '__main__':
    app.run(debug=True)
