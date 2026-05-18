from flask import abort, request, jsonify
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from app.api import api
from app.database import db
from app.database.expense import Expense


@api.route('/expenses', methods=['GET'])
def get_expenses():
    expenses = Expense.query.options(joinedload(Expense.user)).order_by(Expense.id).all()
    return jsonify({
        "expenses": [
            {
                "id": e.id,
                "name": e.name,
                "amount": e.amount,
                "creation_date": e.creation_date,
                "owner": {
                    "id": e.user.id,
                    "name": e.user.name,
                    "surname": e.user.surname,
                    "email": e.user.email,
                    "profile_image": e.user.profile_image,
                    "paid_list_shown": e.user.paid_list_shown,
                },
                "update_date": e.update_date,
                "modified_by": e.modified_by,
                "expense_list_id": e.expense_list_id,
                "expense_date": e.expense_date
            }
            for e in expenses
        ]
    })

@api.route('/expenses/<int:expense_id>', methods=['GET'])
def get_expense(expense_id):
    e = Expense.query.options(joinedload(Expense.user)).filter_by(id=expense_id).first_or_404()
    return jsonify({
        "id": e.id,
        "name": e.name,
        "amount": e.amount,
        "creation_date": e.creation_date,
        "owner": {
            "id": e.user.id,
            "name": e.user.name,
            "surname": e.user.surname,
            "email": e.user.email,
            "profile_image": e.user.profile_image,
            "paid_list_shown": e.user.paid_list_shown,
        },
        "update_date": e.update_date,
        "modified_by": e.modified_by,
        "expense_list_id": e.expense_list_id,
        "expense_date": e.expense_date
    })

@api.route('/expenses', methods=['POST'])
def create_expense():
    data = request.get_json()
    expense = Expense(
        name=data.get('name'),
        amount=data.get('amount'),
        creation_date=datetime.now(timezone.utc),
        expense_owner_user_id=data['expense_owner_user_id'],
        expense_list_id=data['expense_list_id'],
        expense_date=datetime.fromisoformat(data['expense_date']),
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify({"id": expense.id}), 201

@api.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    return '', 204
