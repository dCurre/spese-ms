from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.product import Product
from app.database.purchase import Purchase
from app.database.measurement_unit import MeasurementUnit
from app.exceptions import ValidationError
from app.schemas import parse_body, CreateProductSchema


@api.route('/products', methods=['GET'])
def get_products():
    products = Product.query.order_by(Product.name).all()

    # Una sola query su tutti gli acquisti: evita N+1 nel ciclo di serializzazione.
    # Count aggregato in SQL; min_price calcolato lato Python per evitare problemi
    # di tipo/divisione intera sulla divisione SQL di Numeric.
    counts = {}
    min_prices = {}
    rows = db.session.query(
        Purchase.product_id, Purchase.price, Purchase.quantity
    ).all()
    for product_id, price, quantity in rows:
        counts[product_id] = counts.get(product_id, 0) + 1
        unit_price = round(float(price) / float(quantity), 4)
        current = min_prices.get(product_id)
        if current is None or unit_price < current:
            min_prices[product_id] = unit_price

    return jsonify({
        "products": [
            _serialize_product(
                p,
                purchase_count=counts.get(p.id, 0),
                min_price=min_prices.get(p.id),
            )
            for p in products
        ]
    })


@api.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get_or_404(product_id)

    rows = db.session.query(Purchase.price, Purchase.quantity).filter(
        Purchase.product_id == product_id
    ).all()
    purchase_count = len(rows)
    min_price = None
    for price, quantity in rows:
        unit_price = round(float(price) / float(quantity), 4)
        if min_price is None or unit_price < min_price:
            min_price = unit_price

    return jsonify(_serialize_product(
        product,
        purchase_count=purchase_count,
        min_price=min_price,
    ))


@api.route('/products', methods=['POST'])
def create_product():
    data = parse_body(CreateProductSchema)
    product = Product(
        name=data['name'],
        brand=data.get('brand'),
        default_unit_id=data.get('default_unit_id'),
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({"id": product.id, "message": "Prodotto creato"}), 201


@api.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json() or {}
    if 'name' in data:
        product.name = data['name']
    if 'brand' in data:
        product.brand = data['brand']
    if 'default_unit_id' in data:
        product.default_unit_id = data['default_unit_id']
    db.session.commit()
    return jsonify({"message": "Prodotto aggiornato"}), 200


@api.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Prodotto eliminato"}), 200


@api.route('/products/bulk-delete', methods=['POST'])
def bulk_delete_products():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids:
        raise ValidationError("ids mancante o vuoto")
    # purchases.product_id ha ON DELETE CASCADE a livello DB: cancellando i
    # prodotti, gli acquisti collegati vengono rimossi automaticamente (come
    # fa la DELETE singola via db.session.delete).
    deleted = Product.query.filter(Product.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"deleted": deleted, "message": f"{deleted} prodotti eliminati"}), 200


def _serialize_product(product, purchase_count=0, min_price=None):
    unit = MeasurementUnit.query.get(product.default_unit_id) if product.default_unit_id else None
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "default_unit_id": product.default_unit_id,
        "default_unit_symbol": unit.symbol if unit else None,
        "purchase_count": purchase_count,
        "min_price": min_price,
    }
