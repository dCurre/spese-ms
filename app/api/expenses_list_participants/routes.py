from flask import request, jsonify
from datetime import datetime, timezone
from app.api import api
from app.database import db
from app.database.expenses_list_participant import ExpensesListParticipant
from app.exceptions import NotFoundError
from app.audit import log_audit


@api.route('/expenses-lists/<int:list_id>/participants', methods=['GET'])
def get_participants(list_id):
    participants = ExpensesListParticipant.query.filter_by(expenses_list_id=list_id).all()
    return jsonify({
        "participants": [
            {
                "user_id": p.user_id,
                "expenses_list_id": p.expenses_list_id,
                "joined_at": p.joined_at,
                "name": p.user.name,
                "surname": p.user.surname,
                "email": p.user.email,
                "profile_image": p.user.profile_image,
                "is_guest": bool(p.user.is_guest),
            }
            for p in participants
        ]
    })


@api.route('/expenses-lists/<int:list_id>/participants', methods=['POST'])
def add_participant(list_id):
    data = request.get_json() or {}
    participant = ExpensesListParticipant(
        expenses_list_id=list_id,
        user_id=data['user_id'],
        joined_at=datetime.now(timezone.utc),
    )
    db.session.add(participant)
    db.session.commit()
    log_audit("add_participant", list_id=list_id, user_id=data['user_id'])
    return jsonify({"message": "Partecipante aggiunto"}), 201


@api.route('/expenses-lists/<int:list_id>/participants/<int:user_id>', methods=['DELETE'])
def remove_participant(list_id, user_id):
    participant = ExpensesListParticipant.query.filter_by(
        expenses_list_id=list_id,
        user_id=user_id
    ).first_or_404()
    db.session.delete(participant)
    db.session.commit()
    log_audit("remove_participant", list_id=list_id, user_id=user_id)
    return jsonify({"message": "Partecipante rimosso"}), 200


@api.route('/expenses-lists/<int:list_id>/participants/<int:user_id>/guest', methods=['DELETE'])
def remove_guest_participant(list_id, user_id):
    from app.database.user import User
    from app.database.expense import Expense
    guest = User.query.filter_by(id=user_id, is_guest=True).first_or_404()

    placeholder = User.query.filter_by(email='deleted@system.local').first()
    if not placeholder:
        raise NotFoundError("Utente placeholder non trovato")

    Expense.query.filter_by(
        expense_list_id=list_id,
        expense_owner_user_id=user_id
    ).update({"expense_owner_user_id": placeholder.id})

    participant = ExpensesListParticipant.query.filter_by(
        expenses_list_id=list_id,
        user_id=user_id
    ).first_or_404()
    db.session.delete(participant)
    db.session.delete(guest)
    db.session.commit()
    log_audit("remove_guest_participant", list_id=list_id, guest_user_id=user_id)
    return jsonify({"message": "Ospite rimosso"}), 200
