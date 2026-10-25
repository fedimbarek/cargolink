# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CargoLink (StackUnity) is a Django 6 + DRF freight marketplace connecting **PMEs** (shippers) with **Transporteurs** (carriers). Code, identifiers, comments and UI are in French. Dependencies are managed with `uv` (Python >= 3.12); database is SQLite (`db.sqlite3`).

## Commands

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
uv run python manage.py makemigrations <app>
uv run python manage.py test                                   # all tests
uv run python manage.py test factures                          # one app
uv run python manage.py test factures.tests.SomeTestCase.test_x  # single test
uv run python manage.py expire_demandes                        # mark past-due open DemandeTransport as expired
```

No linter/formatter is configured.

## Architecture

**Two parallel front-ends per app.** Each app exposes both server-rendered HTML pages and a JSON API, wired separately in `config/urls.py`:
- `<app>/web_urls.py` + `views.py` (or `users/web_views.py`) → HTML templates, session auth, mounted at `/<app>/` (users at `/`).
- `<app>/urls.py` (+ `api_views.py`/`serializers.py` where present) → DRF, mounted at `/api/<app>/`. DRF defaults to JWT auth (simplejwt) and `IsAuthenticated`. Auth endpoints: `/api/auth/register|login|refresh|me/`.

Shared templates live in `templates/` (`base.html`, users pages); app templates in `<app>/templates/<app>/`.

**Business logic lives in `services.py`**, not views. Views/API views call service functions (e.g. `factures.services.creer_facture/emettre/enregistrer_paiement`, `propositions.services.accepter_proposition/comparer`, `meteo.services.mettre_a_jour`). Services raise app-specific exceptions (`ErreurMetier`, `ErreurFacture`, `ErreurMeteo`) that views turn into user-facing errors. Visibility scoping per user is also done in services (`factures_visibles`, `alertes_visibles`, `demandes_du_user`). Keep new logic in services so both HTML and API paths share it.

**Roles and permissions.** Custom user `users.User` (`AUTH_USER_MODEL`) with a `role` (PME / TRANSPORTEUR / ADMIN) and one-to-one profiles `user.pme` / `user.transporteur`. A transporteur must be `verified` by an admin before acting.
- HTML views: `users.decorators.role_required("PME", ...)`.
- API views: `users.permissions.IsPME`, `IsTransporteur` (also checks verified), `IsAdminRole`.

**Domain flow across apps:**
1. `annonces` – PME publishes a `DemandeTransport` (status OPEN → … / EXPIREE). `services.py` geocodes cities and computes routes via external HTTP APIs (`requests`).
2. `propositions` – Transporteurs register `Vehicle`s, see compatible demandes (`demandes_compatibles`), submit a `Proposition`; PME compares (`comparer`, scoring) and accepts one (`accepter_proposition`). Currency conversion via an external rate API.
3. `factures` – A `Facture` is one-to-one with an accepted `Proposition` (PROTECT), with `Paiement`s; status is recomputed from payments (`recalculer_statut`); emitted invoices are locked.
4. `meteo` – `PrevisionMeteo` per demande from an external weather API, risk evaluation, and `AlerteMeteo` synced from forecasts.
5. `reservations`, `evaluations` – API-only apps (no web URLs yet).
