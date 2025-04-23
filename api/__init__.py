# /api/__init__.py
from flask import Blueprint

# Create a Blueprint for API routes
api_bp = Blueprint('api', __name__)

# Import routes and resources
from . import routes
