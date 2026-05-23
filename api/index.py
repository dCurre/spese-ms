import sys
import os

# Assicura che la root del progetto sia nel path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from flask import request

app = create_app()

@app.before_request
def log_request():
    app.logger.warning(f">>> PATH: {request.path} | FULL: {request.full_path} | METHOD: {request.method}")
