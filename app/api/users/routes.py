import os
import uuid
import json
from flask import request, jsonify
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from supabase import create_client
from app.api import api
from app.database import db
from app.database.user import User
from app.database.user_role import UserRole
from app.database.expenses_list import ExpensesList
from app.database.expenses_list_participant import ExpensesListParticipant
from app.exceptions import ValidationError, ForbiddenError, NotFoundError
from app.schemas import parse_body, UpsertUserSchema, CreateUserSchema
from app.audit import log_audit

def get_supabase():
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_KEY')
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_KEY non configurati")
    return create_client(url, key)

BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', 'profile-images')

MAX_HISTORY = 4

def _get_history(u) -> list:
    try:
        return json.loads(u.profile_images_history or '[]')
    except Exception:
        return []

def _path_from_url(url: str) -> str | None:
    """Estrae il path relativo al bucket dall'URL pubblico Supabase."""
    marker = f"/object/public/{BUCKET}/"
    idx = url.find(marker)
    if idx == -1:
        return None
    return url[idx + len(marker):]

def _delete_from_storage(supabase, path: str):
    try:
        supabase.storage.from_(BUCKET).remove([path])
    except Exception:
        pass

def user_to_dict(u):
    return {
        "id": u.id,
        "name": u.name,
        "surname": u.surname,
        "email": u.email,
        "profile_image": u.profile_image,
        "profile_images_history": _get_history(u),
        "paid_list_shown": u.paid_list_shown,
        "theme_preference": u.theme_preference,
        "role": u.role.name if u.role else None,
        "is_guest": bool(u.is_guest),
    }


def user_query():
    return User.query.options(joinedload(User.role))


@api.route('/users', methods=['GET'])
def get_users():
    users = user_query().order_by(User.id).all()
    return jsonify({"users": [user_to_dict(u) for u in users]})


@api.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    u = user_query().filter_by(id=user_id).first_or_404()
    return jsonify(user_to_dict(u))


@api.route('/users/by-email/<string:email>', methods=['GET'])
def get_user_by_email(email):
    from urllib.parse import unquote
    email = unquote(email)
    u = user_query().filter_by(email=email).first_or_404()
    return jsonify(user_to_dict(u))


@api.route('/users/upsert-by-email', methods=['POST'])
def upsert_user_by_email():
    """Ritorna l'utente se esiste, altrimenti lo crea. Usato al login con Google."""
    data = parse_body(UpsertUserSchema)
    email = data['email']

    u = user_query().filter_by(email=email).first()
    if u:
        return jsonify(user_to_dict(u)), 200

    u = User(
        name=data.get('name', ''),
        surname=data.get('surname', '') or '',
        email=email,
        profile_image=data.get('profile_image', ''),
        paid_list_shown=True,
        is_guest=False,
    )
    db.session.add(u)
    db.session.commit()
    u = user_query().filter_by(email=email).first()
    return jsonify(user_to_dict(u)), 201


@api.route('/users/by-email/<string:email>/expenses-lists', methods=['GET'])
def get_user_expenses_lists_by_email(email):
    from urllib.parse import unquote
    email = unquote(email)
    u = user_query().filter_by(email=email).first_or_404()
    participated_ids = (
        db.session.query(ExpensesListParticipant.expenses_list_id)
        .filter_by(user_id=u.id)
    )
    expenses_lists = (
        ExpensesList.query
        .filter(
            (ExpensesList.user_id == u.id) |
            ExpensesList.id.in_(participated_ids)
        )
        .options(joinedload(ExpensesList.list_type))
        .order_by(ExpensesList.id)
        .all()
    )

    all_list_ids = [el.id for el in expenses_lists]

    part_counts = db.session.query(
        ExpensesListParticipant.expenses_list_id,
        func.count(ExpensesListParticipant.user_id)
    ).filter(ExpensesListParticipant.expenses_list_id.in_(all_list_ids)) \
     .group_by(ExpensesListParticipant.expenses_list_id).all()
    parts_by_list = {row[0]: row[1] for row in part_counts}

    from app.database.expense import Expense
    exp_counts = db.session.query(
        Expense.expense_list_id,
        func.count(Expense.id)
    ).filter(Expense.expense_list_id.in_(all_list_ids)) \
     .group_by(Expense.expense_list_id).all()
    exps_by_list = {row[0]: row[1] for row in exp_counts}

    return jsonify({
        "user": user_to_dict(u),
        "expenses_lists": [
            {
                "id": el.id,
                "name": el.name,
                "user_id": el.user_id,
                "paid": el.paid,
                "created_at": el.created_at,
                "list_type": el.list_type.name if el.list_type else "shared",
                "max_participants": el.list_type.max_participants if el.list_type else 8,
                "expenses_count": exps_by_list.get(el.id, 0),
                "participants_count": parts_by_list.get(el.id, 0),
            }
            for el in expenses_lists
        ]
    })


@api.route('/users/<int:user_id>/profile-image', methods=['POST'])
def upload_profile_image(user_id):
    if 'file' not in request.files:
        raise ValidationError("Nessun file ricevuto")

    file = request.files['file']
    if not file.filename:
        raise ValidationError("Nome file mancante")

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
        raise ValidationError("Formato non supportato")

    file_bytes = file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise ValidationError("File troppo grande (max 5MB)")

    path = f"{user_id}/{uuid.uuid4().hex}.{ext}"
    content_type = file.content_type or f"image/{ext}"

    supabase = get_supabase()
    supabase.storage.from_(BUCKET).upload(
        path, file_bytes, {"content-type": content_type, "upsert": "true"}
    )
    public_url = supabase.storage.from_(BUCKET).get_public_url(path)

    u = User.query.get_or_404(user_id)
    history = _get_history(u)

    if u.profile_image and u.profile_image not in history:
        history.append(u.profile_image)

    if public_url not in history:
        history.insert(0, public_url)

    while len(history) > MAX_HISTORY:
        old_url = history.pop()
        old_path = _path_from_url(old_url)
        if old_path:
            _delete_from_storage(supabase, old_path)

    u.profile_image = public_url
    u.profile_images_history = json.dumps(history)
    db.session.commit()

    return jsonify({"url": public_url, "history": history}), 200


@api.route('/users/<int:user_id>/profile-image/select', methods=['PUT'])
def select_profile_image(user_id):
    """Imposta come foto attiva una già presente nello storico."""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        raise ValidationError("URL mancante")

    u = User.query.get_or_404(user_id)
    history = _get_history(u)

    if url not in history:
        raise NotFoundError("Immagine non presente nello storico")

    history.remove(url)
    history.insert(0, url)

    u.profile_image = url
    u.profile_images_history = json.dumps(history)
    db.session.commit()

    return jsonify({"url": url, "history": history}), 200


@api.route('/users', methods=['POST'])
def create_user():
    data = parse_body(CreateUserSchema)
    user = User(
        name=data['name'],
        surname=data.get('surname') or '',
        email=data['email'],
        profile_image=data.get('profile_image'),
        paid_list_shown=data.get('paid_list_shown', True),
        is_guest=data.get('is_guest', False),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "message": "Utente creato"}), 201


@api.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    u = user_query().filter_by(id=user_id).first_or_404()
    data = request.get_json() or {}

    if 'role_id' in data:
        caller_email = data.get('caller_email')
        if caller_email:
            caller = user_query().filter_by(email=caller_email).first()
            if not caller:
                raise ForbiddenError("Caller non trovato")

            if caller.id == u.id:
                raise ForbiddenError("Non puoi modificare il tuo stesso ruolo")

            caller_role_id = caller.role_id
            target_role_id = u.role_id
            new_role_id = int(data['role_id'])

            if caller_role_id == 2:  # admin
                if target_role_id == 1:
                    raise ForbiddenError("Non puoi modificare un superadmin")
                if new_role_id == 1:
                    raise ForbiddenError("Non puoi assegnare il ruolo superadmin")
            elif caller_role_id != 1:
                raise ForbiddenError("Non hai i permessi")

    old_role_id = u.role_id
    if 'name' in data: u.name = data['name']
    if 'surname' in data: u.surname = data['surname']
    if 'email' in data: u.email = data['email']
    if 'profile_image' in data: u.profile_image = data['profile_image']
    if 'paid_list_shown' in data: u.paid_list_shown = data['paid_list_shown']
    if 'theme_preference' in data: u.theme_preference = data['theme_preference']
    if 'role_id' in data: u.role_id = data['role_id']
    db.session.commit()
    if 'role_id' in data and data['role_id'] != old_role_id:
        log_audit("change_role", user_id=user_id, from_role_id=old_role_id, to_role_id=data['role_id'], by=data.get('caller_email', 'unknown'))
    return jsonify({"message": "Utente aggiornato"}), 200


@api.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Utente eliminato"}), 200
