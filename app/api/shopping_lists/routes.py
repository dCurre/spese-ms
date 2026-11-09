import re
import secrets
from datetime import datetime, timezone
from flask import request, jsonify
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from app.api import api
from app.database import db
from app.database.shopping_list import ShoppingList, ShoppingItem, ShoppingCategory, ShoppingListParticipant
from app.api.shopping_items.routes import _norm_qty
from app.api.shopping_categories.routes import soft_delete_category
from app.exceptions import ValidationError, ForbiddenError
from app.schemas import parse_body, CreateShoppingListSchema
from app.audit import log_audit


def _soft_delete_list(sl):
    """Soft-delete di una lista: marca deleted=true la lista e propaga ai figli
    (categorie e articoli). I partecipanti restano (non sono entita' sincronizzate).
    Il trigger DB aggiorna updated_at; impostiamo deleted esplicitamente via bulk
    UPDATE per non caricare tutte le righe in sessione."""
    sl.deleted = True
    ShoppingCategory.query.filter_by(shopping_list_id=sl.id, deleted=False) \
        .update({'deleted': True}, synchronize_session=False)
    ShoppingItem.query.filter_by(shopping_list_id=sl.id, deleted=False) \
        .update({'deleted': True}, synchronize_session=False)


def _build_category_tree(list_id):
    """Carica tutte le categorie e item (non cancellati) di una lista in query flat e
    ricostruisce l'albero in Python. Supporta sottocategorie a profondità arbitraria
    senza join ricorsivi."""
    all_cats = ShoppingCategory.query.filter_by(shopping_list_id=list_id, deleted=False).all()
    all_items = ShoppingItem.query.filter_by(shopping_list_id=list_id, deleted=False).all()

    items_by_cat = {}
    uncategorized = []
    for item in all_items:
        if item.category_id is None:
            uncategorized.append(item)
        else:
            items_by_cat.setdefault(item.category_id, []).append(item)

    cat_by_id = {c.id: c for c in all_cats}
    children_by_parent = {}
    for c in all_cats:
        children_by_parent.setdefault(c.parent_id, []).append(c)

    def serialize_cat(c, visited=None):
        if visited is None:
            visited = set()
        if c.id in visited:
            return None
        visited = visited | {c.id}
        return {
            "id": c.id,
            "client_id": c.client_id,
            "shopping_list_id": c.shopping_list_id,
            "parent_id": c.parent_id,
            "name": c.name,
            "sort_order": c.sort_order,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "deleted": c.deleted,
            "items": [_serialize_item(i) for i in sorted(items_by_cat.get(c.id, []), key=lambda i: i.sort_order)],
            "children": [
                child_data
                for ch in sorted(children_by_parent.get(c.id, []), key=lambda ch: ch.sort_order)
                if (child_data := serialize_cat(ch, visited)) is not None
            ],
        }

    root_cats = sorted(children_by_parent.get(None, []), key=lambda c: c.sort_order)
    return (
        [serialize_cat(c) for c in root_cats],
        [_serialize_item(i) for i in sorted(uncategorized, key=lambda i: i.sort_order)],
        all_items,
    )


def _serialize_item(i):
    return {
        "id": i.id,
        "client_id": i.client_id,
        "shopping_list_id": i.shopping_list_id,
        "category_id": i.category_id,
        "name": i.name,
        "quantity": i.quantity,
        "checked": i.checked,
        "sort_order": i.sort_order,
        "created_at": i.created_at,
        "updated_at": i.updated_at,
        "deleted": i.deleted,
    }


def _serialize_category(c):
    """Serializza ricorsivamente una categoria con i suoi item e sottocategorie."""
    return {
        "id": c.id,
        "client_id": c.client_id,
        "shopping_list_id": c.shopping_list_id,
        "parent_id": c.parent_id,
        "name": c.name,
        "sort_order": c.sort_order,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
        "deleted": c.deleted,
        "items": [_serialize_item(i) for i in sorted(c.items, key=lambda i: i.sort_order) if not i.deleted],
        "children": [_serialize_category(child) for child in sorted(c.children or [], key=lambda ch: ch.sort_order) if not child.deleted],
    }


def _serialize_list(sl, include_items=False, items_count=None, checked_count=None, participant_count=None):
    if items_count is None or checked_count is None:
        counts = db.session.query(
            func.count(ShoppingItem.id),
            func.sum(func.cast(ShoppingItem.checked, db.Integer))
        ).filter_by(shopping_list_id=sl.id, deleted=False).one()
        items_count = counts[0] or 0
        checked_count = counts[1] or 0

    if participant_count is None:
        participant_count = db.session.query(func.count(ShoppingListParticipant.user_id)) \
            .filter_by(shopping_list_id=sl.id).scalar() or 0
        participant_count += 1  # includi owner

    data = {
        "id": sl.id,
        "client_id": sl.client_id,
        "name": sl.name,
        "owner_id": sl.owner_id,
        "list_type": sl.list_type,
        "completed": sl.completed,
        "starred": sl.starred,
        "invite_token": sl.invite_token,
        "created_at": sl.created_at,
        "updated_at": sl.updated_at,
        "deleted": sl.deleted,
        "items_count": items_count,
        "checked_count": checked_count,
        "participants_count": participant_count,
    }
    if include_items:
        data["participants"] = (
            [
                {
                    "user_id": sl.owner.id,
                    "shopping_list_id": sl.id,
                    "name": sl.owner.name,
                    "surname": sl.owner.surname,
                    "email": sl.owner.email,
                    "profile_image": sl.owner.profile_image,
                    "joined_at": sl.created_at,
                }
            ] if sl.owner else []
        ) + [
            {
                "user_id": p.user_id,
                "shopping_list_id": p.shopping_list_id,
                "name": p.user.name,
                "surname": p.user.surname,
                "email": p.user.email,
                "profile_image": p.user.profile_image,
                "joined_at": p.joined_at,
            }
            for p in (sl.participants or [])
        ]
        categories, uncategorized_items, _ = _build_category_tree(sl.id)
        data["categories"] = categories
        data["items"] = uncategorized_items
    return data


@api.route('/shopping-lists/by-user/<int:user_id>', methods=['GET'])
def get_shopping_lists_by_user(user_id):
    owned = ShoppingList.query.options(
        joinedload(ShoppingList.owner),
    ).filter_by(owner_id=user_id, deleted=False).all()

    shared_ids = db.session.query(ShoppingListParticipant.shopping_list_id).filter_by(user_id=user_id)
    shared = ShoppingList.query.options(
        joinedload(ShoppingList.owner),
    ).filter(ShoppingList.id.in_(shared_ids), ShoppingList.owner_id != user_id, ShoppingList.deleted == False).all()

    all_lists = owned + shared
    all_list_ids = [sl.id for sl in all_lists]

    counts_rows = db.session.query(
        ShoppingItem.shopping_list_id,
        func.count(ShoppingItem.id),
        func.sum(func.cast(ShoppingItem.checked, db.Integer))
    ).filter(ShoppingItem.shopping_list_id.in_(all_list_ids), ShoppingItem.deleted == False).group_by(ShoppingItem.shopping_list_id).all()
    counts_by_list = {row[0]: (row[1] or 0, row[2] or 0) for row in counts_rows}

    part_rows = db.session.query(
        ShoppingListParticipant.shopping_list_id,
        func.count(ShoppingListParticipant.user_id)
    ).filter(ShoppingListParticipant.shopping_list_id.in_(all_list_ids)).group_by(ShoppingListParticipant.shopping_list_id).all()
    parts_by_list = {row[0]: row[1] for row in part_rows}

    return jsonify({"shopping_lists": [
        _serialize_list(sl,
            items_count=counts_by_list.get(sl.id, (0, 0))[0],
            checked_count=counts_by_list.get(sl.id, (0, 0))[1],
            participant_count=parts_by_list.get(sl.id, 0) + 1,
        ) for sl in all_lists
    ]})


def _serialize_list_flat(sl):
    """Serializzazione piatta di una lista per il delta (senza tree/conteggi)."""
    return {
        "id": sl.id,
        "client_id": sl.client_id,
        "name": sl.name,
        "owner_id": sl.owner_id,
        "list_type": sl.list_type,
        "completed": sl.completed,
        "starred": sl.starred,
        "invite_token": sl.invite_token,
        "created_at": sl.created_at,
        "updated_at": sl.updated_at,
        "deleted": sl.deleted,
    }


def _serialize_category_flat(c):
    return {
        "id": c.id,
        "client_id": c.client_id,
        "shopping_list_id": c.shopping_list_id,
        "parent_id": c.parent_id,
        "name": c.name,
        "sort_order": c.sort_order,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
        "deleted": c.deleted,
    }


def _parse_since(raw):
    """Converte il query param `since` (ISO 8601) in datetime naive UTC,
    coerente con i TIMESTAMP (without time zone) salvati dal DB in UTC.

    Tollerante al caso in cui il '+' dell'offset sia stato decodificato come
    spazio (querystring non URL-encodata): '...946271 00:00' -> '...946271+00:00'.
    """
    if not raw:
        return None
    value = raw.strip()
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    # Un '+' nell'offset arriva come spazio se il client non URL-encoda il since:
    # ripristina solo uno spazio seguito da un offset 'HH:MM' a fine stringa.
    value = re.sub(r' (\d{2}:\d{2})$', r'+\1', value)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError("Parametro 'since' non è un timestamp ISO valido")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@api.route('/shopping-lists/delta', methods=['GET'])
def shopping_lists_delta():
    """Delta pull per il sync local-first.

    Query param:
      - user_id (obbligatorio): utente di cui scaricare le checklist.
      - since (opzionale, ISO 8601): se presente, ritorna solo le entità con
        updated_at > since; se assente, ritorna tutto.

    Ritorna TUTTE le entità checklist accessibili all'utente (liste possedute +
    condivise, con relative categorie e articoli) modificate dopo `since`,
    INCLUSE quelle con deleted=true (così l'app rimuove i dati localmente).

    `server_time` è l'ora corrente del DB: l'app la userà come prossimo `since`.
    """
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        raise ValidationError("user_id mancante")
    since = _parse_since(request.args.get('since'))

    # server_time PRIMA di leggere i dati: una riga modificata durante la query
    # avrà updated_at >= server_time e verrà ripresa al prossimo delta (niente buchi).
    server_time = db.session.query(func.now()).scalar()

    # Liste accessibili all'utente: possedute + condivise (come partecipante).
    # Qui NON filtriamo deleted: il delta deve includere le cancellazioni.
    owned_ids = db.session.query(ShoppingList.id).filter_by(owner_id=user_id)
    shared_ids = db.session.query(ShoppingListParticipant.shopping_list_id).filter_by(user_id=user_id)
    accessible_ids = [
        row[0] for row in owned_ids.union(shared_ids).all()
    ]

    if not accessible_ids:
        return jsonify({
            "server_time": server_time,
            "lists": [], "categories": [], "items": [],
        })

    lists_q = ShoppingList.query.filter(ShoppingList.id.in_(accessible_ids))
    cats_q = ShoppingCategory.query.filter(ShoppingCategory.shopping_list_id.in_(accessible_ids))
    items_q = ShoppingItem.query.filter(ShoppingItem.shopping_list_id.in_(accessible_ids))

    if since is not None:
        lists_q = lists_q.filter(ShoppingList.updated_at > since)
        cats_q = cats_q.filter(ShoppingCategory.updated_at > since)
        items_q = items_q.filter(ShoppingItem.updated_at > since)

    return jsonify({
        "server_time": server_time,
        "lists": [_serialize_list_flat(sl) for sl in lists_q.all()],
        "categories": [_serialize_category_flat(c) for c in cats_q.all()],
        "items": [_serialize_item(i) for i in items_q.all()],
    })


@api.route('/shopping-lists/<int:list_id>', methods=['GET'])
def get_shopping_list(list_id):
    sl = ShoppingList.query.options(
        joinedload(ShoppingList.owner),
        joinedload(ShoppingList.participants).joinedload(ShoppingListParticipant.user)
    ).filter_by(id=list_id, deleted=False).first_or_404()
    return jsonify(_serialize_list(sl, include_items=True))


@api.route('/shopping-lists', methods=['POST'])
def create_shopping_list():
    data = parse_body(CreateShoppingListSchema)
    client_id = data.get('client_id')

    # Create idempotente: client_id gia' visto per lo stesso owner -> update.
    existing = None
    if client_id:
        existing = ShoppingList.query.filter_by(
            owner_id=data['owner_id'], client_id=client_id
        ).first()

    if existing:
        existing.name = data['name']
        existing.list_type = data.get('list_type', 'personal')
        existing.completed = data.get('completed', False)
        existing.deleted = False
        db.session.commit()
        return jsonify({"id": existing.id, "client_id": existing.client_id, "message": "Checklist aggiornata"}), 200

    sl = ShoppingList(
        name=data['name'],
        owner_id=data['owner_id'],
        list_type=data.get('list_type', 'personal'),
        completed=data.get('completed', False),
        client_id=client_id,
    )
    db.session.add(sl)
    db.session.commit()
    return jsonify({"id": sl.id, "client_id": sl.client_id, "message": "Checklist creata"}), 201


@api.route('/shopping-lists/<int:list_id>', methods=['PUT'])
def update_shopping_list(list_id):
    sl = ShoppingList.query.get_or_404(list_id)
    data = request.get_json() or {}
    if 'name' in data: sl.name = data['name']
    if 'completed' in data: sl.completed = data['completed']
    if 'list_type' in data:
        # Solo il proprietario della lista può cambiarne il tipo.
        requester_id = data.get('requester_id')
        if not requester_id:
            raise ValidationError("requester_id mancante")
        if sl.owner_id != requester_id:
            raise ForbiddenError("Non sei il proprietario della lista")

        sl.list_type = data['list_type']
        # Diventa personale: rimuovi i partecipanti (una lista personale non ne ha).
        # Le checklist non hanno "owner delle spese", quindi non serve riassegnare nulla.
        if data['list_type'] == 'personal':
            ShoppingListParticipant.query.filter_by(shopping_list_id=sl.id).delete(
                synchronize_session=False,
            )
    if 'starred' in data: sl.starred = data['starred']
    db.session.commit()
    return jsonify({"message": "Checklist aggiornata"}), 200


@api.route('/shopping-lists/<int:list_id>', methods=['DELETE'])
def delete_shopping_list(list_id):
    # Soft-delete: marca deleted=true (lista + categorie + articoli) cosi' il
    # delta sync propaga la cancellazione all'app. Nessuna rimozione fisica.
    sl = ShoppingList.query.filter_by(id=list_id, deleted=False).first_or_404()
    _soft_delete_list(sl)
    db.session.commit()
    return jsonify({"message": "Checklist eliminata"}), 200


@api.route('/shopping-lists/bulk-delete', methods=['POST'])
def bulk_delete_shopping_lists():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids:
        raise ValidationError("ids mancante o vuoto")
    # Soft-delete di piu' liste: marca deleted=true su liste + categorie +
    # articoli. Nessuna rimozione fisica (il delta pull le restituira' per far
    # rimuovere i dati localmente all'app).
    lists = ShoppingList.query.filter(ShoppingList.id.in_(ids), ShoppingList.deleted == False).all()
    for sl in lists:
        _soft_delete_list(sl)
    db.session.commit()
    deleted = len(lists)
    return jsonify({"deleted": deleted, "message": f"{deleted} checklist eliminate"}), 200


@api.route('/shopping-lists/<int:list_id>/invite-token', methods=['POST'])
def generate_invite_token(list_id):
    sl = ShoppingList.query.get_or_404(list_id)
    if not sl.invite_token:
        sl.invite_token = secrets.token_urlsafe(32)
        db.session.commit()
    return jsonify({"invite_token": sl.invite_token}), 200


@api.route('/shopping-lists/<int:list_id>/invite-token', methods=['DELETE'])
def revoke_invite_token(list_id):
    sl = ShoppingList.query.get_or_404(list_id)
    sl.invite_token = None
    db.session.commit()
    return jsonify({"message": "Link revocato"}), 200


@api.route('/shopping-lists/join/<string:token>', methods=['POST'])
def join_by_token(token):
    sl = ShoppingList.query.filter_by(invite_token=token, deleted=False).first_or_404()
    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id:
        raise ValidationError("user_id mancante")

    if sl.owner_id == user_id:
        return jsonify({"id": sl.id, "message": "Sei il proprietario"}), 200

    existing = ShoppingListParticipant.query.filter_by(
        shopping_list_id=sl.id, user_id=user_id
    ).first()
    if not existing:
        p = ShoppingListParticipant(shopping_list_id=sl.id, user_id=user_id)
        db.session.add(p)
        db.session.commit()

    return jsonify({"id": sl.id, "message": "Aggiunto alla lista"}), 200


@api.route('/shopping-lists/<int:list_id>/transfer-ownership', methods=['POST'])
def transfer_ownership(list_id):
    # SELECT FOR UPDATE: serializza trasferimenti concorrenti sulla stessa lista
    sl = ShoppingList.query.filter_by(id=list_id).with_for_update().first_or_404()
    data = request.get_json() or {}
    new_owner_id = data.get('new_owner_id')
    old_owner_id = data.get('old_owner_id')
    if not new_owner_id or not old_owner_id:
        raise ValidationError("new_owner_id e old_owner_id obbligatori")
    if sl.owner_id != old_owner_id:
        raise ForbiddenError("Non sei il proprietario")

    existing = ShoppingListParticipant.query.filter_by(
        shopping_list_id=list_id, user_id=new_owner_id
    ).first()
    if not existing:
        raise ValidationError("Il nuovo owner deve essere un partecipante")

    sl.owner_id = new_owner_id
    db.session.delete(existing)
    old_entry = ShoppingListParticipant.query.filter_by(
        shopping_list_id=list_id, user_id=old_owner_id
    ).first()
    if old_entry:
        db.session.delete(old_entry)
    db.session.commit()
    log_audit("transfer_ownership", list_id=list_id, from_user_id=old_owner_id, to_user_id=new_owner_id)
    return jsonify({"message": "Ownership trasferita"}), 200


@api.route('/shopping-lists/<int:list_id>/participants', methods=['POST'])
def add_shopping_list_participant(list_id):
    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id:
        raise ValidationError("user_id mancante")
    existing = ShoppingListParticipant.query.filter_by(
        shopping_list_id=list_id, user_id=user_id
    ).first()
    if existing:
        return jsonify({"message": "Già partecipante"}), 200
    p = ShoppingListParticipant(shopping_list_id=list_id, user_id=user_id)
    db.session.add(p)
    db.session.commit()
    return jsonify({"message": "Partecipante aggiunto"}), 201


@api.route('/shopping-lists/<int:list_id>/batch-save', methods=['POST'])
def batch_save_list(list_id):
    """
    Salva in un'unica transazione tutte le modifiche della modifica multipla:
    - categories_update: [{id, name}]
    - categories_delete: [id, ...]
    - categories_create: [{temp_id, name, parent_id, sort_order}]
      parent_id può essere un id reale oppure un temp_id (stringa) se il parent è anch'esso nuovo
    - items_update: [{id, name, quantity, checked}]
    - items_delete: [id, ...]
    - items_create: [{name, quantity, checked, sort_order, category_id, category_temp_id}]
      category_temp_id usato se l'item appartiene a una categoria nuova (creata nello stesso batch)
    """
    ShoppingList.query.filter_by(id=list_id, deleted=False).first_or_404()
    data = request.get_json() or {}

    temp_id_map = {}

    # Soft-delete delle categorie (propaga ad articoli e sottocategorie).
    for cat_id in (data.get('categories_delete') or []):
        soft_delete_category(cat_id)
    db.session.flush()

    for upd in (data.get('categories_update') or []):
        cat = ShoppingCategory.query.get(upd['id'])
        if cat and upd.get('name', '').strip():
            cat.name = upd['name'].strip()

    new_cats = data.get('categories_create') or []
    deleted_cat_ids = set(data.get('categories_delete') or [])

    def _resolve_pid(pid):
        if pid is None:
            return None
        if isinstance(pid, str):
            return temp_id_map.get(pid)
        if isinstance(pid, int):
            return None if pid in deleted_cat_ids else pid
        return None

    def _parent_is_resolved(nc):
        pid = nc.get('parent_id')
        if pid is None:
            return True
        if isinstance(pid, int):
            return True
        return str(pid) in temp_id_map

    max_iter = len(new_cats) + 1
    remaining = list(new_cats)
    iteration = 0
    while remaining and iteration < max_iter:
        iteration += 1
        next_remaining = []
        for nc in remaining:
            if not _parent_is_resolved(nc):
                next_remaining.append(nc)
                continue
            pid = _resolve_pid(nc.get('parent_id'))
            # Create idempotente via client_id nella stessa lista.
            nc_client_id = nc.get('client_id')
            cat = None
            if nc_client_id:
                cat = ShoppingCategory.query.filter_by(
                    shopping_list_id=list_id, client_id=nc_client_id
                ).first()
            if cat:
                cat.parent_id = pid
                cat.name = nc['name'].strip()
                cat.sort_order = nc.get('sort_order', 0)
                cat.deleted = False
            else:
                cat = ShoppingCategory(
                    shopping_list_id=list_id,
                    parent_id=pid,
                    name=nc['name'].strip(),
                    sort_order=nc.get('sort_order', 0),
                    client_id=nc_client_id,
                )
                db.session.add(cat)
            db.session.flush()
            if nc.get('temp_id') is not None:
                temp_id_map[str(nc['temp_id'])] = cat.id
        remaining = next_remaining

    # Soft-delete degli articoli.
    for item_id in (data.get('items_delete') or []):
        item = ShoppingItem.query.get(item_id)
        if item and not item.deleted:
            item.deleted = True

    for upd in (data.get('items_update') or []):
        item = ShoppingItem.query.get(upd['id'])
        if not item:
            continue
        if 'name' in upd and upd['name'].strip():
            item.name = upd['name'].strip()
        if 'quantity' in upd:
            item.quantity = _norm_qty(upd['quantity'])
        if 'checked' in upd:
            item.checked = upd['checked']
        if 'category_id' in upd:
            item.category_id = upd['category_id']

    for ni in (data.get('items_create') or []):
        cat_id = ni.get('category_id')
        temp = ni.get('category_temp_id')
        if temp is not None:
            cat_id = temp_id_map.get(str(temp), cat_id)
        if not ni.get('name', '').strip():
            continue
        # Create idempotente via client_id nella stessa lista.
        ni_client_id = ni.get('client_id')
        item = None
        if ni_client_id:
            item = ShoppingItem.query.filter_by(
                shopping_list_id=list_id, client_id=ni_client_id
            ).first()
        if item:
            item.category_id = cat_id
            item.name = ni['name'].strip()
            item.quantity = _norm_qty(ni.get('quantity'))
            item.checked = ni.get('checked', False)
            item.sort_order = ni.get('sort_order', 0)
            item.deleted = False
        else:
            item = ShoppingItem(
                shopping_list_id=list_id,
                category_id=cat_id,
                name=ni['name'].strip(),
                quantity=_norm_qty(ni.get('quantity')),
                checked=ni.get('checked', False),
                sort_order=ni.get('sort_order', 0),
                client_id=ni_client_id,
            )
            db.session.add(item)

    db.session.commit()
    return jsonify({"message": "Batch salvato"}), 200


@api.route('/shopping-lists/batch-sync', methods=['POST'])
def batch_sync():
    """Push batch del sync local-first: create/update/delete misti su liste,
    categorie e articoli in un'unica transazione, per ridurre le chiamate.

    Body (tutti i blocchi sono opzionali):
      {
        "lists_create":      [{temp_id, name, owner_id, list_type?, completed?, starred?}],
        "lists_update":      [{id, name?, completed?, starred?}],
        "lists_delete":      [id, ...],
        "categories_create": [{temp_id, shopping_list_id|list_temp_id, parent_id|parent_temp_id?, name, sort_order?}],
        "categories_update": [{id, name?, sort_order?, parent_id?}],
        "categories_delete": [id, ...],
        "items_create":      [{temp_id, shopping_list_id|list_temp_id, category_id|category_temp_id?, name, quantity?, checked?, sort_order?}],
        "items_update":      [{id, name?, quantity?, checked?, sort_order?, category_id?}],
        "items_delete":      [id, ...]
      }

    `temp_id` è l'id locale dell'app: nelle risposte viene mappato all'id reale
    generato, così l'app aggiorna i propri riferimenti (local→remote).
    I riferimenti incrociati fra entità nuove usano i rispettivi *_temp_id.

    Risposta:
      {
        "server_time": "<timestamp>",
        "id_map": { "lists": {temp_id: id}, "categories": {...}, "items": {...} }
      }
    Ordine di applicazione: delete → create (liste, poi categorie con parent
    risolti iterativamente, poi articoli) → update.
    """
    data = request.get_json() or {}
    list_map = {}   # temp_id(str) -> id reale
    cat_map = {}
    item_map = {}

    # --- DELETE (soft) ---
    del_list_ids = data.get('lists_delete') or []
    for lid in del_list_ids:
        sl = ShoppingList.query.filter_by(id=lid, deleted=False).first()
        if sl:
            _soft_delete_list(sl)
    for cid in (data.get('categories_delete') or []):
        soft_delete_category(cid)
    for iid in (data.get('items_delete') or []):
        item = ShoppingItem.query.get(iid)
        if item and not item.deleted:
            item.deleted = True
    db.session.flush()

    # --- CREATE liste (idempotenti via client_id per owner) ---
    for nl in (data.get('lists_create') or []):
        if not (nl.get('name') or '').strip():
            continue
        cid = nl.get('client_id')
        sl = None
        if cid:
            sl = ShoppingList.query.filter_by(owner_id=nl['owner_id'], client_id=cid).first()
        if sl:
            sl.name = nl['name'].strip()
            sl.list_type = nl.get('list_type', 'personal')
            sl.completed = nl.get('completed', False)
            sl.starred = nl.get('starred', False)
            sl.deleted = False
        else:
            sl = ShoppingList(
                name=nl['name'].strip(),
                owner_id=nl['owner_id'],
                list_type=nl.get('list_type', 'personal'),
                completed=nl.get('completed', False),
                starred=nl.get('starred', False),
                client_id=cid,
            )
            db.session.add(sl)
        db.session.flush()
        if nl.get('temp_id') is not None:
            list_map[str(nl['temp_id'])] = sl.id

    def _resolve_list_id(obj):
        if obj.get('shopping_list_id') is not None:
            return obj['shopping_list_id']
        lt = obj.get('list_temp_id')
        return list_map.get(str(lt)) if lt is not None else None

    # --- CREATE categorie (risoluzione iterativa dei parent temp) ---
    new_cats = data.get('categories_create') or []

    def _cat_parent_resolved(nc):
        if nc.get('parent_id') is not None:
            return True
        pt = nc.get('parent_temp_id')
        if pt is None:
            return True
        return str(pt) in cat_map

    def _resolve_cat_parent(nc):
        if nc.get('parent_id') is not None:
            return nc['parent_id']
        pt = nc.get('parent_temp_id')
        return cat_map.get(str(pt)) if pt is not None else None

    remaining = list(new_cats)
    max_iter = len(new_cats) + 1
    iteration = 0
    while remaining and iteration < max_iter:
        iteration += 1
        next_remaining = []
        for nc in remaining:
            if not _cat_parent_resolved(nc):
                next_remaining.append(nc)
                continue
            if not (nc.get('name') or '').strip():
                continue
            nc_list_id = _resolve_list_id(nc)
            cid = nc.get('client_id')
            cat = None
            if cid and nc_list_id is not None:
                cat = ShoppingCategory.query.filter_by(shopping_list_id=nc_list_id, client_id=cid).first()
            if cat:
                cat.parent_id = _resolve_cat_parent(nc)
                cat.name = nc['name'].strip()
                cat.sort_order = nc.get('sort_order', 0)
                cat.deleted = False
            else:
                cat = ShoppingCategory(
                    shopping_list_id=nc_list_id,
                    parent_id=_resolve_cat_parent(nc),
                    name=nc['name'].strip(),
                    sort_order=nc.get('sort_order', 0),
                    client_id=cid,
                )
                db.session.add(cat)
            db.session.flush()
            if nc.get('temp_id') is not None:
                cat_map[str(nc['temp_id'])] = cat.id
        remaining = next_remaining

    # --- CREATE articoli ---
    for ni in (data.get('items_create') or []):
        if not (ni.get('name') or '').strip():
            continue
        cat_id = ni.get('category_id')
        ct = ni.get('category_temp_id')
        if ct is not None:
            cat_id = cat_map.get(str(ct), cat_id)
        ni_list_id = _resolve_list_id(ni)
        cid = ni.get('client_id')
        item = None
        if cid and ni_list_id is not None:
            item = ShoppingItem.query.filter_by(shopping_list_id=ni_list_id, client_id=cid).first()
        if item:
            item.category_id = cat_id
            item.name = ni['name'].strip()
            item.quantity = _norm_qty(ni.get('quantity'))
            item.checked = ni.get('checked', False)
            item.sort_order = ni.get('sort_order', 0)
            item.deleted = False
        else:
            item = ShoppingItem(
                shopping_list_id=ni_list_id,
                category_id=cat_id,
                name=ni['name'].strip(),
                quantity=_norm_qty(ni.get('quantity')),
                checked=ni.get('checked', False),
                sort_order=ni.get('sort_order', 0),
                client_id=cid,
            )
            db.session.add(item)
        db.session.flush()
        if ni.get('temp_id') is not None:
            item_map[str(ni['temp_id'])] = item.id

    # --- UPDATE liste ---
    for ul in (data.get('lists_update') or []):
        sl = ShoppingList.query.filter_by(id=ul['id'], deleted=False).first()
        if not sl:
            continue
        if 'name' in ul and (ul['name'] or '').strip():
            sl.name = ul['name'].strip()
        if 'completed' in ul:
            sl.completed = ul['completed']
        if 'starred' in ul:
            sl.starred = ul['starred']

    # --- UPDATE categorie ---
    for uc in (data.get('categories_update') or []):
        cat = ShoppingCategory.query.filter_by(id=uc['id'], deleted=False).first()
        if not cat:
            continue
        if 'name' in uc and (uc['name'] or '').strip():
            cat.name = uc['name'].strip()
        if 'sort_order' in uc:
            cat.sort_order = uc['sort_order']
        if 'parent_id' in uc:
            cat.parent_id = uc['parent_id']

    # --- UPDATE articoli ---
    for ui in (data.get('items_update') or []):
        item = ShoppingItem.query.filter_by(id=ui['id'], deleted=False).first()
        if not item:
            continue
        if 'name' in ui and (ui['name'] or '').strip():
            item.name = ui['name'].strip()
        if 'quantity' in ui:
            item.quantity = _norm_qty(ui['quantity'])
        if 'checked' in ui:
            item.checked = ui['checked']
        if 'sort_order' in ui:
            item.sort_order = ui['sort_order']
        if 'category_id' in ui:
            item.category_id = ui['category_id']

    db.session.commit()
    server_time = db.session.query(func.now()).scalar()
    return jsonify({
        "server_time": server_time,
        "id_map": {"lists": list_map, "categories": cat_map, "items": item_map},
    }), 200


@api.route('/shopping-lists/<int:list_id>/participants/<int:user_id>', methods=['DELETE'])
def remove_shopping_list_participant(list_id, user_id):
    p = ShoppingListParticipant.query.filter_by(
        shopping_list_id=list_id, user_id=user_id
    ).first_or_404()
    db.session.delete(p)
    db.session.commit()
    return jsonify({"message": "Partecipante rimosso"}), 200
