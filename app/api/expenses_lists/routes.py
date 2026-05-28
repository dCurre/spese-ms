import traceback
from flask import abort, request, jsonify
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from app.api import api
from app.database import db
from app.database.expenses_list import ExpensesList
from app.database.list_type import ListType

@api.route('/expenses-lists', methods=['GET'])
def get_expenses_lists():
    show_paid = request.args.get('paid', default=None, type=lambda v: v.lower() == 'true')
    query = ExpensesList.query
    if show_paid is not None:
        query = query.filter_by(paid=show_paid)
    expenses_lists = query.options(joinedload(ExpensesList.list_type)).order_by(ExpensesList.id).all()
    return jsonify({
        "expenses_lists": [
            {
                "id": el.id,
                "name": el.name,
                "user_id": el.user_id,
                "paid": el.paid,
                "created_at": el.created_at,
                "list_type": el.list_type.name if el.list_type else "shared",
                "max_participants": el.list_type.max_participants if el.list_type else 8,
            }
            for el in expenses_lists
        ]
    })

@api.route('/expenses-lists/<int:list_id>', methods=['GET'])
def get_expenses_list(list_id):
    el = ExpensesList.query.options(joinedload(ExpensesList.list_type)).get_or_404(list_id)
    return jsonify({
        "id": el.id,
        "name": el.name,
        "user_id": el.user_id,
        "paid": el.paid,
        "created_at": el.created_at,
        "list_type": el.list_type.name if el.list_type else "shared",
        "max_participants": el.list_type.max_participants if el.list_type else 8,
        "participants": [
            {
                "user_id": p.user_id,
                "name": p.user.name,
                "surname": p.user.surname,
                "email": p.user.email,
                "profile_image": p.user.profile_image,
                "joined_at": p.joined_at,
                "is_guest": bool(p.user.is_guest),
            }
            for p in el.participants
        ]
    })

@api.route('/expenses-lists', methods=['POST'])
def create_expenses_list():
    try:
        data = request.get_json()
        type_name = data.get('list_type', 'shared')
        list_type = ListType.query.filter_by(name=type_name).first()
        expenses_list = ExpensesList(
            name=data.get('name'),
            user_id=data['user_id'],
            paid=data.get('paid', False),
            list_type_id=list_type.id if list_type else 1,
        )
        db.session.add(expenses_list)
        db.session.commit()
        return jsonify({"id": expenses_list.id, "message": "Lista creata"}), 201
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500

@api.route('/expenses-lists/<int:list_id>', methods=['PUT'])
def update_expenses_list(list_id):
    try:
        el = ExpensesList.query.get_or_404(list_id)
        data = request.get_json()
        if 'name' in data: el.name = data['name']
        if 'paid' in data: el.paid = data['paid']
        db.session.commit()
        return jsonify({"message": "Lista aggiornata"}), 200
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500

@api.route('/expenses-lists/<int:list_id>/transfer-owner', methods=['POST'])
def transfer_owner(list_id):
    try:
        data = request.get_json()
        new_owner_id = data.get('new_owner_id')
        current_owner_id = data.get('current_owner_id')
        if not new_owner_id or not current_owner_id:
            return jsonify({"error": "Parametri mancanti"}), 400

        el = ExpensesList.query.get_or_404(list_id)
        if el.user_id != current_owner_id:
            return jsonify({"error": "Non sei il proprietario della lista"}), 403

        from app.database.expenses_list_participant import ExpensesListParticipant
        from app.database.user import User as UserModel
        new_owner = UserModel.query.get(new_owner_id)
        if not new_owner or new_owner.is_guest:
            return jsonify({"error": "Un ospite non può essere proprietario di una lista"}), 400

        is_participant = ExpensesListParticipant.query.filter_by(
            expenses_list_id=list_id, user_id=new_owner_id
        ).first()
        if not is_participant:
            return jsonify({"error": "Il nuovo owner deve essere un partecipante"}), 400

        el.user_id = new_owner_id

        old_owner = ExpensesListParticipant.query.filter_by(
            expenses_list_id=list_id, user_id=current_owner_id
        ).first()
        if old_owner:
            db.session.delete(old_owner)

        db.session.commit()
        return jsonify({"message": "Ownership trasferita"}), 200
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/expenses-lists/<int:list_id>/balance', methods=['GET'])
def get_expenses_list_balance(list_id):
    try:
        from app.database.expense import Expense
        from sqlalchemy.orm import joinedload
        expenses = (
            Expense.query
            .options(joinedload(Expense.user))
            .filter_by(expense_list_id=list_id)
            .all()
        )
        map_pagato = {}
        for e in expenses:
            key = f"{e.user.name} {e.user.surname or ''}".strip()
            map_pagato[key] = map_pagato.get(key, 0) + float(e.amount)

        balance = []
        keys = list(map_pagato.keys())
        for buyer, buyer_paid in map_pagato.items():
            for receiver, receiver_paid in map_pagato.items():
                if buyer != receiver:
                    balance.append({
                        "buyer": buyer,
                        "receiver": receiver,
                        "toPay": round((receiver_paid - buyer_paid) / len(map_pagato), 2),
                    })
        return jsonify({
            "balance": balance,
            "totals": [{"name": k, "amount": round(v, 2)} for k, v in sorted(map_pagato.items())],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/expenses-lists/<int:list_id>', methods=['DELETE'])
def delete_expenses_list(list_id):
    try:
        expenses_list = ExpensesList.query.get_or_404(list_id)
        db.session.delete(expenses_list)
        db.session.commit()
        return jsonify({"message": "Lista eliminata"}), 200
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500
