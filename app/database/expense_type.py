from sqlalchemy import Column, BigInteger, String
from app.database import db


class ExpenseType(db.Model):
    __tablename__ = 'expense_types'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
