---
name: db-change
description: >-
  Applica modifiche al database Postgres/Supabase del progetto spese-ms:
  DDL (CREATE/ALTER/DROP TABLE, indici, colonne), DML (INSERT/UPDATE/DELETE,
  seed), e genera il codice applicativo collegato (model SQLAlchemy, route
  CRUD, schema marshmallow). Usala quando l'utente chiede di creare/modificare
  tabelle o colonne, aggiungere una nuova entita', fare seed/migrazioni dati,
  o "aggiungere/cambiare qualcosa sul DB". Esegue l'SQL direttamente sul DB
  tramite scripts/run_sql.py usando le credenziali del .env.
---

# Modifiche al database (spese-ms)

Skill per apportare modifiche al DB Postgres/Supabase **ed eseguirle direttamente**,
oltre a generare il codice applicativo collegato seguendo le convenzioni del progetto.

## Convenzioni del progetto (da rispettare SEMPRE)

- **Schema DB:** tutte le tabelle stanno nello schema `spese` (es. `spese.expenses`).
  Nei model SQLAlchemy: `__table_args__ = {'schema': 'spese'}`.
- **ORM:** Flask-SQLAlchemy. L'istanza condivisa e' `from app.database import db`.
- **Model:** un file per entita' in `app/database/<entity>.py`, classe `db.Model`.
- **Route:** `app/api/<entity>/routes.py` con un blueprint-import. Le route usano
  il decoratore `@api.route(...)` dove `from app.api import api`. Il prefisso URL
  globale e' `/api` (aggiunto in `app/__init__.py`), quindi dentro le route si usa
  `/<risorsa>` (es. `/expense-types`). URL in kebab-case.
- **Registrazione:** ogni nuovo model va importato in `app/__init__.py` (dentro
  `create_app`, blocco `with app.app_context()` prima di `db.create_all()`), e ogni
  nuovo file route va aggiunto in `app/api/__init__.py`.
- **Migrazioni:** file `.sql` in `migrations/`. NOTA: `migrations/` e' in `.gitignore`,
  quindi i file SQL restano locali (storico), NON vengono committati. Devono essere
  **idempotenti**: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`,
  `INSERT ... ON CONFLICT (id) DO NOTHING`.
- **Errori/validazione:** eccezioni in `app/exceptions.py` (es. `ForbiddenError`,
  `AppError`); validazione input con marshmallow in `app/schemas.py`.
- **ID:** chiavi primarie `BigInteger`. Per tabelle di lookup con ID fissi (come
  `expense_types`) gli ID sono espliciti nel seed.

## Esecuzione SQL sul DB — `scripts/run_sql.py`

Lo script si connette al DB usando le credenziali `DATASOURCE_*` del `.env`
(le stesse di `config.py`). **Non incorporare mai segreti nei file**: lo script
li legge a runtime. Esegue tutto in **una transazione** (rollback automatico su errore).

Eseguire sempre dalla root del progetto con l'interprete del venv:

```bash
# Elenca le tabelle dello schema spese
.venv/Scripts/python.exe .claude/skills/db-change/scripts/run_sql.py --list-tables

# Ispeziona le colonne di una tabella (PRIMA di un ALTER, per non duplicare)
.venv/Scripts/python.exe .claude/skills/db-change/scripts/run_sql.py --check-table spese.expenses

# Esegue un file di migrazione (DDL/DML)
.venv/Scripts/python.exe .claude/skills/db-change/scripts/run_sql.py --file migrations/add_x.sql

# SELECT di verifica (stampa le righe)
.venv/Scripts/python.exe .claude/skills/db-change/scripts/run_sql.py --sql "SELECT * FROM spese.expense_types" --query
```

Se psycopg2 non e' presente nel venv, installare i deps:
`.venv/Scripts/python.exe -m pip install psycopg2-binary python-dotenv SQLAlchemy`

## Workflow

Seguire questi passi per ogni modifica al DB.

### 1. Capire lo stato attuale
Prima di scrivere SQL, ispeziona il DB per non fare modifiche duplicate o errate:
- `--list-tables` per vedere cosa esiste;
- `--check-table spese.<tabella>` per vedere le colonne attuali.

### 2. Scrivere la migrazione
Crea un file `migrations/<descrizione>.sql` idempotente. Vedi `references/examples.md`
per esempi completi (nuova tabella + seed, aggiunta colonna, indice).

### 3. Mostrare l'SQL ed eseguire
- **Mostra sempre l'SQL all'utente** prima di eseguirlo.
- **Operazioni distruttive** (`DROP TABLE`, `DROP COLUMN`, `DELETE` senza WHERE,
  `TRUNCATE`, `ALTER` che cambia tipo con perdita dati): **chiedi conferma esplicita
  all'utente prima di eseguire**. Per operazioni additive/idempotenti (CREATE IF NOT
  EXISTS, ADD COLUMN IF NOT EXISTS, INSERT ... ON CONFLICT) procedi pure.
- Esegui con `run_sql.py --file migrations/...`.
- **Verifica** l'esito con un `--check-table` o `--sql "SELECT ..." --query`.

### 4. Generare il codice applicativo
Se la modifica introduce o cambia un'entita' esposta via API, genera/aggiorna
(vedi `references/examples.md` per i template completi):
1. **Model** `app/database/<entity>.py`.
2. **Registrazione model** in `app/__init__.py`.
3. **Route CRUD** `app/api/<entity>/routes.py` (GET lista, GET singolo, POST, PUT, DELETE).
4. **Registrazione route** in `app/api/__init__.py`.
5. **Schema marshmallow** in `app/schemas.py` se serve validazione input.

### 5. Riepilogo
Elenca all'utente: SQL eseguito, file creati/modificati, esito verifica.
Non pushare: committare/pushare solo su richiesta esplicita dell'utente.

## Riferimenti
- `references/examples.md` — template SQL e codice (model, route, schema) coerenti
  con le convenzioni del progetto.
