"""Verifica dell'ID token Firebase richiesto su ogni chiamata API."""
import logging
import os

import jwt
from flask import g, request

from app.exceptions import UnauthorizedError

logger = logging.getLogger(__name__)

PROJECT_ID = 'spese-dc'
ISSUER = f'https://securetoken.google.com/{PROJECT_ID}'
# Chiavi pubbliche Google con cui Firebase firma i token (tenute in cache dal client).
jwks = jwt.PyJWKClient(
    'https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com',
    lifespan=3600,
)

# Senza login: stato, keepalive e i cataloghi in sola lettura usati dalla modalità ospite dell'app.
PUBLIC_ENDPOINTS = {
    'api.api_home',
    'api.keepalive',
    'api.get_expense_types',
    'api.get_measurement_units',
}


def _verified_email(header):
    scheme, _, token = header.partition(' ')
    if scheme != 'Bearer' or not token:
        raise jwt.InvalidTokenError("token mancante")
    key = jwks.get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token, key, algorithms=['RS256'], audience=PROJECT_ID, issuer=ISSUER, leeway=10,
        options={'require': ['exp', 'iat', 'aud', 'iss', 'sub']},
    )
    if claims.get('email_verified') is not True or not claims.get('email'):
        raise jwt.InvalidTokenError("email assente o non verificata")
    return claims['email']


def require_auth():
    if request.method == 'OPTIONS' or request.endpoint in PUBLIC_ENDPOINTS:
        return
    try:
        g.auth_email = _verified_email(request.headers.get('Authorization', ''))
    except jwt.PyJWKClientConnectionError:
        raise  # chiavi Google irraggiungibili: è un errore del server (500), non del client
    except jwt.PyJWTError as e:
        # AUTH_REQUIRED=false è l'interruttore di emergenza: registra e lascia passare.
        if os.environ.get('AUTH_REQUIRED', 'true').lower() != 'false':
            raise UnauthorizedError() from e
        logger.error("Auth non obbligatoria: %s %s senza token valido (%s)", request.method, request.path, e)
