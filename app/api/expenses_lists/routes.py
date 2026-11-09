import re
from datetime import datetime, timezone
from flask import request, jsonify
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from app.api import api
from app.database import db
from app.database.expenses_list import ExpensesList
from app.database.expense import Expense
from app.database.expenses_list_participant import ExpensesListParticipant
from app.database.list_type import ListType
from app.exceptions import ValidationError, ForbiddenError
from app.schemas import parse_body, CreateExpensesListSchema
from app.audit import log_audit


def _parse_since(raw):
    """Converte il query param `since` (ISO 8601) in datetime naive UTC.
    Tollera 'Z', offset, e il '+' decodificato come spazio in querystring."""
    if not raw:
        return None
    value = raw.strip()
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    value = re.sub(r' (\d{2}:\d{2})$', r'+\1', value)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError("Parametro 'since' non è un timestamp ISO valido")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _soft_delete_expenses_list(el):
    """Soft-delete di una lista spese: marca deleted=true la lista e propaga
    alle sue spese. I partecipanti/inviti restano gestiti dagli endpoint online
    (non entrano nel delta)."""
    el.deleted = True
    Expense.query.filter_by(expense_list_id=el.id, deleted=False) \
        .update({'deleted': True}, synchronize_session=False)


@api.route('/expenses-lists', methods=['GET'])
def get_expenses_lists():
    show_paid = request.args.get('paid', default=None, type=lambda v: v.lower() == 'true')
    query = ExpensesList.query.filter_by(deleted=False)
    if show_paid is not None:
        query = query.filter_by(paid=show_paid)
    expenses_lists = query.options(joinedload(ExpensesList.list_type)).order_by(ExpensesList.id).all()
    return jsonify({
        "expenses_lists": [
            {
                "id": el.id,
                "client_id": el.client_id,
                "name": el.name,
                "user_id": el.user_id,
                "paid": el.paid,
                "created_at": el.created_at,
                "updated_at": el.updated_at,
                "deleted": el.deleted,
                "list_type": el.list_type.name if el.list_type else "shared",
                "max_participants": el.list_type.max_participants if el.list_type else 8,
            }
            for el in expenses_lists
        ]
    })


@api.route('/expenses-lists/<int:list_id>', methods=['GET'])
def get_expenses_list(list_id):
    el = ExpensesList.query.options(joinedload(ExpensesList.list_type)) \
        .filter_by(id=list_id, deleted=False).first_or_404()
    return jsonify({
        "id": el.id,
        "client_id": el.client_id,
        "name": el.name,
        "user_id": el.user_id,
        "paid": el.paid,
        "created_at": el.created_at,
        "updated_at": el.updated_at,
        "deleted": el.deleted,
        "list_type": el.list_type.name if el.list_type else "shared",
        "max_participants": el.list_type.max_participants if el.list_type else 8,
        "participants": [
            {
                "user_id": p.user_id,
                "name": p.user.name,
                "surname": p.user.surname,
                "email": p.user.email,
                "profile_image": p.user.profile_image,
                "joined_at": p.joined_at,
                "is_guest": bool(p.user.is_guest),
            }
            for p in el.participants
        ]
    })


@api.route('/expenses-lists', methods=['POST'])
def create_expenses_list():
    data = parse_body(CreateExpensesListSchema)
    type_name = data.get('list_type', 'shared')
    list_type = ListType.query.filter_by(name=type_name).first()
    client_id = data.get('client_id')

    # Create idempotente: client_id gia' visto per lo stesso user -> update.
    existing = None
    if client_id:
        existing = ExpensesList.query.filter_by(user_id=data['user_id'], client_id=client_id).first()
    if existing:
        existing.name = data['name']
        existing.paid = data.get('paid', False)
        existing.list_type_id = list_type.id if list_type else 1
        existing.deleted = False
        db.session.commit()
        return jsonify({"id": existing.id, "client_id": existing.client_id, "message": "Lista aggiornata"}), 200

    expenses_list = ExpensesList(
        name=data['name'],
        user_id=data['user_id'],
        paid=data.get('paid', False),
        list_type_id=list_type.id if list_type else 1,
        client_id=client_id,
    )
    db.session.add(expenses_list)
    db.session.commit()
    return jsonify({"id": expenses_list.id, "client_id": expenses_list.client_id, "message": "Lista creata"}), 201


@api.route('/expenses-lists/<int:list_id>', methods=['PUT'])
def update_expenses_list(list_id):
    el = ExpensesList.query.get_or_404(list_id)
    data = request.get_json() or {}
    if 'name' in data: el.name = data['name']
    if 'paid' in data: el.paid = data['paid']

    if 'list_type' in data:
        type_name = data['list_type']

        # Solo il proprietario della lista può cambiarne il tipo.
        requester_id = data.get('requester_id')
        if not requester_id:
            raise ValidationError("requester_id mancante")
        if el.user_id != requester_id:
            raise ForbiddenError("Non sei il proprietario della lista")

        list_type = ListType.query.filter_by(name=type_name).first()
        if not list_type:
            raise ValidationError(f"Tipo lista non valido: {type_name}")
        el.list_type_id = list_type.id

        # Diventa personale: tutte le spese passano al proprietario della lista
        # e gli altri partecipanti vengono rimossi. L'owner e' esso stesso un
        # partecipante (ha un record in expenses_list_participants): va mantenuto,
        # cosi' una lista personale resta con 1 partecipante (il proprietario).
        if type_name == 'personal':
            Expense.query.filter_by(expense_list_id=el.id, deleted=False).update(
                {Expense.expense_owner_user_id: el.user_id},
                synchronize_session=False,
            )
            ExpensesListParticipant.query.filter(
                ExpensesListParticipant.expenses_list_id == el.id,
                ExpensesListParticipant.user_id != el.user_id,
            ).delete(synchronize_session=False)

    db.session.commit()
    return jsonify({"message": "Lista aggiornata"}), 200


@api.route('/expenses-lists/<int:list_id>/transfer-owner', methods=['POST'])
def transfer_owner(list_id):
    data = request.get_json() or {}
    new_owner_id = data.get('new_owner_id')
    current_owner_id = data.get('current_owner_id')
    if not new_owner_id or not current_owner_id:
        raise ValidationError("Parametri mancanti")

    # SELECT FOR UPDATE: serializza trasferimenti concorrenti sulla stessa lista
    el = ExpensesList.query.filter_by(id=list_id).with_for_update().first_or_404()
    if el.user_id != current_owner_id:
        raise ForbiddenError("Non sei il proprietario della lista")

    from app.database.expenses_list_participant import ExpensesListParticipant
    from app.database.user import User as UserModel
    new_owner = UserModel.query.get(new_owner_id)
    if not new_owner or new_owner.is_guest:
        raise ValidationError("Un ospite non può essere proprietario di una lista")

    is_participant = ExpensesListParticipant.query.filter_by(
        expenses_list_id=list_id, user_id=new_owner_id
    ).first()
    if not is_participant:
        raise ValidationError("Il nuovo owner deve essere un partecipante")

    el.user_id = new_owner_id

    old_owner = ExpensesListParticipant.query.filter_by(
        expenses_list_id=list_id, user_id=current_owner_id
    ).first()
    if old_owner:
        db.session.delete(old_owner)

    db.session.commit()
    log_audit("transfer_owner", list_id=list_id, from_user_id=current_owner_id, to_user_id=new_owner_id)
    return jsonify({"message": "Ownership trasferita"}), 200


@api.route('/expenses-lists/<int:list_id>/balance', methods=['GET'])
def get_expenses_list_balance(list_id):
    expenses = (
        Expense.query
        .options(joinedload(Expense.user))
        .filter_by(expense_list_id=list_id, deleted=False)
        .all()
    )
    map_pagato = {}
    for e in expenses:
        key = f"{e.user.name} {e.user.surname or ''}".strip()
        map_pagato[key] = map_pagato.get(key, 0) + float(e.amount)

    balance = []
    for buyer, buyer_paid in map_pagato.items():
        for receiver, receiver_paid in map_pagato.items():
            if buyer != receiver:
                balance.append({
                    "buyer": buyer,
                    "receiver": receiver,
                    "toPay": round((receiver_paid - buyer_paid) / len(map_pagato), 2),
                })
    return jsonify({
        "balance": balance,
        "totals": [{"name": k, "amount": round(v, 2)} for k, v in sorted(map_pagato.items())],
    })


@api.route('/expenses-lists/<int:list_id>', methods=['DELETE'])
def delete_expenses_list(list_id):
    # Soft-delete: marca deleted=true la lista e propaga alle sue spese.
    expenses_list = ExpensesList.query.filter_by(id=list_id, deleted=False).first_or_404()
    _soft_delete_expenses_list(expenses_list)
    db.session.commit()
    return jsonify({"message": "Lista eliminata"}), 200


@api.route('/expenses-lists/bulk-delete', methods=['POST'])
def bulk_delete_expenses_lists():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids:
        raise ValidationError("ids mancante o vuoto")
    # Soft-delete: marca deleted=true su liste + relative spese. Partecipanti e
    # inviti restano gestiti dagli endpoint online (fuori dal delta).
    lists = ExpensesList.query.filter(ExpensesList.id.in_(ids), ExpensesList.deleted == False).all()
    for el in lists:
        _soft_delete_expenses_list(el)
    db.session.commit()
    deleted = len(lists)
    return jsonify({"deleted": deleted, "message": f"{deleted} liste eliminate"}), 200


def _serialize_expenses_list_flat(el):
    return {
        "id": el.id,
        "client_id": el.client_id,
        "name": el.name,
        "user_id": el.user_id,
        "paid": el.paid,
        "list_type_id": el.list_type_id,
        "created_at": el.created_at,
        "updated_at": el.updated_at,
        "deleted": el.deleted,
    }


def _serialize_expense_flat(e):
    return {
        "id": e.id,
        "client_id": e.client_id,
        "name": e.name,
        "amount": e.amount,
        "expense_owner_user_id": e.expense_owner_user_id,
        "modified_by": e.modified_by,
        "expense_list_id": e.expense_list_id,
        "expense_date": e.expense_date,
        "expense_type_id": e.expense_type_id,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
        "deleted": e.deleted,
    }


@api.route('/expenses-lists/delta', methods=['GET'])
def expenses_lists_delta():
    """Delta pull per il sync local-first delle SPESE.

    Query param: user_id (obbligatorio), since (ISO 8601, opzionale).
    Ritorna le liste spese accessibili all'utente (possedute + condivise come
    partecipante) e le relative spese, modificate dopo since, INCLUSE le
    deleted=true. `server_time` (ISO) va usato come prossimo since.
    """
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        raise ValidationError("user_id mancante")
    since = _parse_since(request.args.get('since'))

    server_time = db.session.query(func.now()).scalar()

    owned_ids = db.session.query(ExpensesList.id).filter_by(user_id=user_id)
    shared_ids = db.session.query(ExpensesListParticipant.expenses_list_id).filter_by(user_id=user_id)
    accessible_ids = [row[0] for row in owned_ids.union(shared_ids).all()]

    if not accessible_ids:
        return jsonify({"server_time": server_time, "lists": [], "expenses": []})

    lists_q = ExpensesList.query.filter(ExpensesList.id.in_(accessible_ids))
    exp_q = Expense.query.filter(Expense.expense_list_id.in_(accessible_ids))
    if since is not None:
        lists_q = lists_q.filter(ExpensesList.updated_at > since)
        exp_q = exp_q.filter(Expense.updated_at > since)

    return jsonify({
        "server_time": server_time,
        "lists": [_serialize_expenses_list_flat(el) for el in lists_q.all()],
        "expenses": [_serialize_expense_flat(e) for e in exp_q.all()],
    })


@api.route('/expenses-lists/batch-sync', methods=['POST'])
def expenses_batch_sync():
    """Push batch del sync local-first per le SPESE: create/update/delete misti
    su liste spese e spese in un'unica transazione.

    Body (blocchi opzionali):
      lists_create:   [{temp_id, client_id?, name, user_id, paid?, list_type?}]
      lists_update:   [{id, name?, paid?}]
      lists_delete:   [id, ...]
      expenses_create:[{temp_id, client_id?, expense_list_id|list_temp_id, name, amount,
                        expense_owner_user_id, expense_date, expense_type_id?, modified_by?}]
      expenses_update:[{id, name?, amount?, expense_date?, expense_owner_user_id?,
                        expense_type_id?, modified_by?}]
      expenses_delete:[id, ...]

    client_id dedup per scope (user per le liste, lista per le spese); temp_id per
    referenziare una lista nuova da una spesa nuova. Risposta: { server_time, id_map }.
    """
    from app.api.expenses.routes import parse_date
    data = request.get_json() or {}
    list_map = {}
    expense_map = {}

    # --- DELETE (soft) ---
    for lid in (data.get('lists_delete') or []):
        el = ExpensesList.query.filter_by(id=lid, deleted=False).first()
        if el:
            _soft_delete_expenses_list(el)
    for eid in (data.get('expenses_delete') or []):
        e = Expense.query.get(eid)
        if e and not e.deleted:
            e.deleted = True
    db.session.flush()

    # --- CREATE liste (idempotenti via client_id per user) ---
    for nl in (data.get('lists_create') or []):
        if not (nl.get('name') or '').strip():
            continue
        list_type = ListType.query.filter_by(name=nl.get('list_type', 'shared')).first()
        cid = nl.get('client_id')
        el = None
        if cid:
            el = ExpensesList.query.filter_by(user_id=nl['user_id'], client_id=cid).first()
        if el:
            el.name = nl['name']
            el.paid = nl.get('paid', False)
            el.list_type_id = list_type.id if list_type else 1
            el.deleted = False
        else:
            el = ExpensesList(
                name=nl['name'],
                user_id=nl['user_id'],
                paid=nl.get('paid', False),
                list_type_id=list_type.id if list_type else 1,
                client_id=cid,
            )
            db.session.add(el)
        db.session.flush()
        if nl.get('temp_id') is not None:
            list_map[str(nl['temp_id'])] = el.id

    def _resolve_list_id(obj):
        if obj.get('expense_list_id') is not None:
            return obj['expense_list_id']
        lt = obj.get('list_temp_id')
        return list_map.get(str(lt)) if lt is not None else None

    # --- CREATE spese (idempotenti via client_id per lista) ---
    for ne in (data.get('expenses_create') or []):
        list_id = _resolve_list_id(ne)
        cid = ne.get('client_id')
        e = None
        if cid and list_id is not None:
            e = Expense.query.filter_by(expense_list_id=list_id, client_id=cid).first()
        if e:
            e.name = ne.get('name')
            if ne.get('amount') is not None:
                e.amount = ne['amount']
            if ne.get('expense_date') is not None:
                e.expense_date = parse_date(ne['expense_date'])
            if ne.get('expense_owner_user_id') is not None:
                e.expense_owner_user_id = ne['expense_owner_user_id']
            e.expense_type_id = ne.get('expense_type_id')
            e.modified_by = ne.get('modified_by')
            e.deleted = False
        else:
            e = Expense(
                name=ne.get('name'),
                amount=ne.get('amount'),
                expense_owner_user_id=ne['expense_owner_user_id'],
                expense_list_id=list_id,
                expense_date=parse_date(ne['expense_date']),
                expense_type_id=ne.get('expense_type_id'),
                modified_by=ne.get('modified_by'),
                client_id=cid,
            )
            db.session.add(e)
        db.session.flush()
        if ne.get('temp_id') is not None:
            expense_map[str(ne['temp_id'])] = e.id

    # --- UPDATE liste ---
    for ul in (data.get('lists_update') or []):
        el = ExpensesList.query.filter_by(id=ul['id'], deleted=False).first()
        if not el:
            continue
        if 'name' in ul:
            el.name = ul['name']
        if 'paid' in ul:
            el.paid = ul['paid']

    # --- UPDATE spese ---
    for ue in (data.get('expenses_update') or []):
        e = Expense.query.filter_by(id=ue['id'], deleted=False).first()
        if not e:
            continue
        if 'name' in ue:
            e.name = ue['name']
        if 'amount' in ue:
            e.amount = ue['amount']
        if 'expense_date' in ue:
            e.expense_date = parse_date(ue['expense_date'])
        if 'expense_owner_user_id' in ue:
            e.expense_owner_user_id = ue['expense_owner_user_id']
        if 'expense_type_id' in ue:
            e.expense_type_id = ue['expense_type_id']
        if 'modified_by' in ue:
            e.modified_by = ue['modified_by']

    db.session.commit()
    server_time = db.session.query(func.now()).scalar()
    return jsonify({
        "server_time": server_time,
        "id_map": {"lists": list_map, "expenses": expense_map},
    }), 200
