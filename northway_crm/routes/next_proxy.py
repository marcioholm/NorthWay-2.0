from flask import Blueprint, request, Response, make_response
import requests

next_proxy_bp = Blueprint('next_proxy', __name__)

NEXT_APP_URL = "https://northway-crm-next.vercel.app"

@next_proxy_bp.route('/formularios', defaults={'path': ''})
@next_proxy_bp.route('/formularios/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_formularios(path):
    return proxy_request(f"/formularios/{path}")

@next_proxy_bp.route('/api/forms', defaults={'path': ''})
@next_proxy_bp.route('/api/forms/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_api_forms(path):
    return proxy_request(f"/api/forms/{path}")

@next_proxy_bp.route('/_next', defaults={'path': ''})
@next_proxy_bp.route('/_next/<path:path>', methods=['GET'])
def proxy_next_static(path):
    return proxy_request(f"/_next/{path}")

def proxy_request(path):
    url = f"{NEXT_APP_URL}{path}"
    if request.query_string:
        url += f"?{request.query_string.decode('utf-8')}"
    
    # Mirror headers for consistency (excluding Host)
    headers = {key: value for (key, value) in request.headers if key.lower() != 'host'}
    
    # Force no compression for upstream if we want requests to handle it reliably
    headers['Accept-Encoding'] = 'identity'
    
    try:
        if request.method == 'GET':
            resp = requests.get(url, headers=headers, allow_redirects=False)
        else:
            resp = requests.request(
                method=request.method,
                url=url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False
            )

        # Create Flask response
        response = make_response(resp.content, resp.status_code)
        
        # Forward critical headers
        if 'Content-Type' in resp.headers:
             response.headers['Content-Type'] = resp.headers['Content-Type']
        
        # EXCLUDE transfer-encoding and content-encoding
        # This allows Flask/Vercel to handle downstream compression correctly
        return response
        
    except Exception as e:
        return f"Proxy Error: {str(e)}", 502
