from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.shopping_list import ShoppingCategory, ShoppingItem
from app.schemas import parse_body, CreateShoppingCategorySchema


def _check_recursive(category_id, checked):
    """Spunta/despunta ricorsivamente tutti gli item (non cancellati) della categoria e delle sue sottocategorie."""
    ShoppingItem.query.filter_by(category_id=category_id, deleted=False).update(
        {'checked': checked}, synchronize_session=False
    )
    children = ShoppingCategory.query.filter_by(parent_id=category_id, deleted=False).all()
    for child in children:
        _check_recursive(child.id, checked)


def soft_delete_category(category_id):
    """Soft-delete di una categoria: marca deleted=true la categoria, i suoi
    articoli e ricorsivamente le sottocategorie (con i rispettivi articoli).
    Non committa: il chiamante gestisce la transazione."""
    cat = ShoppingCategory.query.filter_by(id=category_id, deleted=False).first()
    if not cat:
        return
    cat.deleted = True
    ShoppingItem.query.filter_by(category_id=category_id, deleted=False).update(
        {'deleted': True}, synchronize_session=False
    )
    children = ShoppingCategory.query.filter_by(parent_id=category_id, deleted=False).all()
    for child in children:
        soft_delete_category(child.id)


@api.route('/shopping-categories', methods=['POST'])
def create_shopping_category():
    data = parse_body(CreateShoppingCategorySchema)
    client_id = data.get('client_id')

    # Create idempotente: client_id gia' visto nella stessa lista -> update.
    existing = None
    if client_id:
        existing = ShoppingCategory.query.filter_by(
            shopping_list_id=data['shopping_list_id'], client_id=client_id
        ).first()

    if existing:
        existing.parent_id = data.get('parent_id')
        existing.name = data['name']
        existing.sort_order = data.get('sort_order', 0)
        existing.deleted = False
        db.session.commit()
        return jsonify({"id": existing.id, "client_id": existing.client_id, "message": "Categoria aggiornata"}), 200

    cat = ShoppingCategory(
        shopping_list_id=data['shopping_list_id'],
        parent_id=data.get('parent_id'),
        name=data['name'],
        sort_order=data.get('sort_order', 0),
        client_id=client_id,
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify({"id": cat.id, "client_id": cat.client_id, "message": "Categoria creata"}), 201


@api.route('/shopping-categories/<int:category_id>', methods=['PUT'])
def update_shopping_category(category_id):
    cat = ShoppingCategory.query.filter_by(id=category_id, deleted=False).first_or_404()
    data = request.get_json() or {}
    if 'name' in data: cat.name = data['name']
    if 'sort_order' in data: cat.sort_order = data['sort_order']
    if 'parent_id' in data: cat.parent_id = data['parent_id']
    db.session.commit()
    return jsonify({"message": "Categoria aggiornata"}), 200


@api.route('/shopping-categories/<int:category_id>', methods=['DELETE'])
def delete_shopping_category(category_id):
    # Soft-delete: marca deleted=true la categoria + articoli + sottocategorie.
    ShoppingCategory.query.filter_by(id=category_id, deleted=False).first_or_404()
    soft_delete_category(category_id)
    db.session.commit()
    return jsonify({"message": "Categoria eliminata"}), 200


@api.route('/shopping-categories/<int:category_id>/check', methods=['PATCH'])
def check_category(category_id):
    """Spunta/despunta ricorsivamente tutti gli item della categoria e sottocategorie."""
    ShoppingCategory.query.filter_by(id=category_id, deleted=False).first_or_404()
    data = request.get_json() or {}
    checked = data.get('checked', True)
    _check_recursive(category_id, checked)
    db.session.commit()
    return jsonify({"message": "Categoria aggiornata", "checked": checked}), 200
