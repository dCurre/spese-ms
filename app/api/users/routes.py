from flask import abort, request, jsonify
from app.api import api
from app.database import db
from app.database.user import User

@api.route('/users', methods=['GET'])
def get_users():
    users = User.query.order_by(User.id).all()
    return jsonify({
        "users": [
            {
                "id": u.id,
                "name": u.name,
                "surname": u.surname,
                "email": u.email,
                "profile_image": u.profile_image,
                "paid_list_shown": u.paid_list_shown,
            }
            for u in users
        ]
    })

@api.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    u = User.query.get_or_404(user_id)
    return jsonify({
        "id": u.id,
        "name": u.name,
        "surname": u.surname,
        "email": u.email,
        "profile_image": u.profile_image,
        "paid_list_shown": u.paid_list_shown,
    })

@api.route('/users', methods=['POST'])
def create_user():
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
    return jsonify({"id": user.id}), 201

@api.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204
