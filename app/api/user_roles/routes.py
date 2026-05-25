import traceback
from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.user_role import UserRole

PROTECTED_IDS = {1, 2, 3}  # superadmin, admin, user non modificabili

# Gerarchia: valore più basso = ruolo più alto
ROLE_HIERARCHY = {1: 0, 2: 1, 3: 2}  # superadmin > admin > user


@api.route('/user-roles', methods=['GET'])
def get_user_roles():
    roles = UserRole.query.all()
    protected = sorted([r for r in roles if r.id in PROTECTED_IDS], key=lambda r: r.id)
    others = sorted([r for r in roles if r.id not in PROTECTED_IDS], key=lambda r: r.name)
    ordered = protected + others
    return jsonify({"user_roles": [{"id": r.id, "name": r.name, "protected": r.id in PROTECTED_IDS} for r in ordered]})


@api.route('/user-roles', methods=['POST'])
def create_user_role():
    try:
        data = request.get_json()
        role = UserRole(name=data['name'])
        db.session.add(role)
        db.session.commit()
        return jsonify({"id": role.id, "message": "Ruolo creato"}), 201
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/user-roles/<int:role_id>', methods=['PUT'])
def update_user_role(role_id):
    if role_id in PROTECTED_IDS:
        return jsonify({"error": "Ruolo non modificabile", "code": 403}), 403
    try:
        role = UserRole.query.get_or_404(role_id)
        data = request.get_json()
        if 'name' in data:
            role.name = data['name']
        db.session.commit()
        return jsonify({"message": "Ruolo aggiornato"}), 200
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/user-roles/<int:role_id>', methods=['DELETE'])
def delete_user_role(role_id):
    if role_id in PROTECTED_IDS:
        return jsonify({"error": "Ruolo non eliminabile", "code": 403}), 403
    try:
        role = UserRole.query.get_or_404(role_id)
        db.session.delete(role)
        db.session.commit()
        return jsonify({"message": "Ruolo eliminato"}), 200
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500
