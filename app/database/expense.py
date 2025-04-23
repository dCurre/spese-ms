from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import db


class Expense(db.Model):
    __tablename__ = 'expenses'
    __table_args__ = {'schema': 'spese'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    amount = Column(Numeric(10, 2), nullable=True)
    creation_date = Column(DateTime, nullable=False)
    owner = Column(Integer, ForeignKey('auth.users.id'), nullable=False)
    update_date = Column(DateTime, nullable=True)
    modified_by = Column(Integer, nullable=True)
    expense_list_id = Column(Integer, nullable=False)
    expense_date = Column(DateTime, nullable=False)

    # This creates a relationship between Expense and User
    user = relationship('User', backref='expenses', foreign_keys=[owner])