import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:c1rmee94%21SPESE@db.zclxrrjkcteilzlzlqhq.supabase.co:5432/postgres?sslmode=require'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
