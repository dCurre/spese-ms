"""Limite di richieste a finestra fissa."""
import time

# shortcut: contatori in memoria del singolo processo (Render: un'istanza). Con più worker o istanze
# servirà uno store condiviso.
_windows = {}


def allow(key, limit, seconds):
    """Conta una richiesta per `key` e dice se rientra in `limit` richieste ogni `seconds`."""
    window = int(time.monotonic() // seconds)
    current, count = _windows.get(key, (window, 0))
    count = count + 1 if current == window else 1
    _windows[key] = (window, count)
    return count <= limit
