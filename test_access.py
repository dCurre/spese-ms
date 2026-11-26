"""Test di permessi e validazione sull'app reale, database SQLite in memoria: `python test_access.py`."""
from io import BytesIO
from types import SimpleNamespace

from sqlalchemy import BigInteger, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

import config

config.Config.SQLALCHEMY_DATABASE_URI = 'sqlite://'
config.Config.SQLALCHEMY_ENGINE_OPTIONS = {'poolclass': StaticPool}


@compiles(BigInteger, 'sqlite')
def _bigint(*_, **__):
    return 'INTEGER'  # in SQLite solo INTEGER si autoincrementa


@event.listens_for(Engine, 'connect')
def _connect(connection, _):
    connection.execute("ATTACH DATABASE ':memory:' AS spese")
    connection.create_function('to_char', 2, lambda value, fmt: str(value)[:7])


from app.database import db  # noqa: E402

_create_all = db.create_all


def _portable_create_all(*args, **kwargs):
    """I default 'now()' e 'false' sono scritti per Postgres."""
    for table in db.metadata.tables.values():
        for column in table.columns:
            raw = getattr(column.server_default, 'arg', None)
            if raw == 'now()':
                column.server_default.arg = text('CURRENT_TIMESTAMP')
            elif raw == 'false':
                column.server_default.arg = text('0')
    _create_all(*args, **kwargs)


db.create_all = _portable_create_all

from app import auth, create_app  # noqa: E402
from app.api.users import routes as users_routes  # noqa: E402
from app.database.expense_type import ExpenseType  # noqa: E402
from app.database.measurement_unit import MeasurementUnit  # noqa: E402
from app.database.user import User  # noqa: E402
from app.database.user_role import UserRole  # noqa: E402

auth._verified_email = lambda header: header.removeprefix('Bearer ')  # il token è l'email

app = create_app()
with app.app_context():
    db.session.add_all([UserRole(id=1, name='admin'), UserRole(id=2, name='user'),
                        UserRole(id=3, name='superadmin'), ExpenseType(id=1, name='Altro'),
                        MeasurementUnit(id=1, name='pezzo', symbol='pz', category='numero')])
    db.session.add_all([User(id=i, name=n, email=f'{n}@x.it', role_id=r) for i, n, r in
                        ((1, 'alice', 2), (2, 'bob', 2), (3, 'anna', 1), (4, 'sara', 3))])
    db.session.commit()

client = app.test_client()
checks = 0


def call(who, method, path, expect, body=None):
    global checks
    response = client.open('/api' + path, method=method, json=body,
                           headers={'Authorization': f'Bearer {who}@x.it'})
    assert response.status_code == expect, \
        f'{who} {method} {path}: {response.status_code} invece di {expect} {response.get_json()}'
    checks += 1
    return response.get_json()


A, B = 'alice', 'bob'

# ---------------------------------------------------------------- liste spese
lid = call(A, 'POST', '/expenses-lists', 201, {'name': 'Casa', 'user_id': 1, 'list_type': 'shared'})['id']
call(B, 'POST', '/expenses-lists', 403, {'name': 'x', 'user_id': 1, 'list_type': 'shared'})
call(A, 'POST', f'/expenses-lists/{lid}/participants', 201, {'user_id': 1})
expense = {'name': 'Pane', 'amount': '3.00', 'expense_owner_user_id': 1, 'expense_list_id': lid,
           'expense_date': '2026-11-20'}
eid = call(A, 'POST', '/expenses', 201, expense)['id']
call(A, 'POST', '/expenses', 400, {**expense, 'expense_owner_user_id': 2})  # bob non partecipa

for method, path, body in (
    ('GET', f'/expenses-lists/{lid}', None), ('GET', f'/expenses-lists/{lid}/balance', None),
    ('GET', f'/expenses-lists/{lid}/participants', None), ('GET', f'/expenses/by-list/{lid}', None),
    ('GET', f'/expenses/{eid}', None), ('PUT', f'/expenses/{eid}', {'name': 'rubata'}),
    ('DELETE', f'/expenses/{eid}', None), ('POST', '/expenses', {**expense, 'expense_owner_user_id': 2}),
    ('PUT', f'/expenses-lists/{lid}', {'name': 'rubata'}), ('DELETE', f'/expenses-lists/{lid}', None),
    ('POST', f'/expenses-lists/{lid}/participants', {'user_id': 2}),
    ('DELETE', f'/expenses-lists/{lid}/participants/1', None),
    ('POST', f'/expenses-lists/{lid}/transfer-owner', {'new_owner_id': 2, 'current_owner_id': 1}),
    ('POST', f'/expenses-lists/{lid}/invite-token', {}),
    ('GET', '/expenses-lists/delta?user_id=1', None), ('GET', '/expenses/stats?user_id=1', None),
    ('GET', '/users/by-email/alice@x.it/expenses-lists', None),
):
    call(B, method, path, 403, body)

assert call(B, 'GET', '/expenses', 200)['expenses'] == []
assert call(B, 'GET', '/expenses-lists', 200)['expenses_lists'] == []
assert call(B, 'POST', '/expenses/bulk-delete', 200, {'ids': [eid]})['deleted'] == 0
assert call(B, 'POST', '/expenses-lists/bulk-delete', 200, {'ids': [lid]})['deleted'] == 0
call(B, 'POST', '/expenses-lists/batch-sync', 200, {
    'lists_delete': [lid], 'expenses_delete': [eid], 'lists_update': [{'id': lid, 'name': 'rubata'}],
    'expenses_update': [{'id': eid, 'name': 'rubata'}],
    'expenses_create': [{'temp_id': 1, 'expense_list_id': lid, 'name': 'intrusa', 'amount': '1',
                         'expense_owner_user_id': 2, 'expense_date': '2026-11-20'}]})
assert call(A, 'GET', f'/expenses-lists/{lid}', 200)['name'] == 'Casa'
assert [e['name'] for e in call(A, 'GET', f'/expenses/by-list/{lid}', 200)['expenses']] == ['Pane']

# ospiti
guest = call(A, 'POST', '/users', 201, {'name': 'Ospite', 'is_guest': True})['id']
call(A, 'POST', f'/expenses-lists/{lid}/participants', 201, {'user_id': guest})
call(A, 'POST', f'/expenses-lists/{lid}/participants', 403, {'user_id': 2})  # persone: solo invito
other = call(B, 'POST', '/expenses-lists', 201, {'name': 'Bob', 'user_id': 2, 'list_type': 'shared'})['id']
call(B, 'POST', f'/expenses-lists/{other}/participants', 403, {'user_id': guest})  # ospite altrui
sneaky = call(B, 'POST', '/users', 201, {'name': 'x', 'email': 'new@x.it', 'is_guest': False})['id']
with app.app_context():
    created = db.session.get(User, sneaky)
    assert created.is_guest and created.email is None

# invito
token = call(A, 'POST', f'/expenses-lists/{lid}/invite-token', 200)['invite_token']
call(B, 'GET', '/expenses-lists/invite/sbagliato', 404)
assert call(B, 'GET', f'/expenses-lists/invite/{token}', 200)['is_member'] is False
call(B, 'POST', f'/expenses-lists/join/{token}', 200)
call(B, 'GET', f'/expenses-lists/{lid}', 200)
call(B, 'PUT', f'/expenses-lists/{lid}', 200, {'paid': True})
call(B, 'PUT', f'/expenses-lists/{lid}', 403, {'list_type': 'personal', 'requester_id': 1})
call(B, 'DELETE', f'/expenses-lists/{lid}/participants/1', 403)
call(B, 'DELETE', f'/expenses-lists/{lid}/invite-token', 403)
call(B, 'DELETE', f'/expenses-lists/{lid}', 200)  # il partecipante abbandona
call(B, 'GET', f'/expenses-lists/{lid}', 403)
call(A, 'GET', f'/expenses-lists/{lid}', 200)
call(A, 'DELETE', f'/expenses-lists/{lid}/participants/1/guest', 404)  # alice non è un ospite
call(A, 'DELETE', f'/expenses-lists/{lid}/participants/{guest}/guest', 404)  # manca il placeholder
with app.app_context():
    db.session.add(User(id=100, name='Eliminato', email='deleted@system.local', is_guest=False))
    db.session.commit()
call(A, 'DELETE', f'/expenses-lists/{lid}/participants/{guest}/guest', 200)
call(A, 'PUT', f'/expenses-lists/{lid}', 200, {'list_type': 'personal'})
call(B, 'POST', f'/expenses-lists/join/{token}', 404)  # token annullato
call(A, 'POST', f'/expenses-lists/{lid}/invite-token', 400)
synced = call(A, 'POST', '/expenses-lists/batch-sync', 200, {
    'lists_create': [{'temp_id': 7, 'name': 'Offline', 'user_id': 999, 'list_type': 'personal'}],
    'expenses_create': [{'temp_id': 8, 'list_temp_id': 7, 'name': 'Latte', 'amount': '1.20',
                         'expense_owner_user_id': 1, 'expense_date': '2026-11-20'}]})['id_map']
assert synced['lists'] and synced['expenses']
call(A, 'GET', '/expenses-lists/delta?user_id=1', 200)
call(A, 'GET', '/users/by-email/alice@x.it/expenses-lists', 200)

# ---------------------------------------------------------------- checklist
sid = call(A, 'POST', '/shopping-lists', 201, {'name': 'Spesa', 'owner_id': 1, 'list_type': 'shared'})['id']
call(B, 'POST', '/shopping-lists', 403, {'name': 'x', 'owner_id': 1})
cat = call(A, 'POST', '/shopping-categories', 201, {'shopping_list_id': sid, 'name': 'Frigo'})['id']
item = call(A, 'POST', '/shopping-items', 201, {'shopping_list_id': sid, 'name': 'Uova', 'category_id': cat})['id']
for method, path, body in (
    ('GET', f'/shopping-lists/{sid}', None), ('GET', '/shopping-lists/by-user/1', None),
    ('GET', '/shopping-lists/delta?user_id=1', None), ('PUT', f'/shopping-lists/{sid}', {'name': 'x'}),
    ('DELETE', f'/shopping-lists/{sid}', None), ('POST', f'/shopping-lists/{sid}/invite-token', {}),
    ('POST', f'/shopping-lists/{sid}/participants', {'user_id': 2}),
    ('POST', f'/shopping-lists/{sid}/transfer-ownership', {'new_owner_id': 2, 'old_owner_id': 1}),
    ('POST', f'/shopping-lists/{sid}/batch-save', {'items_delete': [item]}),
    ('POST', '/shopping-items', {'shopping_list_id': sid, 'name': 'x'}),
    ('PUT', f'/shopping-items/{item}', {'name': 'x'}), ('PATCH', f'/shopping-items/{item}/check', {}),
    ('DELETE', f'/shopping-items/{item}', None),
    ('PATCH', '/shopping-items/check-all', {'shopping_list_id': sid}),
    ('POST', '/shopping-categories', {'shopping_list_id': sid, 'name': 'x'}),
    ('PUT', f'/shopping-categories/{cat}', {'name': 'x'}), ('DELETE', f'/shopping-categories/{cat}', None),
    ('PATCH', f'/shopping-categories/{cat}/check', {}),
):
    call(B, method, path, 403, body)
call(B, 'PUT', '/shopping-items/bulk', 200, {'updates': [{'id': item, 'name': 'x'}], 'delete_ids': [item]})
call(B, 'PUT', '/shopping-items/reorder', 200, {'ordered_ids': [item]})
assert call(B, 'POST', '/shopping-lists/bulk-delete', 200, {'ids': [sid]})['deleted'] == 0
call(B, 'POST', '/shopping-lists/batch-sync', 200, {
    'lists_delete': [sid], 'categories_delete': [cat], 'items_delete': [item],
    'items_update': [{'id': item, 'name': 'x'}], 'categories_update': [{'id': cat, 'name': 'x'}],
    'items_create': [{'temp_id': 1, 'shopping_list_id': sid, 'name': 'intruso'}],
    'categories_create': [{'temp_id': 2, 'shopping_list_id': sid, 'name': 'intrusa'}]})
tree = call(A, 'GET', f'/shopping-lists/{sid}', 200)
assert tree['name'] == 'Spesa' and [c['name'] for c in tree['categories']] == ['Frigo']
assert [i['name'] for i in tree['categories'][0]['items']] == ['Uova'] and tree['items'] == []

# oggetti di un'altra lista non entrano nella propria
mine = call(B, 'POST', '/shopping-lists', 201, {'name': 'Bob', 'owner_id': 2})['id']
call(B, 'POST', '/shopping-items', 400, {'shopping_list_id': mine, 'name': 'x', 'category_id': cat})
call(B, 'POST', f'/shopping-lists/{mine}/batch-save', 400, {'categories_delete': [cat]})
call(B, 'POST', f'/shopping-lists/{mine}/batch-save', 200,
     {'categories_update': [{'id': cat, 'name': 'x'}], 'items_delete': [item]})
assert call(A, 'GET', f'/shopping-lists/{sid}', 200)['categories'][0]['name'] == 'Frigo'

invite = call(A, 'POST', f'/shopping-lists/{sid}/invite-token', 200)['invite_token']
call(B, 'POST', f'/shopping-lists/join/{invite}', 200, {'user_id': 999})
call(B, 'PATCH', f'/shopping-items/{item}/check', 200, {})
call(B, 'DELETE', f'/shopping-lists/{sid}/participants/1', 403)
call(B, 'DELETE', f'/shopping-lists/{sid}/invite-token', 403)
call(B, 'DELETE', f'/shopping-lists/{sid}', 200)
call(B, 'GET', f'/shopping-lists/{sid}', 403)
call(A, 'GET', f'/shopping-lists/{sid}', 200)
call(A, 'GET', '/shopping-lists/delta?user_id=1', 200)

# ---------------------------------------------------------------- prezzi
pid = call(A, 'POST', '/products', 201, {'name': 'Olio', 'default_unit_id': 1})['id']
buy = {'product_id': pid, 'user_id': 1, 'purchased_at': '2026-11-20', 'price': '8', 'quantity': '1', 'unit_id': 1}
pu = call(A, 'POST', '/purchases', 201, buy)['id']
call(B, 'POST', '/purchases', 403, buy)
assert call(B, 'GET', f'/products/{pid}/purchases', 200)['purchases'] == []
assert call(B, 'GET', f'/products/{pid}/price-history', 200)['data'] == []
assert call(B, 'GET', f'/products/{pid}', 200)['purchase_count'] == 0
call(B, 'PUT', f'/purchases/{pu}', 404, {'price': '0'})
call(B, 'DELETE', f'/purchases/{pu}', 404)
assert call(B, 'POST', '/purchases/bulk-delete', 200, {'ids': [pu]})['deleted'] == 0
call(B, 'DELETE', f'/products/{pid}', 403)
call(B, 'POST', '/products/bulk-delete', 403, {'ids': [pid]})
call(B, 'GET', '/products/delta?user_id=1', 403)
call(B, 'POST', '/products/batch-sync', 200, {
    'products_delete': [pid], 'purchases_delete': [pu], 'purchases_update': [{'id': pu, 'price': '0'}]})
mine_pu = call(A, 'GET', f'/products/{pid}/purchases', 200)['purchases']
assert len(mine_pu) == 1 and mine_pu[0]['price'] == 8
assert call(A, 'GET', '/products', 200)['products'][0]['purchase_count'] == 1
call(A, 'DELETE', f'/products/{pid}', 200)

# ---------------------------------------------------------------- utenti, ruoli, cataloghi
call(B, 'GET', '/users', 403)
call(B, 'GET', '/users/1', 403)
call(B, 'GET', '/users/by-email/alice@x.it', 403)
call(B, 'PUT', '/users/1', 403, {'name': 'x'})
call(B, 'PUT', '/users/2', 403, {'role_id': 3})
call(B, 'PUT', '/users/2', 403, {'role_id': 1, 'caller_email': 'sara@x.it'})
call(B, 'PUT', '/users/2', 403, {'email': 'alice@x.it'})
call(B, 'PUT', '/users/2', 200, {'name': 'Roberto'})
call(B, 'DELETE', '/users/1', 403)
call(B, 'PUT', '/users/1/profile-image/select', 403, {'url': 'x'})
call(B, 'POST', '/users/1/profile-image', 403)
assert call(B, 'POST', '/users/upsert-by-email', 200, {'email': 'alice@x.it'})['id'] == 2
assert call('nuovo', 'POST', '/users/upsert-by-email', 201, {'email': 'alice@x.it'})['email'] == 'nuovo@x.it'
call('fantasma', 'GET', '/expenses-lists', 403)  # token valido ma utente non registrato
for method, path in (('POST', '/user-roles'), ('PUT', '/user-roles/9'), ('DELETE', '/user-roles/9'),
                     ('POST', '/expense-types'), ('PUT', '/expense-types/1'), ('DELETE', '/expense-types/9'),
                     ('POST', '/measurement-units'), ('PUT', '/measurement-units/9'),
                     ('DELETE', '/measurement-units/9')):
    call(B, method, path, 403, {'name': 'x'})
call('anna', 'POST', '/expense-types', 201, {'name': 'Nuovo'})
call('anna', 'GET', '/users', 200)
call('anna', 'PUT', '/users/2', 403, {'name': 'x'})
call('anna', 'PUT', '/users/2', 403, {'role_id': 3, 'caller_email': 'anna@x.it'})
call('anna', 'PUT', '/users/4', 403, {'role_id': 2})
call('anna', 'PUT', '/users/3', 403, {'role_id': 2})
call('anna', 'PUT', '/users/2', 200, {'role_id': 1})
call('sara', 'PUT', '/users/2', 200, {'role_id': 3})

# ---------------------------------------------------------------- validazione
vl = call(A, 'POST', '/expenses-lists', 201, {'name': 'V', 'user_id': 1, 'list_type': 'shared'})['id']
good = {**expense, 'expense_list_id': vl}
ve = call(A, 'POST', '/expenses', 201, good)['id']
for bad in ({'amount': -1}, {'amount': 'abc'}, {'amount': 'NaN'}, {'amount': '1e30'}, {'amount': None},
            {'name': ''}, {'name': '   '}, {'name': 'x' * 256}, {'name': 5}, {'expense_date': 'ieri'},
            {'expense_date': None}):
    call(A, 'PUT', f'/expenses/{ve}', 400, bad)
    call(A, 'POST', '/expenses-lists/batch-sync', 400, {'expenses_update': [{'id': ve, **bad}]})
assert call(A, 'GET', f'/expenses/{ve}', 200)['name'] == 'Pane'
call(A, 'PUT', f'/expenses/{ve}', 200, {'amount': '12.50', 'expense_date': '2026-11-21'})
call(A, 'PUT', f'/expenses-lists/{vl}', 400, {'paid': 'si'})
call(A, 'PUT', f'/expenses-lists/{vl}', 400, {'name': ''})

vs = call(A, 'POST', '/shopping-lists', 201, {'name': 'V', 'owner_id': 1})['id']
vi = call(A, 'POST', '/shopping-items', 201, {'shopping_list_id': vs, 'name': 'x'})['id']
call(A, 'PUT', f'/shopping-lists/{vs}', 400, {'completed': 'no'})
call(A, 'PUT', f'/shopping-items/{vi}', 400, {'checked': 'x'})
call(A, 'PUT', f'/shopping-items/{vi}', 400, {'sort_order': 'x'})
call(A, 'PATCH', '/shopping-items/check-all', 400, {'shopping_list_id': vs, 'checked': 'x'})
call(A, 'PUT', f'/shopping-items/{vi}', 200, {'quantity': 3, 'checked': True})

vp = call(A, 'POST', '/products', 201, {'name': 'V', 'default_unit_id': 1})['id']
vbuy = call(A, 'POST', '/purchases', 201, {**buy, 'product_id': vp})['id']
for bad in ({'quantity': 0}, {'quantity': '0.0001'}, {'quantity': -2}, {'price': -1}, {'price': 'x'},
            {'purchased_at': '31/02/2026'}, {'store': 'x' * 151}):
    call(A, 'PUT', f'/purchases/{vbuy}', 400, bad)
    call(A, 'POST', '/products/batch-sync', 400, {'purchases_update': [{'id': vbuy, **bad}]})
call(A, 'PUT', f'/purchases/{vbuy}', 200, {'quantity': '1.5', 'price': '2', 'purchased_at': '2026-11-22'})
call(A, 'GET', '/products', 200)
call(A, 'GET', f'/products/{vp}/price-history?from=boh', 400)
call(A, 'GET', f'/products/{vp}/price-history?from=2026-01-01&to=2026-12-31', 200)
call('sara', 'PUT', '/users/4', 400, {'profile_image': 'javascript:alert(1)'})

# upload: conta il contenuto, non nome o content-type dichiarati
uploads = []


class _Bucket:
    def upload(self, path, data, options):
        uploads.append((path, options['content-type']))

    def get_public_url(self, path):
        return f'https://storage.example/{path}'


users_routes.get_supabase = lambda: SimpleNamespace(storage=SimpleNamespace(from_=lambda _: _Bucket()))
for content, name, expected in ((b'<html><script>', 'x.png', 400), (b'<svg/>', 'x.jpg', 400),
                                (b'\x89PNG\r\n\x1a\n' + b'0' * (5 * 1024 * 1024), 'big.png', 400),
                                (b'\x89PNG\r\n\x1a\nrest', 'finto.html', 200)):
    response = client.post('/api/users/1/profile-image', headers={'Authorization': 'Bearer alice@x.it'},
                           data={'file': (BytesIO(content), name, 'text/html')})
    assert response.status_code == expected, (name, response.status_code, response.get_json())
assert len(uploads) == 1 and uploads[0][0].endswith('.png') and uploads[0][1] == 'image/png'

# ---------------------------------------------------------------- limiti, CORS, segnalazioni
import os  # noqa: E402

from app import ratelimit  # noqa: E402
from app.api.bug_reports import routes as bug_routes  # noqa: E402

sent = []
bug_routes._create_issue = lambda token, payload: sent.append(payload) or {'number': 1, 'html_url': 'u'}
report = {'title': 'Crash di a@x.it', 'body': 'GET /api/users/by-email/a%40x.it ciao @qualcuno'}
os.environ.pop('GITHUB_BUGREPORT_TOKEN', None)
assert client.post('/api/bug-reports', json=report).status_code == 502
os.environ['GITHUB_BUGREPORT_TOKEN'] = 'finto'
assert client.post('/api/bug-reports', json={**report, 'title': ''}).status_code == 400
assert client.post('/api/bug-reports', json={**report, 'labels': ['security']}).status_code == 400
assert client.post('/api/bug-reports', json={**report, 'labels': [{}]}).status_code == 400
assert client.post('/api/bug-reports', json=report).status_code == 201  # senza login
text_sent = sent[0]['title'] + sent[0]['body']
assert 'x.it' not in text_sent and '@qualcuno' not in text_sent
codes = [client.post('/api/bug-reports', json=report).status_code for _ in range(25)]
assert codes.count(201) == 19 and codes[-1] == 429, codes

ratelimit._windows.clear()
auth.MAX_PER_MINUTE = 3
for expected in (200, 200, 200, 429):
    call(A, 'GET', '/expenses-lists', expected)
call(B, 'GET', '/expenses-lists', 200)  # il limite è per utente
auth.MAX_PER_MINUTE = 10_000

big = client.post('/api/expenses-lists/batch-sync', data=b'x' * (7 * 1024 * 1024),
                  content_type='application/json', headers={'Authorization': 'Bearer alice@x.it'})
assert big.status_code == 413, big.status_code
for origin, allowed in (('https://spese-dc.web.app', True), ('https://evil.example', False)):
    preflight = client.options('/api/users', headers={'Origin': origin, 'Access-Control-Request-Method': 'GET',
                                                      'Access-Control-Request-Headers': 'authorization'})
    assert (preflight.headers.get('Access-Control-Allow-Origin') == origin) is allowed, origin

print(f'OK ({checks} chiamate verificate)')
