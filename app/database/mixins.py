from sqlalchemy import Column, Boolean, String, TIMESTAMP, func


class DeltaSyncMixin:
    """Colonne condivise per il delta sync local-first.

    - client_id: UUID generato dall'app. Usato per deduplicare le create: una
      create che arriva con un client_id gia' visto (nel suo scope) fa UPDATE
      della riga esistente invece di inserirne una nuova (idempotenza anti
      re-invio). Unicita' per scope garantita da indici DB parziali.
    - updated_at: aggiornato automaticamente a ogni modifica della riga.
      A livello DB un trigger BEFORE UPDATE (vedi migrations/add_checklist_delta_sync.sql)
      forza updated_at = now(), coprendo anche bulk UPDATE e SQL raw. L'onupdate
      ORM qui sotto mantiene l'allineamento lato sessione SQLAlchemy.
    - deleted: soft-delete. Le letture normali escludono deleted=true; il delta
      pull le include cosi' l'app sa cosa rimuovere localmente.

    Riutilizzabile da altre entita' sincronizzabili (es. spese, prezzi).
    """

    client_id = Column(String(36), nullable=True, index=True)
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted = Column(Boolean, nullable=False, server_default='false')
