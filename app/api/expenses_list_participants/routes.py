from flask import request, jsonify
from datetime import datetime, timezone
from app.api import api
from app.database import db
from app.database.expenses_list_participant import ExpensesListParticipant


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
            }
            for p in participants
        ]
    })


@api.route('/expenses-lists/<int:list_id>/participants', methods=['POST'])
def add_participant(list_id):
    data = request.get_json()
    participant = ExpensesListParticipant(
        expenses_list_id=list_id,
        user_id=data['user_id'],
        joined_at=datetime.now(timezone.utc),
    )
    db.session.add(participant)
    db.session.commit()
    return '', 201


@api.route('/expenses-lists/<int:list_id>/participants/<int:user_id>', methods=['DELETE'])
def remove_participant(list_id, user_id):
    participant = ExpensesListParticipant.query.filter_by(
        expenses_list_id=list_id,
        user_id=user_id
    ).first_or_404()
    db.session.delete(participant)
    db.session.commit()
    return '', 204
