"""Controlli sui valori scritti nel database. I modelli li applicano con @validates, quindi valgono
per ogni strada di scrittura (API, batch-sync). Le update massive via query li saltano: lì vanno
chiamati a mano."""
from datetime import date
from decimal import Decimal, InvalidOperation

from app.exceptions import ValidationError

MAX_AMOUNT = Decimal('99999999.99')   # Numeric(10, 2)
MAX_QUANTITY = Decimal('9999999.999')  # Numeric(10, 3)


def _fail(field, reason):
    raise ValidationError(f"Valore non valido per '{field}': {reason}")


def text(value, field, max_length, required=True):
    if value is None or value == '':
        if required:
            _fail(field, "obbligatorio")
        return value
    if not isinstance(value, str):
        _fail(field, "deve essere un testo")
    if len(value) > max_length:
        _fail(field, f"massimo {max_length} caratteri")
    if required and not value.strip():
        _fail(field, "obbligatorio")
    return value


def https_url(value, field):
    value = text(value, field, 2000, required=False)
    if value and not value.startswith('https://'):
        _fail(field, "deve essere un indirizzo https")
    return value


def number(value, field, minimum, maximum, places):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        _fail(field, "deve essere un numero")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        _fail(field, "deve essere un numero")
    if not result.is_finite() or abs(result) > maximum:
        _fail(field, "fuori dall'intervallo ammesso")
    # Prima si arrotonda come farà il database, poi si controlla il minimo (0.0004 diventa 0).
    result = result.quantize(Decimal(1).scaleb(-places))
    if result < minimum:
        _fail(field, f"minimo {minimum}")
    return result


def integer(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _fail(field, f"intero tra {minimum} e {maximum}")
    return value


def boolean(value, field):
    if not isinstance(value, bool):
        _fail(field, "deve essere vero o falso")
    return value


def one_of(value, field, allowed):
    if value not in allowed:
        _fail(field, f"valori ammessi: {', '.join(allowed)}")
    return value


def day(value, field):
    """Accetta una data o una stringa yyyy-MM-dd."""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            _fail(field, "data attesa nel formato yyyy-MM-dd")
    if not isinstance(value, date) or not 1900 <= value.year <= 2100:
        _fail(field, "data non valida")
    return value
