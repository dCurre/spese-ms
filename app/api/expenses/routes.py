import traceback
from flask import abort, request, jsonify
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from app.api import api
from app.database import db
from app.database.expense import Expense
from app.database.expense_type import ExpenseType


def parse_date(date_str: str) -> datetime:
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(date_str)


def expense_to_dict(e, include_paid_list_shown=False):
    owner = {
        "id": e.user.id,
        "name": e.user.name,
        "surname": e.user.surname,
        "email": e.user.email,
        "profile_image": e.user.profile_image,
    }
    if include_paid_list_shown:
        owner["paid_list_shown"] = e.user.paid_list_shown
    return {
        "id": e.id,
        "name": e.name,
        "amount": e.amount,
        "created_at": e.created_at,
        "owner": owner,
        "updated_at": e.updated_at,
        "modified_by": e.modified_by,
        "expense_list_id": e.expense_list_id,
        "expense_date": e.expense_date,
        "expense_type_id": e.expense_type_id,
        "expense_type": e.expense_type.name if e.expense_type else None,
    }


@api.route('/expenses', methods=['GET'])
def get_expenses():
    expenses = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).order_by(Expense.id).all()
    return jsonify({"expenses": [expense_to_dict(e, include_paid_list_shown=True) for e in expenses]})


@api.route('/expenses/<int:expense_id>', methods=['GET'])
def get_expense(expense_id):
    e = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).filter_by(id=expense_id).first_or_404()
    return jsonify(expense_to_dict(e, include_paid_list_shown=True))


@api.route('/expenses', methods=['POST'])
def create_expense():
    try:
        data = request.get_json()
        expense = Expense(
            name=data.get('name'),
            amount=data.get('amount'),
            expense_owner_user_id=data['expense_owner_user_id'],
            expense_list_id=data['expense_list_id'],
            expense_date=parse_date(data['expense_date']),
            expense_type_id=data.get('expense_type_id'),
        )
        db.session.add(expense)
        db.session.commit()
        return jsonify({"id": expense.id, "message": "Spesa creata"}), 201
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    try:
        e = Expense.query.get_or_404(expense_id)
        data = request.get_json()
        if 'name' in data: e.name = data['name']
        if 'amount' in data: e.amount = data['amount']
        if 'expense_date' in data: e.expense_date = parse_date(data['expense_date'])
        if 'expense_owner_user_id' in data: e.expense_owner_user_id = data['expense_owner_user_id']
        if 'modified_by' in data: e.modified_by = data['modified_by']
        if 'expense_type_id' in data: e.expense_type_id = data['expense_type_id']
        e.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({"message": "Spesa aggiornata"}), 200
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/expenses/by-list/<int:list_id>', methods=['GET'])
def get_expenses_by_list(list_id):
    expenses = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).filter_by(expense_list_id=list_id).order_by(Expense.id).all()
    return jsonify({"expenses": [expense_to_dict(e) for e in expenses]})


@api.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    try:
        expense = Expense.query.get_or_404(expense_id)
        db.session.delete(expense)
        db.session.commit()
        return jsonify({"message": "Spesa eliminata"}), 200
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500
