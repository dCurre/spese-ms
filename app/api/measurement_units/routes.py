from flask import request, jsonify
from app.api import api
from app.database import db
from app.database.measurement_unit import MeasurementUnit
from app.exceptions import ForbiddenError
from app.schemas import parse_body, CreateMeasurementUnitSchema

PROTECTED_IDS = {1, 2, 3, 4, 5}


@api.route('/measurement-units', methods=['GET'])
def get_measurement_units():
    units = MeasurementUnit.query.order_by(MeasurementUnit.category, MeasurementUnit.name).all()
    return jsonify({
        "measurement_units": [
            {
                "id": u.id,
                "name": u.name,
                "symbol": u.symbol,
                "category": u.category,
                "protected": u.id in PROTECTED_IDS,
            }
            for u in units
        ]
    })


@api.route('/measurement-units', methods=['POST'])
def create_measurement_unit():
    data = parse_body(CreateMeasurementUnitSchema)
    unit = MeasurementUnit(name=data['name'], symbol=data['symbol'], category=data['category'])
    db.session.add(unit)
    db.session.commit()
    return jsonify({"id": unit.id, "message": "Unità di misura creata"}), 201


@api.route('/measurement-units/<int:unit_id>', methods=['PUT'])
def update_measurement_unit(unit_id):
    if unit_id in PROTECTED_IDS:
        raise ForbiddenError("Unità di misura non modificabile")
    unit = MeasurementUnit.query.get_or_404(unit_id)
    data = request.get_json() or {}
    if 'name' in data:
        unit.name = data['name']
    if 'symbol' in data:
        unit.symbol = data['symbol']
    if 'category' in data:
        unit.category = data['category']
    db.session.commit()
    return jsonify({"message": "Unità di misura aggiornata"}), 200


@api.route('/measurement-units/<int:unit_id>', methods=['DELETE'])
def delete_measurement_unit(unit_id):
    if unit_id in PROTECTED_IDS:
        raise ForbiddenError("Unità di misura non eliminabile")
    unit = MeasurementUnit.query.get_or_404(unit_id)
    db.session.delete(unit)
    db.session.commit()
    return jsonify({"message": "Unità di misura eliminata"}), 200
