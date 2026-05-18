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

@api.route('/users/by-email/<string:email>', methods=['GET'])
def get_user_by_email(email):
    u = User.query.filter_by(email=email).first_or_404()
    return jsonify({
        "id": u.id,
        "name": u.name,
        "surname": u.surname,
        "email": u.email,
        "profile_image": u.profile_image,
        "paid_list_shown": u.paid_list_shown,
    })

@api.route('/users/by-email/<string:email>/expenses-lists', methods=['GET'])
def get_user_expenses_lists_by_email(email):
    u = User.query.filter_by(email=email).first_or_404()
    return jsonify({
        "user": {
            "id": u.id,
            "name": u.name,
            "surname": u.surname,
            "email": u.email,
            "profile_image": u.profile_image,
            "paid_list_shown": u.paid_list_shown,
        },
        "expenses_lists": [
            {
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
            }
            for el in u.expenses_lists
        ]
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

@api.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    u = User.query.get_or_404(user_id)
    data = request.get_json()
    if 'name' in data: u.name = data['name']
    if 'surname' in data: u.surname = data['surname']
    if 'email' in data: u.email = data['email']
    if 'profile_image' in data: u.profile_image = data['profile_image']
    if 'paid_list_shown' in data: u.paid_list_shown = data['paid_list_shown']
    db.session.commit()
    return '', 204

@api.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204
