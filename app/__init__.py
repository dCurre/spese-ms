from flask import Flask
from app.api import api
from app.database import db
from config import Config
from flask_cors import CORS

def create_app():
    app = Flask(__name__)

    CORS(app)

    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        from app.database.list_type import ListType
        from app.database.expense_type import ExpenseType
        from app.database.user_role import UserRole
        from app.database.user import User
        from app.database.expenses_list import ExpensesList
        from app.database.expense import Expense
        from app.database.expenses_list_participant import ExpensesListParticipant

    app.register_blueprint(api, url_prefix='/api')

    return app
