from sqlalchemy.orm import validates
from app import validation as check
from sqlalchemy import Column, BigInteger, String, Text, Date, Numeric, ForeignKey
from app.database import db
from app.database.mixins import DeltaSyncMixin


class Purchase(DeltaSyncMixin, db.Model):
    __tablename__ = 'purchases'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, ForeignKey('spese.products.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('spese.users.id'), nullable=False)
    purchased_at = Column(Date, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_id = Column(BigInteger, ForeignKey('spese.measurement_units.id'), nullable=False)
    store = Column(String(150), nullable=True)
    notes = Column(Text, nullable=True)

    @validates('price')
    def _price(self, key, value):
        return check.number(value, key, 0, check.MAX_AMOUNT, 2)

    @validates('quantity')
    def _quantity(self, key, value):
        return check.number(value, key, check.Decimal('0.001'), check.MAX_QUANTITY, 3)

    @validates('purchased_at')
    def _purchased_at(self, key, value):
        return check.day(value, key)

    @validates('store')
    def _store(self, key, value):
        return check.text(value, key, 150, required=False)

    @validates('notes')
    def _notes(self, key, value):
        return check.text(value, key, 2000, required=False)
