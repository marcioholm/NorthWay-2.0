from flask import Blueprint, request, Response
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
    
    try:
        if request.method == 'GET':
            resp = requests.get(url, headers=headers, stream=True)
        else:
            resp = requests.request(
                method=request.method,
                url=url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                stream=True
            )

        # Exclude hop-by-hop headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return f"Proxy Error: {str(e)}", 502
