from flask import abort, request, jsonify
from datetime import datetime, timezone
from app.api import api
from app.database import db
from app.database.expenses_list import ExpensesList

@api.route('/expenses-lists', methods=['GET'])
def get_expenses_lists():
    show_paid = request.args.get('paid', default=None, type=lambda v: v.lower() == 'true')
    query = ExpensesList.query
    if show_paid is not None:
        query = query.filter_by(paid=show_paid)
    expenses_lists = query.order_by(ExpensesList.id).all()
    return jsonify({
        "expenses_lists": [
            {
                "id": el.id,
                "name": el.name,
                "user_id": el.user_id,
                "paid": el.paid,
                "created_at": el.created_at,
            }
            for el in expenses_lists
        ]
    })

@api.route('/expenses-lists/<int:list_id>', methods=['GET'])
def get_expenses_list(list_id):
    el = ExpensesList.query.get_or_404(list_id)
    return jsonify({
        "id": el.id,
        "name": el.name,
        "user_id": el.user_id,
        "paid": el.paid,
        "created_at": el.created_at,
        "participants": [
            {
                "user_id": p.user_id,
                "name": p.user.name,
                "surname": p.user.surname,
                "email": p.user.email,
                "profile_image": p.user.profile_image,
                "joined_at": p.joined_at,
            }
            for p in el.participants
        ]
    })

@api.route('/expenses-lists', methods=['POST'])
def create_expenses_list():
    data = request.get_json()
    expenses_list = ExpensesList(
        name=data.get('name'),
        user_id=data['user_id'],
        paid=data.get('paid', False),
    )
    db.session.add(expenses_list)
    db.session.commit()
    return jsonify({"id": expenses_list.id}), 201

@api.route('/expenses-lists/<int:list_id>', methods=['PUT'])
def update_expenses_list(list_id):
    el = ExpensesList.query.get_or_404(list_id)
    data = request.get_json()
    if 'name' in data: el.name = data['name']
    if 'paid' in data: el.paid = data['paid']
    db.session.commit()
    return '', 204

@api.route('/expenses-lists/<int:list_id>', methods=['DELETE'])
def delete_expenses_list(list_id):
    expenses_list = ExpensesList.query.get_or_404(list_id)
    db.session.delete(expenses_list)
    db.session.commit()
    return '', 204
