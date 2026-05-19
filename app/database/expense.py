from sqlalchemy import Column, Integer, BigInteger, String, Numeric, DateTime, ForeignKey, ForeignKeyConstraint, TIMESTAMP
from sqlalchemy.orm import relationship

from app.database import db


class Expense(db.Model):
    __tablename__ = 'expenses'
    __table_args__ = (
        ForeignKeyConstraint(['expense_list_id'], ['spese.expenses_lists.id'], name='expenses_expenses_list_fk'),
        ForeignKeyConstraint(['expense_owner_user_id'], ['spese.users.id'], name='expenses_owner_fk'),
        {'schema': 'spese'},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    amount = Column(Numeric(10, 2), nullable=True)
    expense_owner_user_id = Column(BigInteger, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    modified_by = Column(Integer, nullable=True)
    expense_list_id = Column(Integer, nullable=False)
    expense_date = Column(DateTime, nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=None)
    expense_type_id = Column(BigInteger, ForeignKey('spese.expense_types.id'), nullable=True)

    user = relationship('User', backref=db.backref('expenses', cascade='all, delete-orphan'), foreign_keys='Expense.expense_owner_user_id')
    expenses_list = relationship('ExpensesList', backref=db.backref('expenses', cascade='all, delete-orphan'), foreign_keys='Expense.expense_list_id')
    expense_type = relationship('ExpenseType', foreign_keys=[expense_type_id])