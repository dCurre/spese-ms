from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.shopping_list import ShoppingCategory, ShoppingItem


@api.route('/shopping-categories', methods=['POST'])
def create_shopping_category():
    try:
        data = request.get_json()
        cat = ShoppingCategory(
            shopping_list_id=data['shopping_list_id'],
            name=data['name'],
            sort_order=data.get('sort_order', 0),
        )
        db.session.add(cat)
        db.session.commit()
        return jsonify({"id": cat.id, "message": "Categoria creata"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-categories/<int:category_id>', methods=['PUT'])
def update_shopping_category(category_id):
    try:
        cat = ShoppingCategory.query.get_or_404(category_id)
        data = request.get_json()
        if 'name' in data: cat.name = data['name']
        if 'sort_order' in data: cat.sort_order = data['sort_order']
        db.session.commit()
        return jsonify({"message": "Categoria aggiornata"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-categories/<int:category_id>', methods=['DELETE'])
def delete_shopping_category(category_id):
    try:
        cat = ShoppingCategory.query.get_or_404(category_id)
        db.session.delete(cat)
        db.session.commit()
        return jsonify({"message": "Categoria eliminata"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500


@api.route('/shopping-categories/<int:category_id>/check', methods=['PATCH'])
def check_category(category_id):
    """Spunta/despunta tutti gli item della categoria."""
    try:
        cat = ShoppingCategory.query.get_or_404(category_id)
        data = request.get_json()
        checked = data.get('checked', True)
        ShoppingItem.query.filter_by(category_id=category_id).update({'checked': checked})
        db.session.commit()
        return jsonify({"message": "Categoria aggiornata", "checked": checked}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "code": 500}), 500
