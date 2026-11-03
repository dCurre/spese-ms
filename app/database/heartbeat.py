from sqlalchemy import Column, BigInteger, DateTime, func
from app.database import db


class Heartbeat(db.Model):
    __tablename__ = 'heartbeat'
    __table_args__ = {'schema': 'spese'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    last_ping = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
