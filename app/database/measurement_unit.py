from sqlalchemy import Column, BigInteger, String
from app.database import db


class MeasurementUnit(db.Model):
    __tablename__ = 'measurement_units'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    symbol = Column(String(10), nullable=False, unique=True)
    category = Column(String(20), nullable=False)
