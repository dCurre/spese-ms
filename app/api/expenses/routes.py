from flask import request, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.api import api
from app.database import db
from app.database.expense import Expense
from app.database.expense_type import ExpenseType
from app.database.expenses_list import ExpensesList
from app.database.expenses_list_participant import ExpensesListParticipant
from app.exceptions import ValidationError
from app.schemas import parse_body, CreateExpenseSchema


def parse_date(date_str: str) -> datetime:
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(date_str)


def expense_to_dict(e, include_paid_list_shown=False):
    owner = {
        "id": e.user.id,
        "name": e.user.name,
        "surname": e.user.surname,
        "email": e.user.email,
        "profile_image": e.user.profile_image,
    }
    if include_paid_list_shown:
        owner["paid_list_shown"] = e.user.paid_list_shown
    return {
        "id": e.id,
        "client_id": e.client_id,
        "name": e.name,
        "amount": e.amount,
        "created_at": e.created_at,
        "owner": owner,
        "updated_at": e.updated_at,
        "deleted": e.deleted,
        "modified_by": e.modified_by,
        "expense_list_id": e.expense_list_id,
        "expense_date": e.expense_date,
        "expense_type_id": e.expense_type_id,
        "expense_type": e.expense_type.name if e.expense_type else None,
    }


@api.route('/expenses', methods=['GET'])
def get_expenses():
    expenses = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).filter_by(deleted=False).order_by(Expense.id).all()
    return jsonify({"expenses": [expense_to_dict(e, include_paid_list_shown=True) for e in expenses]})


@api.route('/expenses/<int:expense_id>', methods=['GET'])
def get_expense(expense_id):
    e = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).filter_by(id=expense_id, deleted=False).first_or_404()
    return jsonify(expense_to_dict(e, include_paid_list_shown=True))


@api.route('/expenses/stats', methods=['GET'])
def expenses_stats():
    """Statistiche aggregate delle spese PERSONALI dell'utente (solo quelle dove
    lui è expense_owner_user_id), limitate alle liste a cui ha accesso
    (possedute + condivise come partecipante). Per la dashboard statistiche.

    Query param:
      - user_id (obbligatorio)
      - from, to (opzionali, yyyy-MM-dd): finestra su expense_date. Default: ultimi 12 mesi.
      - granularity (month|week|year, default month): raggruppamento temporale.

    Risposta:
      {
        "currency": "EUR",
        "from": "2026-01-01", "to": "2026-12-31", "granularity": "month",
        "total": "1234.50", "count": 42,
        "previous_total": "980.00",
        "by_period": [{"period": "2026-09", "total": "410.00", "count": 12}, ...],
        "by_type":   [{"expense_type_id": 3, "name": "Spesa", "total": "600.00", "count": 20}, ...]
      }
    Importi come stringa (contratto Numeric->stringa, come il resto delle spese).
    """
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        raise ValidationError("user_id mancante")

    granularity = (request.args.get('granularity') or 'month').lower()
    if granularity not in ('month', 'week', 'year'):
        raise ValidationError("granularity non valida (month|week|year)")

    # Finestra temporale: default ultimi 12 mesi (approssimati a 365 giorni).
    def _parse(d):
        if not d:
            return None
        try:
            return datetime.strptime(d, '%Y-%m-%d')
        except ValueError:
            raise ValidationError("data non valida (formato atteso yyyy-MM-dd)")

    now = datetime.utcnow()
    date_to = _parse(request.args.get('to')) or now
    date_from = _parse(request.args.get('from')) or (date_to - timedelta(days=365))
    if date_from > date_to:
        raise ValidationError("'from' successiva a 'to'")

    # Scoping: liste accessibili (possedute + condivise), come il delta sync.
    owned_ids = db.session.query(ExpensesList.id).filter_by(user_id=user_id)
    shared_ids = db.session.query(ExpensesListParticipant.expenses_list_id).filter_by(user_id=user_id)
    accessible_ids = [row[0] for row in owned_ids.union(shared_ids).all()]

    empty = {
        "currency": "EUR",
        "from": date_from.strftime('%Y-%m-%d'),
        "to": date_to.strftime('%Y-%m-%d'),
        "granularity": granularity,
        "total": "0.00", "count": 0, "previous_total": "0.00",
        "by_period": [], "by_type": [],
    }
    if not accessible_ids:
        return jsonify(empty)

    # Base: SOLO le spese pagate dall'utente, non cancellate, nelle liste accessibili, nel periodo.
    def _base_query():
        return (
            db.session.query(Expense)
            .filter(
                Expense.deleted == False,  # noqa: E712
                Expense.expense_list_id.in_(accessible_ids),
                Expense.expense_owner_user_id == user_id,
            )
        )

    in_window = _base_query().filter(
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    ).subquery()

    # Totale + conteggio del periodo.
    total, count = db.session.query(
        func.coalesce(func.sum(in_window.c.amount), 0),
        func.count(in_window.c.id),
    ).one()

    # Totale del periodo PRECEDENTE di pari durata (per il confronto %).
    span = date_to - date_from
    prev_to = date_from
    prev_from = date_from - span
    prev_total = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        Expense.deleted == False,  # noqa: E712
        Expense.expense_list_id.in_(accessible_ids),
        Expense.expense_owner_user_id == user_id,
        Expense.expense_date >= prev_from,
        Expense.expense_date < prev_to,
    ).scalar()

    # Formato del bucket temporale (Postgres to_char, ordinabile come stringa).
    period_fmt = {'month': 'YYYY-MM', 'week': 'IYYY-"W"IW', 'year': 'YYYY'}[granularity]
    period_col = func.to_char(Expense.expense_date, period_fmt)

    by_period_rows = (
        _base_query()
        .filter(Expense.expense_date >= date_from, Expense.expense_date <= date_to)
        .with_entities(
            period_col.label('period'),
            func.coalesce(func.sum(Expense.amount), 0).label('total'),
            func.count(Expense.id).label('count'),
        )
        .group_by(period_col)
        .order_by(period_col)
        .all()
    )

    by_type_rows = (
        _base_query()
        .filter(Expense.expense_date >= date_from, Expense.expense_date <= date_to)
        .outerjoin(ExpenseType, Expense.expense_type_id == ExpenseType.id)
        .with_entities(
            Expense.expense_type_id.label('expense_type_id'),
            ExpenseType.name.label('name'),
            func.coalesce(func.sum(Expense.amount), 0).label('total'),
            func.count(Expense.id).label('count'),
        )
        .group_by(Expense.expense_type_id, ExpenseType.name)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    def _money(v):
        return format(v or 0, '.2f')

    return jsonify({
        "currency": "EUR",
        "from": date_from.strftime('%Y-%m-%d'),
        "to": date_to.strftime('%Y-%m-%d'),
        "granularity": granularity,
        "total": _money(total),
        "count": int(count or 0),
        "previous_total": _money(prev_total),
        "by_period": [
            {"period": r.period, "total": _money(r.total), "count": int(r.count)}
            for r in by_period_rows
        ],
        "by_type": [
            {
                "expense_type_id": r.expense_type_id,
                "name": r.name,
                "total": _money(r.total),
                "count": int(r.count),
            }
            for r in by_type_rows
        ],
    })


@api.route('/expenses', methods=['POST'])
def create_expense():
    data = parse_body(CreateExpenseSchema)
    client_id = data.get('client_id')

    # Create idempotente: client_id gia' visto nella stessa lista -> update.
    existing = None
    if client_id:
        existing = Expense.query.filter_by(
            expense_list_id=data['expense_list_id'], client_id=client_id
        ).first()
    if existing:
        existing.name = data['name']
        existing.amount = data['amount']
        existing.expense_owner_user_id = data['expense_owner_user_id']
        existing.expense_date = parse_date(data['expense_date'])
        existing.expense_type_id = data.get('expense_type_id')
        existing.deleted = False
        db.session.commit()
        return jsonify({"id": existing.id, "client_id": existing.client_id, "message": "Spesa aggiornata"}), 200

    expense = Expense(
        name=data['name'],
        amount=data['amount'],
        expense_owner_user_id=data['expense_owner_user_id'],
        expense_list_id=data['expense_list_id'],
        expense_date=parse_date(data['expense_date']),
        expense_type_id=data.get('expense_type_id'),
        client_id=client_id,
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify({"id": expense.id, "client_id": expense.client_id, "message": "Spesa creata"}), 201


@api.route('/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    e = Expense.query.filter_by(id=expense_id, deleted=False).first_or_404()
    data = request.get_json() or {}
    if 'name' in data: e.name = data['name']
    if 'amount' in data: e.amount = data['amount']
    if 'expense_date' in data: e.expense_date = parse_date(data['expense_date'])
    if 'expense_owner_user_id' in data: e.expense_owner_user_id = data['expense_owner_user_id']
    if 'modified_by' in data: e.modified_by = data['modified_by']
    if 'expense_type_id' in data: e.expense_type_id = data['expense_type_id']
    # updated_at e' gestito automaticamente dal trigger DB set_updated_at().
    db.session.commit()
    return jsonify({"message": "Spesa aggiornata"}), 200


@api.route('/expenses/by-list/<int:list_id>', methods=['GET'])
def get_expenses_by_list(list_id):
    expenses = Expense.query.options(joinedload(Expense.user), joinedload(Expense.expense_type)).filter_by(expense_list_id=list_id, deleted=False).order_by(Expense.id).all()
    return jsonify({"expenses": [expense_to_dict(e) for e in expenses]})


@api.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    # Soft-delete: marca deleted=true (updated_at aggiornato dal trigger DB).
    expense = Expense.query.filter_by(id=expense_id, deleted=False).first_or_404()
    expense.deleted = True
    db.session.commit()
    return jsonify({"message": "Spesa eliminata"}), 200


@api.route('/expenses/bulk-delete', methods=['POST'])
def bulk_delete_expenses():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids:
        raise ValidationError("ids mancante o vuoto")
    # Soft-delete di piu' spese (nessuna rimozione fisica).
    deleted = Expense.query.filter(Expense.id.in_(ids), Expense.deleted == False) \
        .update({'deleted': True}, synchronize_session=False)
    db.session.commit()
    return jsonify({"deleted": deleted, "message": f"{deleted} spese eliminate"}), 200
