from sqlalchemy import Column, BigInteger, String, Boolean, TIMESTAMP, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.database import db


class ShoppingList(db.Model):
    __tablename__ = 'shopping_lists'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    owner_id = Column(BigInteger, ForeignKey('spese.users.id'), nullable=False)
    list_type = Column(String(20), nullable=False, server_default='personal')
    completed = Column(Boolean, nullable=False, server_default='false')
    starred = Column(Boolean, nullable=False, server_default='false')
    invite_token = Column(String(64), nullable=True, unique=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default='now()')

    owner = relationship('User', foreign_keys=[owner_id])
    items = relationship('ShoppingItem', back_populates='shopping_list', cascade='all, delete-orphan')
    categories = relationship('ShoppingCategory', back_populates='shopping_list', cascade='all, delete-orphan')
    participants = relationship('ShoppingListParticipant', back_populates='shopping_list', cascade='all, delete-orphan')


class ShoppingCategory(db.Model):
    __tablename__ = 'shopping_categories'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    shopping_list_id = Column(BigInteger, ForeignKey('spese.shopping_lists.id'), nullable=False)
    parent_id = Column(BigInteger, ForeignKey('spese.shopping_categories.id'), nullable=True)
    name = Column(String(255), nullable=False)
    sort_order = Column(Integer, nullable=False, server_default='0')
    created_at = Column(TIMESTAMP, nullable=False, server_default='now()')

    shopping_list = relationship('ShoppingList', back_populates='categories')
    items = relationship('ShoppingItem', back_populates='category', cascade='all, delete-orphan')
    children = relationship('ShoppingCategory', back_populates='parent', cascade='all, delete-orphan')
    parent = relationship('ShoppingCategory', back_populates='children', remote_side='ShoppingCategory.id')


class ShoppingItem(db.Model):
    __tablename__ = 'shopping_items'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    shopping_list_id = Column(BigInteger, ForeignKey('spese.shopping_lists.id'), nullable=False)
    category_id = Column(BigInteger, ForeignKey('spese.shopping_categories.id'), nullable=True)
    name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=True)
    checked = Column(Boolean, nullable=False, server_default='false')
    sort_order = Column(Integer, nullable=False, server_default='0')
    created_at = Column(TIMESTAMP, nullable=False, server_default='now()')

    shopping_list = relationship('ShoppingList', back_populates='items')
    category = relationship('ShoppingCategory', back_populates='items')


class ShoppingListParticipant(db.Model):
    __tablename__ = 'shopping_list_participants'
    __table_args__ = {'schema': 'spese'}

    shopping_list_id = Column(BigInteger, ForeignKey('spese.shopping_lists.id'), primary_key=True)
    user_id = Column(BigInteger, ForeignKey('spese.users.id'), primary_key=True)
    joined_at = Column(TIMESTAMP, nullable=False, server_default='now()')

    shopping_list = relationship('ShoppingList', back_populates='participants')
    user = relationship('User')
