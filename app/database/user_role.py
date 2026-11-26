from sqlalchemy.orm import validates
from app import validation as check
from sqlalchemy import Column, BigInteger, String
from app.database import db


class UserRole(db.Model):
    __tablename__ = 'user_roles'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)

    @validates('name')
    def _name(self, key, value):
        return check.text(value, key, 50)
