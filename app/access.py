"""Chi può fare cosa. L'identità viene SOLO dal token (vedi app.auth), mai da id o email inviati
dal client. Regole:
- liste (spese e checklist): le usano proprietario e partecipanti; solo il proprietario le elimina,
  ne cambia il tipo o le trasferisce. Un partecipante che "elimina" la lista la abbandona;
- acquisti e statistiche: solo i propri;
- utenti, ruoli e cataloghi: solo admin.
"""
from flask import g

from app.database import db
from app.database.expenses_list import ExpensesList
from app.database.expenses_list_participant import ExpensesListParticipant
from app.database.shopping_list import ShoppingList, ShoppingCategory, ShoppingListParticipant
from app.database.user import User
from app.exceptions import ForbiddenError, ValidationError

# Per NOME: gli id dei ruoli nel database non riflettono la gerarchia.
SUPERADMIN = 'superadmin'
ADMIN_ROLES = {'admin', SUPERADMIN}


def current_user():
    if 'user' not in g:
        g.user = User.query.filter_by(email=g.auth_email, is_guest=False).first()
    if g.user is None:
        raise ForbiddenError("Utente non registrato")
    return g.user


def role_name(user):
    return user.role.name if user and user.role else None


def is_admin():
    return role_name(current_user()) in ADMIN_ROLES


def require_admin():
    if not is_admin():
        raise ForbiddenError("Operazione riservata agli amministratori")


def require_self(user_id):
    if user_id != current_user().id:
        raise ForbiddenError("Puoi accedere solo ai tuoi dati")


def require_self_or_admin(user_id):
    if user_id != current_user().id and not is_admin():
        raise ForbiddenError("Puoi accedere solo ai tuoi dati")


# --- Liste spese -------------------------------------------------------------

def expense_list_ids():
    """Id delle liste spese dell'utente (possedute o condivise), incluse le cancellate."""
    me = current_user().id
    owned = db.session.query(ExpensesList.id).filter_by(user_id=me)
    shared = db.session.query(ExpensesListParticipant.expenses_list_id).filter_by(user_id=me)
    return {row[0] for row in owned.union(shared).all()}


def is_expense_list_member(list_id, user_id):
    el = db.session.get(ExpensesList, list_id) if list_id is not None else None
    if el is None:
        return False
    return el.user_id == user_id or ExpensesListParticipant.query.filter_by(
        expenses_list_id=list_id, user_id=user_id).first() is not None


def can_access_expense_list(list_id):
    return is_expense_list_member(list_id, current_user().id)


def require_expense_list(list_id):
    if not can_access_expense_list(list_id):
        raise ForbiddenError("Non hai accesso a questa lista")


def require_expense_owner(list_id, user_id):
    """Una spesa può essere intestata solo a chi fa parte della lista."""
    if not is_expense_list_member(list_id, user_id):
        raise ValidationError("L'intestatario della spesa non partecipa alla lista")


# --- Checklist ---------------------------------------------------------------

def shopping_list_ids():
    me = current_user().id
    owned = db.session.query(ShoppingList.id).filter_by(owner_id=me)
    shared = db.session.query(ShoppingListParticipant.shopping_list_id).filter_by(user_id=me)
    return {row[0] for row in owned.union(shared).all()}


def can_access_shopping_list(list_id):
    sl = db.session.get(ShoppingList, list_id) if list_id is not None else None
    if sl is None:
        return False
    me = current_user().id
    return sl.owner_id == me or ShoppingListParticipant.query.filter_by(
        shopping_list_id=list_id, user_id=me).first() is not None


def require_shopping_list(list_id):
    if not can_access_shopping_list(list_id):
        raise ForbiddenError("Non hai accesso a questa lista")


def category_in_list(category_id, list_id):
    """True se la categoria è assente (None) o appartiene proprio a quella lista."""
    if category_id is None:
        return True
    cat = db.session.get(ShoppingCategory, category_id)
    return cat is not None and cat.shopping_list_id == list_id


def require_category_in_list(category_id, list_id):
    if not category_in_list(category_id, list_id):
        raise ValidationError("La categoria non appartiene a questa lista")
