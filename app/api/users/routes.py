from app.api import api
from app.database.user import User

@api.route('/users')
def get_users():
    users = User.query.order_by(User.id).all()
    return {
        "users": [
            {
                "id": u.id,
                "name": u.name,
                "surname": u.surname,
                "email": u.email,
                "profile_image": u.profile_image,
                "paid_list_shown": u.paid_list_shown,
            }
            for u in users
        ]
    }
