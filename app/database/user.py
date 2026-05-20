from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import db

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    surname = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    profile_image = Column(String(255), nullable=True)
    paid_list_shown = Column(Boolean, nullable=True, default=True)
    created_at = Column(DateTime, nullable=True, server_default=None)
    role_id = Column(BigInteger, ForeignKey('spese.user_roles.id'), nullable=True, server_default='2')
    role = relationship('UserRole', foreign_keys=[role_id])
    theme_preference = Column(String(20), nullable=True, default='auto')