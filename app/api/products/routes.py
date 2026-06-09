from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.product import Product
from app.database.measurement_unit import MeasurementUnit
from app.schemas import parse_body, CreateProductSchema


@api.route('/products', methods=['GET'])
def get_products():
    products = Product.query.order_by(Product.name).all()
    return jsonify({
        "products": [_serialize_product(p) for p in products]
    })


@api.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify(_serialize_product(product))


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


def _serialize_product(product):
    unit = MeasurementUnit.query.get(product.default_unit_id) if product.default_unit_id else None
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "default_unit_id": product.default_unit_id,
        "default_unit_symbol": unit.symbol if unit else None,
    }
