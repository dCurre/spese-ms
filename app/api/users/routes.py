import os
import uuid
import json
from flask import g, request, jsonify
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
from app.access import (
    ADMIN_ROLES, SUPERADMIN, current_user, is_admin, role_name,
    require_admin, require_self, require_self_or_admin,
)

def get_supabase():
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_KEY')
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_KEY non configurati")
    return create_client(url, key)

BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', 'profile-images')

MAX_HISTORY = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _image_type(data: bytes):
    """(estensione, content-type) ricavati dai primi byte; None se non è un'immagine ammessa."""
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpg', 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png', 'image/png'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return 'gif', 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp', 'image/webp'
    return None

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
        "language_preference": u.language_preference,
        "app_theme_preference": u.app_theme_preference,
        "app_language_preference": u.app_language_preference,
        "role": u.role.name if u.role else None,
        "is_guest": bool(u.is_guest),
    }


def user_query():
    return User.query.options(joinedload(User.role))


@api.route('/users', methods=['GET'])
def get_users():
    require_admin()
    users = user_query().order_by(User.id).all()
    return jsonify({"users": [user_to_dict(u) for u in users]})


@api.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    require_self_or_admin(user_id)
    u = user_query().filter_by(id=user_id).first_or_404()
    return jsonify(user_to_dict(u))


@api.route('/users/by-email/<string:email>', methods=['GET'])
def get_user_by_email(email):
    from urllib.parse import unquote
    email = unquote(email)
    if email != g.auth_email:
        require_admin()
    u = user_query().filter_by(email=email).first_or_404()
    return jsonify(user_to_dict(u))


@api.route('/users/upsert-by-email', methods=['POST'])
def upsert_user_by_email():
    """Ritorna l'utente se esiste, altrimenti lo crea. Usato al login con Google."""
    data = parse_body(UpsertUserSchema)
    email = g.auth_email  # quella del token: l'email nel body non conta

    u = user_query().filter_by(email=email, is_guest=False).first()
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
    u = user_query().filter_by(email=email, is_guest=False).first()
    return jsonify(user_to_dict(u)), 201


@api.route('/users/by-email/<string:email>/expenses-lists', methods=['GET'])
def get_user_expenses_lists_by_email(email):
    from urllib.parse import unquote
    email = unquote(email)
    if email != g.auth_email:
        require_admin()
    u = user_query().filter_by(email=email).first_or_404()
    participated_ids = (
        db.session.query(ExpensesListParticipant.expenses_list_id)
        .filter_by(user_id=u.id)
    )
    expenses_lists = (
        ExpensesList.query
        .filter(
            (ExpensesList.user_id == u.id) |
            ExpensesList.id.in_(participated_ids),
            ExpensesList.deleted == False,  # noqa: E712
        )
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
                "list_type": el.list_type,
                "expenses_count": exps_by_list.get(el.id, 0),
                "participants_count": parts_by_list.get(el.id, 0),
            }
            for el in expenses_lists
        ]
    })


@api.route('/users/<int:user_id>/profile-image', methods=['POST'])
def upload_profile_image(user_id):
    require_self(user_id)
    if 'file' not in request.files:
        raise ValidationError("Nessun file ricevuto")

    # Un byte oltre il limite basta a rifiutare, senza leggere il resto.
    file_bytes = request.files['file'].read(MAX_IMAGE_BYTES + 1)
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise ValidationError("File troppo grande (max 5MB)")
    image = _image_type(file_bytes)
    if image is None:
        raise ValidationError("Formato non supportato")
    ext, content_type = image

    u = User.query.get_or_404(user_id)
    path = f"{user_id}/{uuid.uuid4().hex}.{ext}"

    supabase = get_supabase()
    supabase.storage.from_(BUCKET).upload(
        path, file_bytes, {"content-type": content_type, "upsert": "true"}
    )
    public_url = supabase.storage.from_(BUCKET).get_public_url(path)

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
    require_self(user_id)
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
    # Un utente normale crea solo ospiti (senza email: non devono poter "diventare" un account).
    is_guest = data['is_guest'] or not is_admin()
    if not is_guest and not data['email']:
        raise ValidationError("Email obbligatoria")
    user = User(
        name=data['name'],
        surname=data.get('surname') or '',
        email=None if is_guest else data['email'],
        profile_image=data.get('profile_image'),
        paid_list_shown=data.get('paid_list_shown', True),
        is_guest=is_guest,
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "message": "Utente creato"}), 201


@api.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    me = current_user()
    require_self_or_admin(user_id)
    u = user_query().filter_by(id=user_id).first_or_404()
    data = request.get_json() or {}

    if me.id != u.id and set(data) - {'role_id', 'caller_email'}:
        raise ForbiddenError("Di un altro utente puoi cambiare solo il ruolo")
    if 'email' in data and data['email'] != u.email:
        raise ForbiddenError("L'email non è modificabile")

    if 'role_id' in data and data['role_id'] != u.role_id:
        require_admin()
        if me.id == u.id:
            raise ForbiddenError("Non puoi modificare il tuo stesso ruolo")
        new_role = db.session.get(UserRole, data['role_id'])
        if new_role is None:
            raise ValidationError("Ruolo inesistente")
        if role_name(me) != SUPERADMIN and SUPERADMIN in (role_name(u), new_role.name):
            raise ForbiddenError("Solo un superadmin può gestire il ruolo superadmin")

    old_role_id = u.role_id
    if 'name' in data: u.name = data['name']
    if 'surname' in data: u.surname = data['surname']
    if 'profile_image' in data: u.profile_image = data['profile_image']
    if 'paid_list_shown' in data: u.paid_list_shown = data['paid_list_shown']
    if 'theme_preference' in data: u.theme_preference = data['theme_preference']
    if 'language_preference' in data:
        lang = data['language_preference']
        if lang not in ('it', 'en'):
            raise ValidationError("Lingua non supportata (valori ammessi: 'it', 'en')")
        u.language_preference = lang
    if 'app_theme_preference' in data: u.app_theme_preference = data['app_theme_preference']
    if 'app_language_preference' in data:
        app_lang = data['app_language_preference']
        if app_lang not in ('it', 'en'):
            raise ValidationError("Lingua non supportata (valori ammessi: 'it', 'en')")
        u.app_language_preference = app_lang
    if 'role_id' in data: u.role_id = data['role_id']
    db.session.commit()
    if 'role_id' in data and data['role_id'] != old_role_id:
        log_audit("change_role", user_id=user_id, from_role_id=old_role_id, to_role_id=data['role_id'], by=me.id)
    return jsonify({"message": "Utente aggiornato"}), 200


@api.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user().id:
        raise ForbiddenError("Non puoi eliminare il tuo account da qui")
    if role_name(user) in ADMIN_ROLES and role_name(current_user()) != SUPERADMIN:
        raise ForbiddenError("Solo un superadmin può eliminare un amministratore")
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Utente eliminato"}), 200
