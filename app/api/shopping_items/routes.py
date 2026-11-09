from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.shopping_list import ShoppingItem
from app.exceptions import ValidationError
from app.schemas import parse_body, CreateShoppingItemSchema


def _norm_qty(value):
    """Normalizza la quantity: None/null → 1, valori ≤ 0 → 1, altrimenti intero."""
    if value is None:
        return 1
    try:
        v = int(value)
        return v if v > 0 else 1
    except (TypeError, ValueError):
        return 1


@api.route('/shopping-items', methods=['POST'])
def create_shopping_item():
    data = parse_body(CreateShoppingItemSchema)
    client_id = data.get('client_id')

    # Create idempotente: se arriva un client_id gia' visto nella stessa lista,
    # aggiorna la riga esistente invece di crearne una nuova (anti re-invio).
    existing = None
    if client_id:
        existing = ShoppingItem.query.filter_by(
            shopping_list_id=data['shopping_list_id'], client_id=client_id
        ).first()

    if existing:
        existing.name = data['name']
        existing.quantity = _norm_qty(data.get('quantity'))
        existing.checked = data.get('checked', False)
        existing.sort_order = data.get('sort_order', 0)
        existing.category_id = data.get('category_id')
        existing.deleted = False  # un re-invio della create "ripristina" la riga
        db.session.commit()
        return jsonify({"id": existing.id, "client_id": existing.client_id, "message": "Articolo aggiornato"}), 200

    item = ShoppingItem(
        shopping_list_id=data['shopping_list_id'],
        name=data['name'],
        quantity=_norm_qty(data.get('quantity')),
        checked=data.get('checked', False),
        sort_order=data.get('sort_order', 0),
        category_id=data.get('category_id'),
        client_id=client_id,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"id": item.id, "client_id": item.client_id, "message": "Articolo aggiunto"}), 201


@api.route('/shopping-items/<int:item_id>', methods=['PUT'])
def update_shopping_item(item_id):
    item = ShoppingItem.query.filter_by(id=item_id, deleted=False).first_or_404()
    data = request.get_json() or {}
    if 'name' in data: item.name = data['name']
    if 'quantity' in data: item.quantity = _norm_qty(data['quantity'])
    if 'checked' in data: item.checked = data['checked']
    if 'sort_order' in data: item.sort_order = data['sort_order']
    if 'category_id' in data: item.category_id = data['category_id']
    db.session.commit()
    return jsonify({"message": "Articolo aggiornato"}), 200


@api.route('/shopping-items/<int:item_id>/check', methods=['PATCH'])
def toggle_shopping_item(item_id):
    item = ShoppingItem.query.filter_by(id=item_id, deleted=False).first_or_404()
    data = request.get_json() or {}
    item.checked = data.get('checked', not item.checked)
    db.session.commit()
    return jsonify({"message": "Stato aggiornato", "checked": item.checked}), 200


@api.route('/shopping-items/<int:item_id>', methods=['DELETE'])
def delete_shopping_item(item_id):
    # Soft-delete: marca deleted=true (il trigger DB aggiorna updated_at) cosi'
    # il delta sync propaga la cancellazione all'app.
    item = ShoppingItem.query.filter_by(id=item_id, deleted=False).first_or_404()
    item.deleted = True
    db.session.commit()
    return jsonify({"message": "Articolo eliminato"}), 200


@api.route('/shopping-items/bulk', methods=['PUT'])
def bulk_update_items():
    data = request.get_json() or {}
    updates = data.get('updates', [])
    delete_ids = data.get('delete_ids', [])

    for u in updates:
        item = ShoppingItem.query.get(u['id'])
        if not item or item.deleted:
            continue
        if 'name' in u: item.name = u['name']
        if 'quantity' in u: item.quantity = _norm_qty(u['quantity'])
        if 'checked' in u: item.checked = u['checked']

    # Soft-delete.
    for item_id in delete_ids:
        item = ShoppingItem.query.get(item_id)
        if item and not item.deleted:
            item.deleted = True

    db.session.commit()
    return jsonify({"message": "Aggiornamento completato"}), 200


@api.route('/shopping-items/check-all', methods=['PATCH'])
def check_all_items():
    data = request.get_json() or {}
    list_id = data.get('shopping_list_id')
    if not list_id:
        raise ValidationError("shopping_list_id mancante")
    checked = data.get('checked', True)
    uncategorized_only = data.get('uncategorized_only', False)
    query = ShoppingItem.query.filter_by(shopping_list_id=list_id, deleted=False)
    if uncategorized_only:
        query = query.filter(ShoppingItem.category_id == None)
    query.update({'checked': checked}, synchronize_session=False)
    db.session.commit()
    return jsonify({"message": "Articoli aggiornati"}), 200


@api.route('/shopping-items/reorder', methods=['PUT'])
def reorder_shopping_items():
    data = request.get_json() or {}
    ordered_ids = data.get('ordered_ids', [])
    for idx, item_id in enumerate(ordered_ids):
        item = ShoppingItem.query.get(item_id)
        if item and not item.deleted:
            item.sort_order = idx
    db.session.commit()
    return jsonify({"message": "Ordine aggiornato"}), 200
