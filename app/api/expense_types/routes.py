from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.expense_type import ExpenseType

PROTECTED_DELETE_IDS = {1}  # Altro non eliminabile


@api.route('/expense-types', methods=['GET'])
def get_expense_types():
    types = ExpenseType.query.all()
    protected = [t for t in types if t.id in PROTECTED_DELETE_IDS]
    others = sorted([t for t in types if t.id not in PROTECTED_DELETE_IDS], key=lambda t: t.name)
    ordered = protected + others
    return jsonify({"expense_types": [{"id": t.id, "name": t.name, "protected": t.id in PROTECTED_DELETE_IDS} for t in ordered]})


@api.route('/expense-types', methods=['POST'])
def create_expense_type():
    try:
        data = request.get_json()
        t = ExpenseType(name=data['name'])
        db.session.add(t)
        db.session.commit()
        return jsonify({"id": t.id, "message": "Tipologia creata"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/expense-types/<int:type_id>', methods=['PUT'])
def update_expense_type(type_id):
    try:
        t = ExpenseType.query.get_or_404(type_id)
        data = request.get_json()
        if 'name' in data:
            t.name = data['name']
        db.session.commit()
        return jsonify({"message": "Tipologia aggiornata"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/expense-types/<int:type_id>', methods=['DELETE'])
def delete_expense_type(type_id):
    if type_id in PROTECTED_DELETE_IDS:
        return jsonify({"error": "Tipologia non eliminabile", "code": 403}), 403
    try:
        t = ExpenseType.query.get_or_404(type_id)
        db.session.delete(t)
        db.session.commit()
        return jsonify({"message": "Tipologia eliminata"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500
