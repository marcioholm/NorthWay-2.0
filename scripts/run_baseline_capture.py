import os
import sys
import time
import subprocess
import signal
import urllib.request

db_path = os.path.abspath('crm.db')
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
os.environ['SECRET_KEY'] = 'dev-secret'
os.environ['RATELIMIT_ENABLED'] = 'False'
os.environ['PORT'] = '5055'

server_cmd = [
    sys.executable,
    '-c',
    '''
import os, sys
sys.path.insert(0, os.path.abspath('northway_crm'))
from app import create_app
app = create_app()
app.run(host='127.0.0.1', port=5055, debug=False)
'''
]

print("Starting Flask server on port 5055...")
server_proc = subprocess.Popen(server_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    # Wait for server to be responsive
    started = False
    for i in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:5055/login', timeout=2) as resp:
                if resp.status == 200:
                    started = True
                    break
        except Exception:
            time.sleep(0.5)

    if not started:
        raise RuntimeError("Flask server failed to start within timeout.")

    print("Flask server is up! Running capture_baseline.cjs...")
    script_path = os.path.abspath('scripts/capture_baseline.cjs')
    node_cmd = ['node', script_path]
    env = os.environ.copy()
    env['NODE_PATH'] = os.path.abspath('northway_crm/node_modules')
    res = subprocess.run(node_cmd, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"Puppeteer script failed with code {res.returncode}")

    print("Capture script completed successfully!")

finally:
    print("Terminating Flask server...")
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_proc.kill()
