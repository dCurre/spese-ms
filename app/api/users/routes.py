from flask import abort, request, jsonify
from sqlalchemy.orm import joinedload
from app.api import api
from app.database import db
from app.database.user import User
from app.database.user_role import UserRole
from app.database.expenses_list import ExpensesList


def user_to_dict(u):
    return {
        "id": u.id,
        "name": u.name,
        "surname": u.surname,
        "email": u.email,
        "profile_image": u.profile_image,
        "paid_list_shown": u.paid_list_shown,
        "role": u.role.name if u.role else None,
    }


def user_query():
    return User.query.options(joinedload(User.role))


@api.route('/users', methods=['GET'])
def get_users():
    users = user_query().order_by(User.id).all()
    return jsonify({"users": [user_to_dict(u) for u in users]})


@api.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    u = user_query().filter_by(id=user_id).first_or_404()
    return jsonify(user_to_dict(u))


@api.route('/users/by-email/<string:email>', methods=['GET'])
def get_user_by_email(email):
    u = user_query().filter_by(email=email).first_or_404()
    return jsonify(user_to_dict(u))


@api.route('/users/by-email/<string:email>/expenses-lists', methods=['GET'])
def get_user_expenses_lists_by_email(email):
    u = user_query().filter_by(email=email).first_or_404()
    expenses_lists = (
        ExpensesList.query
        .filter_by(user_id=u.id)
        .options(joinedload(ExpensesList.list_type))
        .order_by(ExpensesList.id)
        .all()
    )
    return jsonify({
        "user": user_to_dict(u),
        "expenses_lists": [
            {
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
                    }
                    for p in el.participants
                ]
            }
            for el in expenses_lists
        ]
    })


@api.route('/users', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        user = User(
            name=data.get('name'),
            surname=data.get('surname'),
            email=data.get('email'),
            profile_image=data.get('profile_image'),
            paid_list_shown=data.get('paid_list_shown', True),
        )
        db.session.add(user)
        db.session.commit()
        return jsonify({"id": user.id, "message": "Utente creato"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        u = user_query().filter_by(id=user_id).first_or_404()
        data = request.get_json()

        if 'role_id' in data:
            caller_email = data.get('caller_email')
            if caller_email:
                caller = user_query().filter_by(email=caller_email).first()
                if not caller:
                    return jsonify({"error": "Caller non trovato", "code": 403}), 403

                # Non puoi modificare te stesso
                if caller.id == u.id:
                    return jsonify({"error": "Non puoi modificare il tuo stesso ruolo", "code": 403}), 403

                caller_role_id = caller.role_id
                target_role_id = u.role_id
                new_role_id = int(data['role_id'])

                # ROLE_HIERARCHY: id ruolo → livello (1=superadmin, 2=admin, 3=user)
                # superadmin può assegnare tutto; admin può assegnare solo admin(2) e user(3)
                if caller_role_id == 2:  # admin
                    if target_role_id == 1:  # target è superadmin
                        return jsonify({"error": "Non puoi modificare un superadmin", "code": 403}), 403
                    if new_role_id == 1:  # vuole assegnare superadmin
                        return jsonify({"error": "Non puoi assegnare il ruolo superadmin", "code": 403}), 403
                elif caller_role_id != 1:  # né superadmin né admin
                    return jsonify({"error": "Non hai i permessi", "code": 403}), 403

        if 'name' in data: u.name = data['name']
        if 'surname' in data: u.surname = data['surname']
        if 'email' in data: u.email = data['email']
        if 'profile_image' in data: u.profile_image = data['profile_image']
        if 'paid_list_shown' in data: u.paid_list_shown = data['paid_list_shown']
        if 'role_id' in data: u.role_id = data['role_id']
        db.session.commit()
        return jsonify({"message": "Utente aggiornato"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "Utente eliminato"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500
