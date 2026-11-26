from sqlalchemy.orm import validates
from app import validation as check
from sqlalchemy import Column, BigInteger, String, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship

from app.database import db
from app.database.mixins import DeltaSyncMixin


class ExpensesList(DeltaSyncMixin, db.Model):
    __tablename__ = 'expenses_lists'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    user_id = Column(BigInteger, ForeignKey('spese.users.id'), nullable=False)
    user = relationship('User', backref=db.backref('expenses_lists', cascade='all, delete-orphan'))
    paid = Column(Boolean, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default='now()')
    # Tipo lista come stringa ('personal' | 'shared'), come shopping_lists. Default 'personal':
    # condividere è una scelta esplicita. (Prima era una FK a expenses_list_types con default shared.)
    list_type = Column(String(20), nullable=False, server_default='personal')
    invite_token = Column(String(64), nullable=True, unique=True)
    participants = relationship('ExpensesListParticipant', back_populates='expenses_list', cascade='all, delete-orphan')

    @validates('name')
    def _name(self, key, value):
        return check.text(value, key, 255)

    @validates('paid')
    def _paid(self, key, value):
        return check.boolean(value, key)

    @validates('list_type')
    def _list_type(self, key, value):
        return check.one_of(value, key, ('personal', 'shared'))
