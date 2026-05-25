import secrets
from flask import request, jsonify
from sqlalchemy.orm import joinedload
from app.api import api
from app.database import db
from app.database.shopping_list import ShoppingList, ShoppingItem, ShoppingCategory, ShoppingListParticipant


def _serialize_list(sl, include_items=False):
    all_items = sl.items or []
    data = {
        "id": sl.id,
        "name": sl.name,
        "owner_id": sl.owner_id,
        "list_type": sl.list_type,
        "completed": sl.completed,
        "starred": sl.starred,
        "invite_token": sl.invite_token,
        "created_at": sl.created_at,
        "items_count": len(all_items),
        "checked_count": sum(1 for i in all_items if i.checked),
        "participants": (
            [
                {
                    "user_id": sl.owner.id,
                    "shopping_list_id": sl.id,
                    "name": sl.owner.name,
                    "surname": sl.owner.surname,
                    "email": sl.owner.email,
                    "profile_image": sl.owner.profile_image,
                    "joined_at": sl.created_at,
                }
            ] if sl.owner else []
        ) + [
            {
                "user_id": p.user_id,
                "shopping_list_id": p.shopping_list_id,
                "name": p.user.name,
                "surname": p.user.surname,
                "email": p.user.email,
                "profile_image": p.user.profile_image,
                "joined_at": p.joined_at,
            }
            for p in (sl.participants or [])
        ],
    }
    if include_items:
        # Serializza categorie con i loro item
        categories = sorted(sl.categories or [], key=lambda c: c.sort_order)
        data["categories"] = [
            {
                "id": c.id,
                "shopping_list_id": c.shopping_list_id,
                "name": c.name,
                "sort_order": c.sort_order,
                "created_at": c.created_at,
                "items": [
                    {
                        "id": i.id,
                        "shopping_list_id": i.shopping_list_id,
                        "category_id": i.category_id,
                        "name": i.name,
                        "quantity": i.quantity,
                        "checked": i.checked,
                        "sort_order": i.sort_order,
                        "created_at": i.created_at,
                    }
                    for i in sorted(c.items, key=lambda i: i.sort_order)
                ],
            }
            for c in categories
        ]
        # Item senza categoria
        uncategorized = sorted(
            [i for i in all_items if i.category_id is None],
            key=lambda i: i.sort_order
        )
        data["items"] = [
            {
                "id": i.id,
                "shopping_list_id": i.shopping_list_id,
                "category_id": None,
                "name": i.name,
                "quantity": i.quantity,
                "checked": i.checked,
                "sort_order": i.sort_order,
                "created_at": i.created_at,
            }
            for i in uncategorized
        ]
    return data


@api.route('/shopping-lists/by-user/<int:user_id>', methods=['GET'])
def get_shopping_lists_by_user(user_id):
    owned = ShoppingList.query.options(
        joinedload(ShoppingList.owner),
        joinedload(ShoppingList.items),
        joinedload(ShoppingList.categories).joinedload(ShoppingCategory.items),
        joinedload(ShoppingList.participants).joinedload(ShoppingListParticipant.user)
    ).filter_by(owner_id=user_id).all()

    shared_ids = db.session.query(ShoppingListParticipant.shopping_list_id).filter_by(user_id=user_id)
    shared = ShoppingList.query.options(
        joinedload(ShoppingList.owner),
        joinedload(ShoppingList.items),
        joinedload(ShoppingList.categories).joinedload(ShoppingCategory.items),
        joinedload(ShoppingList.participants).joinedload(ShoppingListParticipant.user)
    ).filter(ShoppingList.id.in_(shared_ids), ShoppingList.owner_id != user_id).all()

    all_lists = owned + shared
    return jsonify({"shopping_lists": [_serialize_list(sl) for sl in all_lists]})


@api.route('/shopping-lists/<int:list_id>', methods=['GET'])
def get_shopping_list(list_id):
    sl = ShoppingList.query.options(
        joinedload(ShoppingList.owner),
        joinedload(ShoppingList.items),
        joinedload(ShoppingList.categories).joinedload(ShoppingCategory.items),
        joinedload(ShoppingList.participants).joinedload(ShoppingListParticipant.user)
    ).get_or_404(list_id)
    return jsonify(_serialize_list(sl, include_items=True))


@api.route('/shopping-lists', methods=['POST'])
def create_shopping_list():
    try:
        data = request.get_json()
        sl = ShoppingList(
            name=data['name'],
            owner_id=data['owner_id'],
            list_type=data.get('list_type', 'personal'),
            completed=data.get('completed', False),
        )
        db.session.add(sl)
        db.session.commit()
        return jsonify({"id": sl.id, "message": "Checklist creata"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-lists/<int:list_id>', methods=['PUT'])
def update_shopping_list(list_id):
    try:
        sl = ShoppingList.query.get_or_404(list_id)
        data = request.get_json()
        if 'name' in data: sl.name = data['name']
        if 'completed' in data: sl.completed = data['completed']
        if 'list_type' in data: sl.list_type = data['list_type']
        if 'starred' in data: sl.starred = data['starred']
        db.session.commit()
        return jsonify({"message": "Checklist aggiornata"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-lists/<int:list_id>', methods=['DELETE'])
def delete_shopping_list(list_id):
    try:
        sl = ShoppingList.query.get_or_404(list_id)
        db.session.delete(sl)
        db.session.commit()
        return jsonify({"message": "Checklist eliminata"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-lists/<int:list_id>/invite-token', methods=['POST'])
def generate_invite_token(list_id):
    try:
        sl = ShoppingList.query.get_or_404(list_id)
        if not sl.invite_token:
            sl.invite_token = secrets.token_urlsafe(32)
            db.session.commit()
        return jsonify({"invite_token": sl.invite_token}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-lists/<int:list_id>/invite-token', methods=['DELETE'])
def revoke_invite_token(list_id):
    try:
        sl = ShoppingList.query.get_or_404(list_id)
        sl.invite_token = None
        db.session.commit()
        return jsonify({"message": "Link revocato"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-lists/join/<string:token>', methods=['POST'])
def join_by_token(token):
    try:
        sl = ShoppingList.query.filter_by(invite_token=token).first_or_404()
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"error": "user_id mancante"}), 400

        if sl.owner_id == user_id:
            return jsonify({"id": sl.id, "message": "Sei il proprietario"}), 200

        existing = ShoppingListParticipant.query.filter_by(
            shopping_list_id=sl.id, user_id=user_id
        ).first()
        if not existing:
            p = ShoppingListParticipant(shopping_list_id=sl.id, user_id=user_id)
            db.session.add(p)
            db.session.commit()

        return jsonify({"id": sl.id, "message": "Aggiunto alla lista"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-lists/<int:list_id>/transfer-ownership', methods=['POST'])
def transfer_ownership(list_id):
    try:
        sl = ShoppingList.query.get_or_404(list_id)
        data = request.get_json()
        new_owner_id = data.get('new_owner_id')
        old_owner_id = data.get('old_owner_id')
        if not new_owner_id or not old_owner_id:
            return jsonify({"error": "new_owner_id e old_owner_id obbligatori"}), 400
        if sl.owner_id != old_owner_id:
            return jsonify({"error": "Non sei il proprietario"}), 403
        existing = ShoppingListParticipant.query.filter_by(
            shopping_list_id=list_id, user_id=new_owner_id
        ).first()
        if not existing:
            return jsonify({"error": "Il nuovo owner deve essere un partecipante"}), 400
        sl.owner_id = new_owner_id
        db.session.delete(existing)
        old_entry = ShoppingListParticipant.query.filter_by(
            shopping_list_id=list_id, user_id=old_owner_id
        ).first()
        if old_entry:
            db.session.delete(old_entry)
        db.session.commit()
        return jsonify({"message": "Ownership trasferita"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-lists/<int:list_id>/participants', methods=['POST'])
def add_shopping_list_participant(list_id):
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"error": "user_id mancante"}), 400
        existing = ShoppingListParticipant.query.filter_by(
            shopping_list_id=list_id, user_id=user_id
        ).first()
        if existing:
            return jsonify({"message": "Già partecipante"}), 200
        p = ShoppingListParticipant(shopping_list_id=list_id, user_id=user_id)
        db.session.add(p)
        db.session.commit()
        return jsonify({"message": "Partecipante aggiunto"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-lists/<int:list_id>/participants/<int:user_id>', methods=['DELETE'])
def remove_shopping_list_participant(list_id, user_id):
    try:
        p = ShoppingListParticipant.query.filter_by(
            shopping_list_id=list_id, user_id=user_id
        ).first_or_404()
        db.session.delete(p)
        db.session.commit()
        return jsonify({"message": "Partecipante rimosso"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500
