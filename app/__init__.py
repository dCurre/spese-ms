import os
import traceback
import logging
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from marshmallow import ValidationError as MarshmallowValidationError
from app.api import api
from app.database import db
from config import Config
from flask_cors import CORS
from app.exceptions import AppError

logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)

    raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    if raw_origins:
        allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    else:
        allowed_origins = "*"
    CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=False)

    app.config.from_object(Config)

    db.init_app(app)

    @app.errorhandler(AppError)
    def handle_app_error(e):
        db.session.rollback()
        return jsonify({"error": e.message}), e.status_code

    @app.errorhandler(MarshmallowValidationError)
    def handle_validation_error(e):
        return jsonify({"error": e.messages}), 400

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return jsonify({"error": e.description}), e.code

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        logger.error("Unhandled exception on %s %s\n%s", request.method, request.path, traceback.format_exc())
        db.session.rollback()
        return jsonify({"error": "Errore interno del server"}), 500

    with app.app_context():
        from app.database.list_type import ListType
        from app.database.expense_type import ExpenseType
        from app.database.user_role import UserRole
        from app.database.user import User
        from app.database.expenses_list import ExpensesList
        from app.database.expense import Expense
        from app.database.expenses_list_participant import ExpensesListParticipant
        from app.database.shopping_list import ShoppingList, ShoppingItem, ShoppingListParticipant
        db.create_all()

    app.register_blueprint(api, url_prefix='/api')

    return app
