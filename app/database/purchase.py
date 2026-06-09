from sqlalchemy import Column, BigInteger, String, Text, Date, Numeric, ForeignKey
from app.database import db


class Purchase(db.Model):
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
