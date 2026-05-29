from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.shopping_list import ShoppingCategory, ShoppingItem
from app.schemas import parse_body, CreateShoppingCategorySchema


def _check_recursive(category_id, checked):
    """Spunta/despunta ricorsivamente tutti gli item della categoria e delle sue sottocategorie."""
    ShoppingItem.query.filter_by(category_id=category_id).update({'checked': checked})
    children = ShoppingCategory.query.filter_by(parent_id=category_id).all()
    for child in children:
        _check_recursive(child.id, checked)


@api.route('/shopping-categories', methods=['POST'])
def create_shopping_category():
    data = parse_body(CreateShoppingCategorySchema)
    cat = ShoppingCategory(
        shopping_list_id=data['shopping_list_id'],
        parent_id=data.get('parent_id'),
        name=data['name'],
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify({"id": cat.id, "message": "Categoria creata"}), 201


@api.route('/shopping-categories/<int:category_id>', methods=['PUT'])
def update_shopping_category(category_id):
    cat = ShoppingCategory.query.get_or_404(category_id)
    data = request.get_json() or {}
    if 'name' in data: cat.name = data['name']
    if 'sort_order' in data: cat.sort_order = data['sort_order']
    if 'parent_id' in data: cat.parent_id = data['parent_id']
    db.session.commit()
    return jsonify({"message": "Categoria aggiornata"}), 200


@api.route('/shopping-categories/<int:category_id>', methods=['DELETE'])
def delete_shopping_category(category_id):
    cat = ShoppingCategory.query.get_or_404(category_id)
    db.session.delete(cat)
    db.session.commit()
    return jsonify({"message": "Categoria eliminata"}), 200


@api.route('/shopping-categories/<int:category_id>/check', methods=['PATCH'])
def check_category(category_id):
    """Spunta/despunta ricorsivamente tutti gli item della categoria e sottocategorie."""
    ShoppingCategory.query.get_or_404(category_id)
    data = request.get_json() or {}
    checked = data.get('checked', True)
    _check_recursive(category_id, checked)
    db.session.commit()
    return jsonify({"message": "Categoria aggiornata", "checked": checked}), 200
