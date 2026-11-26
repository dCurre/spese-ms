"""Test del controllo token: `python test_auth.py` (nessuna rete, nessun database)."""
import time
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, jsonify

from app import auth
from app.exceptions import AppError

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
auth.jwks.get_signing_key_from_jwt = lambda token: SimpleNamespace(key=key.public_key())

app = Flask(__name__)
app.before_request(auth.require_auth)
app.errorhandler(AppError)(lambda e: (jsonify(error=e.message), e.status_code))
app.add_url_rule('/private', 'private', lambda: 'ok', methods=['GET', 'POST'])
app.add_url_rule('/public', 'api.keepalive', lambda: 'ok')
client = app.test_client()


def token(signing_key=key, **overrides):
    now = int(time.time())
    claims = {'aud': auth.PROJECT_ID, 'iss': auth.ISSUER, 'sub': 'uid', 'iat': now,
              'exp': now + 600, 'email': 'a@example.com', 'email_verified': True}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, signing_key, algorithm='RS256')


def status(value=None, method='get', path='/private'):
    headers = {'Authorization': value} if value else {}
    return getattr(client, method)(path, headers=headers).status_code


assert status(f'Bearer {token()}') == 200
assert status() == 401
assert status(method='post') == 401
assert status('Bearer spazzatura') == 401
assert status(token()) == 401  # manca "Bearer"
for bad in (token(other_key), token(aud='altro'), token(iss='https://evil.example'),
            token(exp=int(time.time()) - 60), token(email=None), token(email_verified=False),
            token(sub=None), jwt.encode({'email': 'a@example.com'}, 'x' * 32, algorithm='HS256')):
    assert status(f'Bearer {bad}') == 401, bad
assert status(path='/public') == 200
assert status(method='options') == 200
print('OK')
