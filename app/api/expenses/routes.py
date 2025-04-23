from app.api import api
from app.database.expense import Expense


@api.route('/expenses')
def get_expenses():
    expenses = Expense.query.order_by(Expense.id).all()
    return {
        "expenses": [
            {
                "id": e.id,
                "name": e.name,
                "amount": e.amount,
                "creation_date": e.creation_date,
                "owner": {
                    "id": e.user.id,
                    "name": e.user.name,
                    "surname": e.user.surname,
                    "email": e.user.email,
                    "profile_image": e.user.profile_image,
                    "paid_list_shown": e.user.paid_list_shown,
                },
                "update_date": e.update_date,
                "modified_by": e.modified_by,
                "expense_list_id": e.expense_list_id,
                "expense_date": e.expense_date
            }
            for e in expenses
        ]
    }
