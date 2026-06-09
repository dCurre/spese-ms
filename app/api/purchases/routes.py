from collections import defaultdict
from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.purchase import Purchase
from app.database.product import Product
from app.database.measurement_unit import MeasurementUnit
from app.schemas import parse_body, CreatePurchaseSchema


@api.route('/products/<int:product_id>/purchases', methods=['GET'])
def get_product_purchases(product_id):
    Product.query.get_or_404(product_id)
    purchases = (
        Purchase.query
        .filter_by(product_id=product_id)
        .order_by(Purchase.purchased_at.desc())
        .all()
    )
    return jsonify({
        "purchases": [_serialize_purchase(p) for p in purchases]
    })


@api.route('/purchases', methods=['POST'])
def create_purchase():
    data = parse_body(CreatePurchaseSchema)
    Product.query.get_or_404(data['product_id'])
    purchase = Purchase(
        product_id=data['product_id'],
        user_id=data['user_id'],
        purchased_at=data['purchased_at'],
        price=data['price'],
        quantity=data['quantity'],
        unit_id=data['unit_id'],
        store=data.get('store'),
        notes=data.get('notes'),
    )
    db.session.add(purchase)
    db.session.commit()
    return jsonify({"id": purchase.id, "message": "Acquisto registrato"}), 201


@api.route('/purchases/<int:purchase_id>', methods=['PUT'])
def update_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    data = request.get_json() or {}
    if 'purchased_at' in data:
        purchase.purchased_at = data['purchased_at']
    if 'price' in data:
        purchase.price = data['price']
    if 'quantity' in data:
        purchase.quantity = data['quantity']
    if 'unit_id' in data:
        purchase.unit_id = data['unit_id']
    if 'store' in data:
        purchase.store = data['store']
    if 'notes' in data:
        purchase.notes = data['notes']
    db.session.commit()
    return jsonify({"message": "Acquisto aggiornato"}), 200


@api.route('/purchases/<int:purchase_id>', methods=['DELETE'])
def delete_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    db.session.delete(purchase)
    db.session.commit()
    return jsonify({"message": "Acquisto eliminato"}), 200


@api.route('/products/<int:product_id>/price-history', methods=['GET'])
def get_price_history(product_id):
    product = Product.query.get_or_404(product_id)
    granularity = request.args.get('granularity', 'month')
    from_date = request.args.get('from')
    to_date = request.args.get('to')

    query = Purchase.query.filter_by(product_id=product_id)
    if from_date:
        query = query.filter(Purchase.purchased_at >= from_date)
    if to_date:
        query = query.filter(Purchase.purchased_at <= to_date)

    purchases = query.order_by(Purchase.purchased_at).all()

    groups = defaultdict(list)
    for p in purchases:
        if granularity == 'year':
            key = str(p.purchased_at.year)
        elif granularity == 'day':
            key = p.purchased_at.strftime('%Y-%m-%d')
        else:
            key = p.purchased_at.strftime('%Y-%m')

        unit_price = float(p.price) / float(p.quantity)
        groups[key].append(unit_price)

    data = []
    for period in sorted(groups.keys()):
        prices = groups[period]
        data.append({
            "period": period,
            "avg_unit_price": round(sum(prices) / len(prices), 4),
            "min_unit_price": round(min(prices), 4),
            "max_unit_price": round(max(prices), 4),
            "count": len(prices),
        })

    unit = MeasurementUnit.query.get(product.default_unit_id) if product.default_unit_id else None
    return jsonify({
        "product_id": product.id,
        "product_name": product.name,
        "unit_symbol": unit.symbol if unit else None,
        "data": data,
    })


def _serialize_purchase(purchase):
    unit = MeasurementUnit.query.get(purchase.unit_id)
    unit_price = float(purchase.price) / float(purchase.quantity)
    return {
        "id": purchase.id,
        "product_id": purchase.product_id,
        "user_id": purchase.user_id,
        "purchased_at": str(purchase.purchased_at),
        "price": float(purchase.price),
        "quantity": float(purchase.quantity),
        "unit_id": purchase.unit_id,
        "unit_symbol": unit.symbol if unit else None,
        "unit_price": round(unit_price, 4),
        "store": purchase.store,
        "notes": purchase.notes,
    }
