from sqlalchemy import Column, BigInteger, String, ForeignKey
from app.database import db


class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    brand = Column(String(100), nullable=True)
    default_unit_id = Column(BigInteger, ForeignKey('spese.measurement_units.id'), nullable=False)
