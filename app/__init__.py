from flask import Flask
from app.api import api
from app.database import db
from config import Config

def create_app():
    app = Flask(__name__)  # Move this inside the function

    CORS(app)  # Enables CORS for all origins

    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(api, url_prefix='/api')

    with app.app_context():
        db.create_all()

    return app
