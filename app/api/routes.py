from flask import jsonify

from app.api import api

APP_VERSION = "1.0.0"

# Define the home route
@api.route('/')
def api_home():
    return jsonify({
        "message": "Spese-ms is up and running!",
        "version": APP_VERSION
    })
