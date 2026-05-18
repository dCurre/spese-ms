from sqlalchemy import Column, BigInteger, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship

from app.database import db


class ExpensesListParticipant(db.Model):
    __tablename__ = 'expenses_list_participants'
    __table_args__ = (
        {'schema': 'spese'},
    )

    expenses_list_id = Column(BigInteger, ForeignKey('spese.expenses_lists.id'), primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('spese.users.id'), primary_key=True, nullable=False)
    joined_at = Column(TIMESTAMP, nullable=False)

    user = relationship('User', backref='participations')
    expenses_list = relationship('ExpensesList', back_populates='participants')
