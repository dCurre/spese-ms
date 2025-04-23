import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:c1rmee94!SPESE@db.zclxrrjkcteilzlzlqhq.supabase.co:5432/postgres'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
