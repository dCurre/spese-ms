"""Verifica dell'ID token Firebase richiesto su ogni chiamata API."""
import logging

import jwt
from flask import g, request

from app.exceptions import UnauthorizedError, TooManyRequestsError
from app.ratelimit import allow

logger = logging.getLogger(__name__)

PROJECT_ID = 'spese-dc'
ISSUER = f'https://securetoken.google.com/{PROJECT_ID}'
# Chiavi pubbliche Google con cui Firebase firma i token (tenute in cache dal client).
jwks = jwt.PyJWKClient(
    'https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com',
    lifespan=3600,
)

MAX_PER_MINUTE = 600  # per utente: largo per il sync, stretto per chi abusa

# Senza login: stato, keepalive, e ciò che serve alla modalità ospite dell'app.
PUBLIC_ENDPOINTS = {
    'api.api_home',
    'api.keepalive',
    'api.get_expense_types',
    'api.get_measurement_units',
    'api.create_bug_report',  # anche gli ospiti segnalano; limite proprio
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
        # Nel log il motivo e l'endpoint, non il path (può contenere email) né il token.
        logger.error("Token rifiutato: %s %s (%s)", request.method, request.endpoint, e)
        raise UnauthorizedError() from e
    if not allow(('user', g.auth_email), MAX_PER_MINUTE, 60):
        raise TooManyRequestsError()
