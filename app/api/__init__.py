from flask import Blueprint

# Create a Blueprint for API routes
api = Blueprint('api', __name__)

# Import routes so they get registered to the Blueprint
from app.api import routes
from app.api.users import routes
from app.api.expenses import routes
from app.api.expenses_lists import routes