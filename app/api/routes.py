from flask import jsonify

from app.api import api

# Define the home route
@api.route('/')
def api_home():
    return jsonify({"message": "Spese-ms is up and running!"})
