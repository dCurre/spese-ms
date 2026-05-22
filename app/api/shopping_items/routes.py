from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.shopping_list import ShoppingItem


@api.route('/shopping-items', methods=['POST'])
def create_shopping_item():
    try:
        data = request.get_json()
        item = ShoppingItem(
            shopping_list_id=data['shopping_list_id'],
            name=data['name'],
            quantity=data.get('quantity'),
            checked=data.get('checked', False),
            sort_order=data.get('sort_order', 0),
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({"id": item.id, "message": "Articolo aggiunto"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-items/<int:item_id>', methods=['PUT'])
def update_shopping_item(item_id):
    try:
        item = ShoppingItem.query.get_or_404(item_id)
        data = request.get_json()
        if 'name' in data: item.name = data['name']
        if 'quantity' in data: item.quantity = data['quantity']
        if 'checked' in data: item.checked = data['checked']
        if 'sort_order' in data: item.sort_order = data['sort_order']
        db.session.commit()
        return jsonify({"message": "Articolo aggiornato"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-items/<int:item_id>/check', methods=['PATCH'])
def toggle_shopping_item(item_id):
    try:
        item = ShoppingItem.query.get_or_404(item_id)
        data = request.get_json()
        item.checked = data.get('checked', not item.checked)
        db.session.commit()
        return jsonify({"message": "Stato aggiornato", "checked": item.checked}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-items/<int:item_id>', methods=['DELETE'])
def delete_shopping_item(item_id):
    try:
        item = ShoppingItem.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        return jsonify({"message": "Articolo eliminato"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-items/bulk', methods=['PUT'])
def bulk_update_items():
    try:
        data = request.get_json()
        updates = data.get('updates', [])
        delete_ids = data.get('delete_ids', [])

        for u in updates:
            item = ShoppingItem.query.get(u['id'])
            if not item:
                continue
            if 'name' in u: item.name = u['name']
            if 'quantity' in u: item.quantity = u['quantity']
            if 'checked' in u: item.checked = u['checked']

        for item_id in delete_ids:
            item = ShoppingItem.query.get(item_id)
            if item:
                db.session.delete(item)

        db.session.commit()
        return jsonify({"message": "Aggiornamento completato"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-items/check-all', methods=['PATCH'])
def check_all_items():
    try:
        data = request.get_json()
        list_id = data.get('shopping_list_id')
        checked = data.get('checked', True)
        ShoppingItem.query.filter_by(shopping_list_id=list_id).update({'checked': checked})
        db.session.commit()
        return jsonify({"message": "Articoli aggiornati"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-items/reorder', methods=['PUT'])
def reorder_shopping_items():
    try:
        data = request.get_json()
        ordered_ids = data.get('ordered_ids', [])
        for idx, item_id in enumerate(ordered_ids):
            item = ShoppingItem.query.get(item_id)
            if item:
                item.sort_order = idx
        db.session.commit()
        return jsonify({"message": "Ordine aggiornato"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500
