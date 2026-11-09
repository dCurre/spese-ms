import os
import traceback
import logging
from datetime import datetime, date
from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException
from marshmallow import ValidationError as MarshmallowValidationError
from app.api import api
from app.database import db
from config import Config
from flask_cors import CORS
from app.exceptions import AppError


class ISOJSONProvider(DefaultJSONProvider):
    """Serializza datetime/date in ISO 8601 (es. '2026-11-09T15:18:22').

    Il default di Flask emette l'HTTP-date RFC 1123 ('Mon, 09 Nov 2026 ...'),
    non ISO: il delta sync usa server_time come prossimo `since` e ha bisogno
    di un formato ISO round-trippabile. Formato coerente su tutte le API.
    """

    @staticmethod
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)

logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.json = ISOJSONProvider(app)

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
        from app.database.measurement_unit import MeasurementUnit
        from app.database.product import Product
        from app.database.purchase import Purchase
        from app.database.heartbeat import Heartbeat
        db.create_all()

    app.register_blueprint(api, url_prefix='/api')

    return app
