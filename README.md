# EventHub – Event Discovery & Real-Time Ticket Booking Platform

A full-stack website where organisers publish events and attendees browse, pick exact seats on a **live seat map**, hold them for **5 minutes**, pay (mock gateway) and receive a **QR e-ticket**. A seat can never be sold twice – even when many people click at the same instant.

Built with **FastAPI · PostgreSQL · React** for the Ascendion Engineering Technology project assignment.

## 1. Problem statement
Basic ticketing sites fail in three ways: (1) two users pay for the same seat because "check availability" and "book" are separate, unprotected steps; (2) seat maps go stale, so people pick seats that are already gone; (3) organisers can't see sales and entry staff can't verify a ticket is genuine and unused.

## 2. Objectives
- Event discovery, seat selection and ticket booking in a responsive website.
- **No double booking**, proven by an automated concurrency test on real PostgreSQL.
- Live seat availability without page refresh (WebSockets).
- Separate, server-enforced experiences for Attendee, Organiser and Admin.
- QR e-ticket that entry staff can validate once.
- Runs locally without Docker; optional Docker Compose + GitHub Actions CI.

## 3. Technology stack
| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2, Pydantic v2, Alembic |
| Database | PostgreSQL (row locking, partial unique indexes) |
| Auth | JWT (python-jose), bcrypt password hashing |
| Real-time | WebSockets (FastAPI) |
| Tickets | `qrcode` + Pillow |
| Frontend | React 18, Vite, React Router, Axios, Context API, CSS3, Lucide icons |
| Tests | Pytest (unit + PostgreSQL integration) |
| DevOps | Git, Docker, Docker Compose, GitHub Actions |

## 4. Features
- **Auth & roles:** register/login, JWT, bcrypt, ATTENDEE / ORGANISER / ADMIN; roles enforced on the server for every API (the role is read from the database, so a disabled/demoted user loses access immediately).
- **Events:** search by name, filter by city/category/date, pagination, sort, images (generated posters + upload), approval workflow.
- **Venues, sections, rows, seats, prices**; seat map API with live status `AVAILABLE | HELD | BOOKED`.
- **Timed holds (5 min)** with countdown; automatic release by a background job; lazy release so an expired hold never blocks anyone.
- **Live updates:** every hold / release / booking is pushed to all viewers of that event.
- **Booking:** idempotent checkout (`Idempotency-Key`), mock payment (idempotent), history, cancellation (with refund + seats freed, up to 24 h before the event).
- **E-ticket:** unguessable ticket code (192 bits), QR PNG, downloadable ticket image, "My Tickets".
- **Organiser dashboard:** events, tickets sold, revenue, per-event availability, booking details. Create / edit / cancel / delete events.
- **Stretch goals (done):** Admin panel (stats, user management, event approval) and entry **check-in** page (a second scan is rejected).

## 5. Folder structure
```
EventHub/
├── backend/
│   ├── app/
│   │   ├── main.py            # app, CORS, error handlers, expiry background task
│   │   ├── config.py          # settings from environment variables
│   │   ├── database.py        # engine / session
│   │   ├── models/            # SQLAlchemy tables
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── routes/            # REST endpoints (one file per tag)
│   │   ├── services/          # business logic: seat_service, booking_service ...
│   │   ├── middleware/        # auth + role dependencies
│   │   ├── websocket/         # connection manager + /ws route
│   │   ├── utils/             # security, QR/ticket images, mock gateway, posters
│   │   └── seed.py            # demo data
│   ├── alembic/               # migrations
│   ├── tests/unit  tests/integration
│   ├── requirements.txt  .env.example  Dockerfile
├── frontend/  (src/components, pages, layouts, context, services, hooks, styles)
├── scripts/                   # Windows helper scripts / SQL
├── docker-compose.yml  .github/workflows/ci.yml  README.md
```

## 6. Architecture
```mermaid
flowchart LR
  B[Browser - React + Vite] -- REST /api --> API[FastAPI]
  B -- WebSocket /ws/events/id --> WS[Connection manager]
  API --> SVC[Services: holds, bookings, payments, tickets]
  SVC -- SQL transactions + SELECT FOR UPDATE --> PG[(PostgreSQL)]
  SVC -- notify after commit --> WS
  SW[Background sweeper every 5s] -- release expired holds --> PG
  SW --> WS
  WS -- seat_update --> B
```

### How double booking is prevented (the key design decision)
1. Every request that changes seat state runs `SELECT … FROM seats WHERE id IN (…) ORDER BY id FOR UPDATE`. PostgreSQL makes a competing request **wait** on that row.
2. After the lock is obtained we re-read the committed state (READ COMMITTED), see `HELD`/`BOOKED`, and return **HTTP 409**.
3. Rows are locked in **ascending id order**, and booking → seats → holds is the same order everywhere, so there are no deadlocks.
4. **Safety net in the database itself** (partial unique indexes): one `ACTIVE` hold per seat; one `CONFIRMED` booking item per seat; one successful payment per booking. Even a bug in Python could not double-sell a seat.
5. **Idempotency:** `(user_id, idempotency_key)` is unique on bookings and payments; repeated or racing requests return the original result and never charge twice.
6. **Expiry:** a hold is valid only while `expires_at > now`; payment re-verifies owner, status and expiry *inside the locked transaction*. A background task frees expired seats and broadcasts it.

## 7. Database ER diagram
```mermaid
erDiagram
  USERS ||--o{ EVENTS : organises
  VENUES ||--o{ EVENTS : hosts
  EVENTS ||--o{ SEATS : has
  USERS ||--o{ HOLDS : makes
  SEATS ||--o{ HOLDS : "is held by"
  USERS ||--o{ BOOKINGS : places
  EVENTS ||--o{ BOOKINGS : "booked for"
  BOOKINGS ||--|{ BOOKING_ITEMS : contains
  SEATS ||--o{ BOOKING_ITEMS : "is sold as"
  HOLDS ||--o| BOOKING_ITEMS : "converted into"
  BOOKING_ITEMS ||--o| TICKETS : issues
  BOOKINGS ||--o{ PAYMENTS : "paid by"
  USERS { int id PK string email UK string role bool is_active }
  EVENTS { int id PK int organiser_id FK int venue_id FK string status datetime starts_at }
  SEATS { int id PK int event_id FK string section string row_label int number numeric price string status }
  HOLDS { int id PK int user_id FK int seat_id FK string status datetime expires_at }
  BOOKINGS { int id PK string reference UK string idempotency_key string status numeric total_amount }
  BOOKING_ITEMS { int id PK int booking_id FK int seat_id FK int hold_id UK string status }
  TICKETS { int id PK int booking_item_id UK string code UK bool checked_in }
  PAYMENTS { int id PK int booking_id FK string idempotency_key string status string card_last4 }
```

## 8. API endpoints (full interactive docs: http://localhost:8000/docs)
| Tag | Endpoints |
|---|---|
| Authentication | `POST /api/auth/register` · `POST /api/auth/login` · `GET /api/auth/me` · `POST /api/auth/logout` |
| Users | `GET/PATCH /api/users/me` |
| Events | `GET /api/events` (q, city, category, date_from, date_to, sort, page, page_size) · `GET /api/events/filters` · `GET/PUT/DELETE /api/events/{id}` · `POST /api/events` · `POST /api/events/upload-image` |
| Venues | `GET/POST /api/venues` · `GET /api/venues/{id}` |
| Seats | `GET /api/events/{id}/seats` |
| Holds | `POST /api/holds` · `GET /api/holds/mine` · `DELETE /api/holds/{id}` |
| Bookings | `POST /api/bookings` (Idempotency-Key) · `GET /api/bookings` · `GET /api/bookings/{id}` · `POST /api/bookings/{id}/cancel` |
| Payments | `POST /api/payments` (Idempotency-Key) · `GET /api/payments/{id}` |
| Tickets | `GET /api/tickets` · `GET /api/tickets/{id}` · `/qr` · `/download` · `POST /api/tickets/check-in` |
| Organiser Dashboard | `GET /api/organiser/summary` · `/events` · `/events/stats` · `/events/{id}/bookings` |
| Admin | `GET /api/admin/stats` · `/users` · `PATCH /users/{id}` · `/events` · `POST /events/{id}/approve｜reject` |
| WebSocket | `ws://localhost:8000/ws/events/{event_id}` → `{"type":"seat_update","seats":[{"seat_id":1,"status":"HELD"}]}` |

## 9. Run locally on Windows (no Docker needed)
**Prerequisites:** Python 3.12, Node.js 20+ (includes npm), PostgreSQL 16, Git.

### 9.1 PostgreSQL setup
1. Download the installer from https://www.postgresql.org/download/windows/ and install it (keep port **5432**; remember the `postgres` password you choose).
2. Open **SQL Shell (psql)** (Start menu), log in as `postgres`, and run (choose your own password):
```sql
CREATE USER eventhub WITH PASSWORD 'your_password_here';
CREATE DATABASE eventhub OWNER eventhub;
CREATE DATABASE eventhub_test OWNER eventhub;
```
(The same statements are in `scripts/create-databases.sql`.)

### 9.2 Terminal 1 – Backend
```powershell
cd EventHub\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
copy .env.example .env                # then edit .env: DATABASE_URL password + JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"   # paste this as JWT_SECRET
alembic upgrade head                  # creates all tables
python -m app.seed                    # demo users, venues, 13 events with seats
uvicorn app.main:app --reload --port 8000
```
### 9.3 Terminal 2 – Frontend
```powershell
cd EventHub\frontend
npm install
npm run dev
```
| What | URL |
|---|---|
| Website | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Database | PostgreSQL on localhost:5432 |

The Vite dev server proxies `/api`, `/static` and `/ws` to port 8000, so there are no CORS problems.

## 10. Environment configuration (`backend/.env`)
| Variable | Meaning |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://user:password@localhost:5432/eventhub` |
| `JWT_SECRET` | long random string (required, ≥16 chars) |
| `ACCESS_TOKEN_MINUTES` | JWT lifetime (default 60) |
| `HOLD_SECONDS` | seat hold length (default 300) |
| `EXPIRY_SWEEP_SECONDS` | how often expired holds are released (default 5) |
| `REQUIRE_EVENT_APPROVAL` | `true` → new organiser events wait for admin approval |

## 11. Tests
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest tests/unit                 # fast, no database
pytest tests/integration          # real PostgreSQL (database eventhub_test)
pytest                            # everything
```
Integration tests use `TEST_DATABASE_URL` (default `…/eventhub_test` with the user from step 9.1 – set it if your password differs):
```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg2://eventhub:your_password_here@localhost:5432/eventhub_test"
$env:JWT_SECRET="any-long-test-secret-0123456789"
```
**The test database is wiped on every run**, so the suite refuses to start unless its name ends in `_test`.

What is covered (71 tests): registration/login, JWT (garbage, forged, expired), role permissions, event CRUD + filters + pagination, seat map, holds, hold expiry (background job **and** lazy path), expired-hold payment rejected, checkout/payment idempotency, declined card + retry, cancellation, QR/ticket privacy, check-in, WebSocket pushes, DB constraints, and **concurrency** (`tests/integration/test_concurrency.py`):
- two users race for the same seat → exactly one `201`, one `409`, one confirmed booking in PostgreSQL;
- same race through the whole hold→checkout→pay flow; 12 users vs. 1 seat; overlapping multi-seat requests (no deadlock); three simultaneous payments for one booking; four identical checkout requests.

The tests start the real app with Uvicorn and use one HTTP connection per thread released by a barrier – real parallel requests, no mocks, no SQLite.

## 12. Docker (optional deployment)
```powershell
docker compose up --build
```
Opens the site on http://localhost:5173 (nginx → React, proxying `/api` and `/ws` to the backend), API on :8000, PostgreSQL with a persistent volume. Migrations and demo seeding run automatically. Default passwords in `docker-compose.yml` are **demo-only** – copy `.env.example` to `.env` and change them for anything real.

## 13. Demo credentials
| Role | Email | Password |
|---|---|---|
| Admin | admin@eventhub.dev | Admin@123 |
| Organiser | organiser@eventhub.dev | Organiser@123 |
| Organiser 2 | organiser2@eventhub.dev | Organiser@123 |
| Attendee | attendee@eventhub.dev | Attendee@123 |
| Attendee 2 | attendee2@eventhub.dev | Attendee@123 |

Payment test cards: `4242 4242 4242 4242` succeeds, `4000 0000 0000 0002` is declined, `4000 0000 0000 9995` = insufficient funds.

**Two-browser demo:** log in as `attendee@…` in one window and `attendee2@…` in a private window, open the same event's seat page, and click a seat in one – it turns orange in the other instantly.

## 14. Screenshots
Add your screenshots to `docs/screenshots/` and reference them here (landing, seat map, checkout, QR ticket, organiser dashboard).

## 15. Known limitations & future improvements
- WebSocket fan-out is in-process: with several Uvicorn workers use Redis pub/sub (or run one worker).
- JWT is kept in `localStorage` (simple; vulnerable if an XSS bug exists). Production: httpOnly cookies + refresh tokens + CSRF protection.
- Mock payments only; plug in Stripe/Razorpay with webhooks.
- Camera QR scanning on the check-in page (currently type/paste the code).
- Email/SMS confirmations, rate limiting, audit logs (MongoDB optional), React Testing Library tests, load testing.
- Hold countdown uses the browser clock; the server is always the authority on expiry.
