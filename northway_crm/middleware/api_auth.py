import functools
import time
import uuid
from flask import request, g, jsonify, current_app
from services.integrations_service import IntegrationsService

def api_key_required(required_scopes=None):
    """
    Decorator for API Key authentication.
    - Extracts `X-API-Key` from headers.
    - Verifies the key and status.
    - Sets `g.company_id` and `g.api_key_id`.
    - Validates required scopes if provided.
    - Logs the inbound API call.
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            request_id = str(uuid.uuid4())
            api_key_str = request.headers.get('X-API-Key')
            
            if not api_key_str:
                return jsonify({
                    "success": False, 
                    "error": "Missing X-API-Key header",
                    "request_id": request_id
                }), 401

            api_key = IntegrationsService.verify_api_key(api_key_str)
            
            if not api_key:
                return jsonify({
                    "success": False, 
                    "error": "Invalid or inactive API Key",
                    "request_id": request_id
                }), 401

            # Check Scopes
            if required_scopes:
                user_scopes = api_key.scopes or []
                missing = [s for s in required_scopes if s not in user_scopes and '*' not in user_scopes]
                if missing:
                    return jsonify({
                        "success": False, 
                        "error": f"Insufficient permissions. Missing: {', '.join(missing)}",
                        "request_id": request_id
                    }), 403

            # Set Context for the request
            g.company_id = api_key.company_id
            g.api_key_id = api_key.id
            g.scopes = api_key.scopes
            g.request_id = request_id
            
            # Execute original function
            response = None
            status_code = 200
            error_msg = None
            
            try:
                result = f(*args, **kwargs)
                
                # Handle Flask return types (jsonify object or (json, status))
                if isinstance(result, tuple):
                    response_obj, status_code = result
                else:
                    response_obj = result
                
                # Attempt to extract data from response for logging
                if hasattr(response_obj, 'get_json'):
                    response = response_obj.get_json()
                elif isinstance(response_obj, dict):
                    response = response_obj
                else:
                    response = str(response_obj)[:1000]
                    
                return result
            except Exception as e:
                error_msg = str(e)
                status_code = 500
                import traceback
                traceback.print_exc()
                return jsonify({
                    "success": False, 
                    "error": "Internal server error during integration call", 
                    "msg": error_msg,
                    "request_id": request_id
                }), 500
            finally:
                # Execution Time
                execution_time = int((time.time() - start_time) * 1000)
                
                # Log Inbound Activity (Audit)
                IntegrationsService.log_activity(
                    company_id=api_key.company_id,
                    type='inbound_api',
                    endpoint=request.path,
                    method=request.method,
                    status_code=status_code,
                    req_payload=request.json if request.is_json else request.form,
                    res_payload=response,
                    error=error_msg,
                    execution_time=execution_time,
                    request_id=request_id
                )

        return decorated_function
    return decorator
