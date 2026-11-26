"""Segnalazioni dell'app (bug e richieste) → issue GitHub. Il token GitHub vive solo qui: non deve
mai finire nell'APK. L'endpoint è pubblico (anche l'ospite segnala), quindi è limitato."""
import json
import os
import re
import urllib.request

from flask import jsonify, request

from app import validation as check
from app.api import api
from app.exceptions import TooManyRequestsError, UpstreamError
from app.ratelimit import allow

ISSUES_URL = 'https://api.github.com/repos/dCurre/spese-app/issues'
LABELS = {'bug', 'enhancement'}
MAX_PER_HOUR = 20
_EMAIL = re.compile(r'[\w.+-]+(?:@|%40)[\w-]+(?:\.[\w-]+)+', re.IGNORECASE)


def _public_text(value):
    """Le issue sono pubbliche: via le email, e le menzioni non devono notificare nessuno."""
    return _EMAIL.sub('[email]', value).replace('@', '@​')


def _create_issue(token, payload):
    req = urllib.request.Request(
        ISSUES_URL, data=json.dumps(payload).encode(), method='POST',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'User-Agent': 'spese-ms'},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


@api.route('/bug-reports', methods=['POST'])
def create_bug_report():
    data = request.get_json(silent=True) or {}
    title = check.text(data.get('title'), 'title', 200)
    body = check.text(data.get('body'), 'body', 12000)
    labels = data.get('labels') or ['bug']
    if not isinstance(labels, list) or not all(isinstance(x, str) and x in LABELS for x in labels):
        check.one_of(labels, 'labels', sorted(LABELS))

    token = os.environ.get('GITHUB_BUGREPORT_TOKEN')
    if not token:
        raise UpstreamError("Segnalazioni non configurate sul server")
    if not allow('bug-reports', MAX_PER_HOUR, 3600):
        raise TooManyRequestsError()
    try:
        issue = _create_issue(token, {'title': _public_text(title), 'body': _public_text(body), 'labels': labels})
    except OSError as e:  # include gli errori HTTP di urllib
        raise UpstreamError("Invio della segnalazione non riuscito") from e
    return jsonify({"number": issue['number'], "html_url": issue['html_url']}), 201
