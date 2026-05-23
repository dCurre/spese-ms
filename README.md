<p align="center">
  <img src="https://spese-dc.web.app/assets/ic_logo.png" alt="Spese logo" width="80"/>
</p>

<h1 align="center">Spese — Backend</h1>

<p align="center">
  REST API per la gestione delle spese condivise e delle liste della spesa.<br/>
  Costruita con <strong>Flask</strong> e deployata su <strong>Render</strong>.
</p>

<p align="center">
  <a href="https://spese-ms.onrender.com/api/">🟢 API Status</a>
</p>

---

## Funzionalità

- 👥 **Utenti** — gestione profili, ruoli gerarchici, upload immagine via Supabase Storage
- 📋 **Liste spese** — CRUD liste condivise con partecipanti e calcolo saldi
- 💸 **Spese** — registrazione spese per categoria e lista
- 🛒 **Checklist** — liste della spesa con items, ordinamento, bulk edit e token di invito
- 🔑 **Ruoli** — sistema gerarchico superadmin / admin / user

## Stack

| Layer | Tecnologia |
|-------|-----------|
| Framework | Flask 3.1 |
| ORM | SQLAlchemy 2 + Flask-SQLAlchemy |
| Database | PostgreSQL (Supabase) |
| Storage | Supabase Storage |
| Deploy | Render |

## Sviluppo locale

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Crea un file `.env` nella root:

```env
DATASOURCE_URL=...
DATASOURCE_PORT=5432
DATASOURCE_DB_NAME=...
DATASOURCE_USERNAME=...
DATASOURCE_PASSWORD=...
SUPABASE_URL=...
SUPABASE_KEY=...
SUPABASE_STORAGE_BUCKET=profile-images
```

Avvia il server:

```bash
python run.py
```

L'API sarà disponibile su `http://localhost:5000`.

## Endpoint principali

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/` | Health check + versione |
| GET/POST | `/api/users` | Lista e creazione utenti |
| GET | `/api/users/by-email/<email>` | Utente per email |
| GET/POST | `/api/expenses-lists` | Liste spese |
| GET/POST | `/api/shopping-lists` | Checklist |
| GET/POST | `/api/shopping-items` | Articoli checklist |

## Struttura

```
app/
├── api/
│   ├── users/
│   ├── expenses/
│   ├── expenses_lists/
│   ├── expenses_list_participants/
│   ├── shopping_lists/
│   ├── shopping_items/
│   ├── expense_types/
│   └── user_roles/
├── database/        # Modelli SQLAlchemy
└── __init__.py      # App factory
```
