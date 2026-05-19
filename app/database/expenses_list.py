from sqlalchemy import Column, BigInteger, String, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship

from app.database import db


class ExpensesList(db.Model):
    __tablename__ = 'expenses_lists'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    user_id = Column(BigInteger, ForeignKey('spese.users.id'), nullable=False)
    user = relationship('User', backref=db.backref('expenses_lists', cascade='all, delete-orphan'))
    paid = Column(Boolean, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default='now()')
    list_type_id = Column(BigInteger, ForeignKey('spese.expenses_list_types.id'), nullable=False, server_default='1')
    list_type = relationship('ListType', foreign_keys=[list_type_id])
    participants = relationship('ExpensesListParticipant', back_populates='expenses_list', cascade='all, delete-orphan')