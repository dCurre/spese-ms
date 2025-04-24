from sqlalchemy import Column, BigInteger, String, Boolean, TIMESTAMP

from app.database import db


class ExpensesList(db.Model):
    __tablename__ = 'expenses_lists'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    owner_id = Column(BigInteger, nullable=False)
    paid = Column(Boolean, nullable=True)
    creation_date = Column(TIMESTAMP, nullable=True)