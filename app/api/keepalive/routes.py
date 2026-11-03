from flask import jsonify
from sqlalchemy import func
from app.api import api
from app.database import db
from app.database.heartbeat import Heartbeat


@api.route('/keepalive', methods=['GET', 'HEAD'])
def keepalive():
    # Scrittura reale per tenere attivo Supabase (il free tier mette in pausa
    # i progetti senza attività). Aggiorna la riga singola, creandola se assente.
    # Nessuna autenticazione e nessun dato sensibile esposto.
    row = db.session.get(Heartbeat, 1)
    if row is None:
        row = Heartbeat(id=1, last_ping=func.now())
        db.session.add(row)
    else:
        row.last_ping = func.now()
    db.session.commit()
    return jsonify({"status": "alive"}), 200
