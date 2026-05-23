from app import create_app
from flask import request, jsonify

app = create_app()

@app.route('/debug')
def debug():
    routes = [str(r) for r in app.url_map.iter_rules()]
    return jsonify({
        "path": request.path,
        "full_path": request.full_path,
        "url": request.url,
        "environ_path": request.environ.get('PATH_INFO'),
        "script_name": request.environ.get('SCRIPT_NAME'),
        "registered_routes": sorted(routes),
    })
