from flask import request, jsonify
from datetime import datetime
from sqlalchemy.orm import joinedload
from app.api import api
from app.database import db
from app.database.expense import Expense
from app.database.expense_type import ExpenseType
from app.exceptions import ValidationError
from app.schemas import parse_body, CreateExpenseSchema


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
        "client_id": e.client_id,
        "name": e.name,
        "amount": e.amount,
        "created_at": e.created_at,
        "owner": owner,
        "updated_at": e.updated_at,
        "deleted": e.deleted,
        "modified_by": e.modified_by,
        "expense_list_id": e.expense_list_id,
        "expense_date": e.expense_date,
        "expense_type_id": e.expense_type_id,
        "expense_type": e.expense_type.name if e.expense_type else None,
    }


@api.route('/expenses', methods=['GET'])
def get_expenses():
    expenses = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).filter_by(deleted=False).order_by(Expense.id).all()
    return jsonify({"expenses": [expense_to_dict(e, include_paid_list_shown=True) for e in expenses]})


@api.route('/expenses/<int:expense_id>', methods=['GET'])
def get_expense(expense_id):
    e = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).filter_by(id=expense_id, deleted=False).first_or_404()
    return jsonify(expense_to_dict(e, include_paid_list_shown=True))


@api.route('/expenses', methods=['POST'])
def create_expense():
    data = parse_body(CreateExpenseSchema)
    client_id = data.get('client_id')

    # Create idempotente: client_id gia' visto nella stessa lista -> update.
    existing = None
    if client_id:
        existing = Expense.query.filter_by(
            expense_list_id=data['expense_list_id'], client_id=client_id
        ).first()
    if existing:
        existing.name = data['name']
        existing.amount = data['amount']
        existing.expense_owner_user_id = data['expense_owner_user_id']
        existing.expense_date = parse_date(data['expense_date'])
        existing.expense_type_id = data.get('expense_type_id')
        existing.deleted = False
        db.session.commit()
        return jsonify({"id": existing.id, "client_id": existing.client_id, "message": "Spesa aggiornata"}), 200

    expense = Expense(
        name=data['name'],
        amount=data['amount'],
        expense_owner_user_id=data['expense_owner_user_id'],
        expense_list_id=data['expense_list_id'],
        expense_date=parse_date(data['expense_date']),
        expense_type_id=data.get('expense_type_id'),
        client_id=client_id,
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify({"id": expense.id, "client_id": expense.client_id, "message": "Spesa creata"}), 201


@api.route('/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    e = Expense.query.filter_by(id=expense_id, deleted=False).first_or_404()
    data = request.get_json() or {}
    if 'name' in data: e.name = data['name']
    if 'amount' in data: e.amount = data['amount']
    if 'expense_date' in data: e.expense_date = parse_date(data['expense_date'])
    if 'expense_owner_user_id' in data: e.expense_owner_user_id = data['expense_owner_user_id']
    if 'modified_by' in data: e.modified_by = data['modified_by']
    if 'expense_type_id' in data: e.expense_type_id = data['expense_type_id']
    # updated_at e' gestito automaticamente dal trigger DB set_updated_at().
    db.session.commit()
    return jsonify({"message": "Spesa aggiornata"}), 200


@api.route('/expenses/by-list/<int:list_id>', methods=['GET'])
def get_expenses_by_list(list_id):
    expenses = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).filter_by(expense_list_id=list_id, deleted=False).order_by(Expense.id).all()
    return jsonify({"expenses": [expense_to_dict(e) for e in expenses]})


@api.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    # Soft-delete: marca deleted=true (updated_at aggiornato dal trigger DB).
    expense = Expense.query.filter_by(id=expense_id, deleted=False).first_or_404()
    expense.deleted = True
    db.session.commit()
    return jsonify({"message": "Spesa eliminata"}), 200


@api.route('/expenses/bulk-delete', methods=['POST'])
def bulk_delete_expenses():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids:
        raise ValidationError("ids mancante o vuoto")
    # Soft-delete di piu' spese (nessuna rimozione fisica).
    deleted = Expense.query.filter(Expense.id.in_(ids), Expense.deleted == False) \
        .update({'deleted': True}, synchronize_session=False)
    db.session.commit()
    return jsonify({"deleted": deleted, "message": f"{deleted} spese eliminate"}), 200
