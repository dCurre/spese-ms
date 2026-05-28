from flask import jsonify

from app.api import api
from version import __version__

@api.route('/')
def api_home():
    return jsonify({
        "message": "Spese-ms is up and running!",
        "version": __version__
    })
