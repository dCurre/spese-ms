from sqlalchemy import Column, BigInteger, String
from app.database import db


class UserRole(db.Model):
    __tablename__ = 'user_roles'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
