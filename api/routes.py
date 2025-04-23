# /api/routes.py
from flask import jsonify
from . import api_bp

# Define the home route
@api_bp.route('/')
def api_home():
    return jsonify({"message": "Spese-ms is up and running!"})

# Define other routes and link them to resources
@api_bp.route('/greet/<name>', methods=['GET'])
def greet_user(name):
    return jsonify({"message": f"Hello, {name}!"})
