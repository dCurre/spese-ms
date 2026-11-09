import re
from datetime import datetime, timezone
from flask import request, jsonify
from sqlalchemy import func
from app.api import api
from app.database import db
from app.database.product import Product
from app.database.purchase import Purchase
from app.database.measurement_unit import MeasurementUnit
from app.exceptions import ValidationError
from app.schemas import parse_body, CreateProductSchema


def _parse_since(raw):
    """Converte il query param `since` (ISO 8601) in datetime naive UTC.
    Tollera 'Z', offset, e il '+' decodificato come spazio in querystring."""
    if not raw:
        return None
    value = raw.strip()
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    value = re.sub(r' (\d{2}:\d{2})$', r'+\1', value)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError("Parametro 'since' non è un timestamp ISO valido")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _soft_delete_product(product):
    """Soft-delete di un prodotto: marca deleted=true il prodotto e propaga ai
    suoi acquisti."""
    product.deleted = True
    Purchase.query.filter_by(product_id=product.id, deleted=False) \
        .update({'deleted': True}, synchronize_session=False)


@api.route('/products', methods=['GET'])
def get_products():
    products = Product.query.filter_by(deleted=False).order_by(Product.name).all()

    # Una sola query su tutti gli acquisti: evita N+1 nel ciclo di serializzazione.
    # Count aggregato in SQL; min_price calcolato lato Python per evitare problemi
    # di tipo/divisione intera sulla divisione SQL di Numeric.
    counts = {}
    min_prices = {}
    rows = db.session.query(
        Purchase.product_id, Purchase.price, Purchase.quantity
    ).filter_by(deleted=False).all()
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
    product = Product.query.filter_by(id=product_id, deleted=False).first_or_404()

    rows = db.session.query(Purchase.price, Purchase.quantity).filter(
        Purchase.product_id == product_id, Purchase.deleted == False
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
    client_id = data.get('client_id')

    # Create idempotente: catalogo globale -> dedup sul solo client_id.
    existing = None
    if client_id:
        existing = Product.query.filter_by(client_id=client_id).first()
    if existing:
        existing.name = data['name']
        existing.brand = data.get('brand')
        existing.default_unit_id = data.get('default_unit_id')
        existing.deleted = False
        db.session.commit()
        return jsonify({"id": existing.id, "client_id": existing.client_id, "message": "Prodotto aggiornato"}), 200

    product = Product(
        name=data['name'],
        brand=data.get('brand'),
        default_unit_id=data.get('default_unit_id'),
        client_id=client_id,
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({"id": product.id, "client_id": product.client_id, "message": "Prodotto creato"}), 201


@api.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    product = Product.query.filter_by(id=product_id, deleted=False).first_or_404()
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
    # Soft-delete: marca deleted=true il prodotto e propaga ai suoi acquisti.
    product = Product.query.filter_by(id=product_id, deleted=False).first_or_404()
    _soft_delete_product(product)
    db.session.commit()
    return jsonify({"message": "Prodotto eliminato"}), 200


@api.route('/products/bulk-delete', methods=['POST'])
def bulk_delete_products():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids:
        raise ValidationError("ids mancante o vuoto")
    # Soft-delete di piu' prodotti + relativi acquisti (nessuna rimozione fisica).
    products = Product.query.filter(Product.id.in_(ids), Product.deleted == False).all()
    for product in products:
        _soft_delete_product(product)
    db.session.commit()
    deleted = len(products)
    return jsonify({"deleted": deleted, "message": f"{deleted} prodotti eliminati"}), 200


def _serialize_product(product, purchase_count=0, min_price=None):
    unit = MeasurementUnit.query.get(product.default_unit_id) if product.default_unit_id else None
    return {
        "id": product.id,
        "client_id": product.client_id,
        "name": product.name,
        "brand": product.brand,
        "default_unit_id": product.default_unit_id,
        "default_unit_symbol": unit.symbol if unit else None,
        "updated_at": product.updated_at,
        "deleted": product.deleted,
        "purchase_count": purchase_count,
        "min_price": min_price,
    }


def _serialize_product_flat(p):
    return {
        "id": p.id,
        "client_id": p.client_id,
        "name": p.name,
        "brand": p.brand,
        "default_unit_id": p.default_unit_id,
        "updated_at": p.updated_at,
        "deleted": p.deleted,
    }


def _serialize_purchase_flat(pu):
    return {
        "id": pu.id,
        "client_id": pu.client_id,
        "product_id": pu.product_id,
        "user_id": pu.user_id,
        "purchased_at": pu.purchased_at,
        "price": float(pu.price) if pu.price is not None else None,
        "quantity": float(pu.quantity) if pu.quantity is not None else None,
        "unit_id": pu.unit_id,
        "store": pu.store,
        "notes": pu.notes,
        "updated_at": pu.updated_at,
        "deleted": pu.deleted,
    }


@api.route('/products/delta', methods=['GET'])
def products_delta():
    """Delta pull per il sync local-first dei PREZZI.

    Query param: user_id (obbligatorio), since (ISO 8601, opzionale).
    Ritorna i prodotti (catalogo GLOBALE) e gli acquisti DELL'UTENTE modificati
    dopo since, INCLUSI i deleted=true. `server_time` (ISO) = prossimo since.
    """
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        raise ValidationError("user_id mancante")
    since = _parse_since(request.args.get('since'))

    server_time = db.session.query(func.now()).scalar()

    products_q = Product.query
    purchases_q = Purchase.query.filter_by(user_id=user_id)
    if since is not None:
        products_q = products_q.filter(Product.updated_at > since)
        purchases_q = purchases_q.filter(Purchase.updated_at > since)

    return jsonify({
        "server_time": server_time,
        "products": [_serialize_product_flat(p) for p in products_q.all()],
        "purchases": [_serialize_purchase_flat(pu) for pu in purchases_q.all()],
    })


@api.route('/products/batch-sync', methods=['POST'])
def products_batch_sync():
    """Push batch del sync local-first per i PREZZI: create/update/delete misti
    su prodotti (globali) e acquisti in un'unica transazione.

    Body (blocchi opzionali):
      products_create:  [{temp_id, client_id?, name, brand?, default_unit_id}]
      products_update:  [{id, name?, brand?, default_unit_id?}]
      products_delete:  [id, ...]
      purchases_create: [{temp_id, client_id?, product_id|product_temp_id, user_id,
                          purchased_at, price, quantity, unit_id, store?, notes?}]
      purchases_update: [{id, purchased_at?, price?, quantity?, unit_id?, store?, notes?}]
      purchases_delete: [id, ...]

    Dedup: prodotti su client_id globale, acquisti su (product_id, client_id).
    temp_id per referenziare un prodotto nuovo da un acquisto nuovo.
    Risposta: { server_time, id_map }.
    """
    data = request.get_json() or {}
    product_map = {}
    purchase_map = {}

    # --- DELETE (soft) ---
    for pid in (data.get('products_delete') or []):
        p = Product.query.filter_by(id=pid, deleted=False).first()
        if p:
            _soft_delete_product(p)
    for puid in (data.get('purchases_delete') or []):
        pu = Purchase.query.get(puid)
        if pu and not pu.deleted:
            pu.deleted = True
    db.session.flush()

    # --- CREATE prodotti (idempotenti via client_id globale) ---
    for npr in (data.get('products_create') or []):
        if not (npr.get('name') or '').strip():
            continue
        cid = npr.get('client_id')
        p = None
        if cid:
            p = Product.query.filter_by(client_id=cid).first()
        if p:
            p.name = npr['name']
            p.brand = npr.get('brand')
            p.default_unit_id = npr.get('default_unit_id')
            p.deleted = False
        else:
            p = Product(
                name=npr['name'],
                brand=npr.get('brand'),
                default_unit_id=npr.get('default_unit_id'),
                client_id=cid,
            )
            db.session.add(p)
        db.session.flush()
        if npr.get('temp_id') is not None:
            product_map[str(npr['temp_id'])] = p.id

    def _resolve_product_id(obj):
        if obj.get('product_id') is not None:
            return obj['product_id']
        pt = obj.get('product_temp_id')
        return product_map.get(str(pt)) if pt is not None else None

    # --- CREATE acquisti (idempotenti via client_id per prodotto) ---
    for npu in (data.get('purchases_create') or []):
        product_id = _resolve_product_id(npu)
        cid = npu.get('client_id')
        pu = None
        if cid and product_id is not None:
            pu = Purchase.query.filter_by(product_id=product_id, client_id=cid).first()
        if pu:
            pu.user_id = npu['user_id']
            pu.purchased_at = npu['purchased_at']
            pu.price = npu['price']
            pu.quantity = npu['quantity']
            pu.unit_id = npu['unit_id']
            pu.store = npu.get('store')
            pu.notes = npu.get('notes')
            pu.deleted = False
        else:
            pu = Purchase(
                product_id=product_id,
                user_id=npu['user_id'],
                purchased_at=npu['purchased_at'],
                price=npu['price'],
                quantity=npu['quantity'],
                unit_id=npu['unit_id'],
                store=npu.get('store'),
                notes=npu.get('notes'),
                client_id=cid,
            )
            db.session.add(pu)
        db.session.flush()
        if npu.get('temp_id') is not None:
            purchase_map[str(npu['temp_id'])] = pu.id

    # --- UPDATE prodotti ---
    for upr in (data.get('products_update') or []):
        p = Product.query.filter_by(id=upr['id'], deleted=False).first()
        if not p:
            continue
        if 'name' in upr:
            p.name = upr['name']
        if 'brand' in upr:
            p.brand = upr['brand']
        if 'default_unit_id' in upr:
            p.default_unit_id = upr['default_unit_id']

    # --- UPDATE acquisti ---
    for upu in (data.get('purchases_update') or []):
        pu = Purchase.query.filter_by(id=upu['id'], deleted=False).first()
        if not pu:
            continue
        if 'purchased_at' in upu:
            pu.purchased_at = upu['purchased_at']
        if 'price' in upu:
            pu.price = upu['price']
        if 'quantity' in upu:
            pu.quantity = upu['quantity']
        if 'unit_id' in upu:
            pu.unit_id = upu['unit_id']
        if 'store' in upu:
            pu.store = upu['store']
        if 'notes' in upu:
            pu.notes = upu['notes']

    db.session.commit()
    server_time = db.session.query(func.now()).scalar()
    return jsonify({
        "server_time": server_time,
        "id_map": {"products": product_map, "purchases": purchase_map},
    }), 200
