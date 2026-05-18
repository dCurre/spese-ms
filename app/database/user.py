from app.database import db

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'spese'}

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=True)
    surname = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    paid_list_shown = db.Column(db.Boolean, nullable=True, default=True)
    created_at = db.Column(db.DateTime, nullable=True, server_default=None)