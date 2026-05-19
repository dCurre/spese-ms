from sqlalchemy import Column, BigInteger, Integer, String
from app.database import db


class ListType(db.Model):
    __tablename__ = 'expenses_list_types'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    max_participants = Column(Integer, nullable=False, server_default='8')
