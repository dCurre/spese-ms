from app.api import api
from app.database.expenses_list import ExpensesList

@api.route('/expenses-lists', methods=['GET'])
def get_expenses_lists():
    expenses_lists = ExpensesList.query.order_by(ExpensesList.id).all()
    return {
        "users": [
            {
                "id": el.id,
                "name": el.name,
                "owner_id": el.owner_id,
                "paid": el.paid,
                "creation_date": el.creation_date,
            }
            for el in expenses_lists
        ]
    }
