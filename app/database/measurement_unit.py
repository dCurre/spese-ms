from sqlalchemy.orm import validates
from app import validation as check
from sqlalchemy import Column, BigInteger, String
from app.database import db


class MeasurementUnit(db.Model):
    __tablename__ = 'measurement_units'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    symbol = Column(String(10), nullable=False, unique=True)
    category = Column(String(20), nullable=False)

    @validates('name')
    def _name(self, key, value):
        return check.text(value, key, 50)

    @validates('symbol')
    def _symbol(self, key, value):
        return check.text(value, key, 10)

    @validates('category')
    def _category(self, key, value):
        return check.one_of(value, key, ('peso', 'volume', 'numero', 'lunghezza', 'energia'))
