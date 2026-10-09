# aicell-api

Backend API for the aicell mobile app: a mobile operator's self-service
product (balance, tariffs, packs, support assistant) built on Django and
Django REST framework. The mobile client lives in a separate repository.

## Run locally

```sh
uv sync
cp .env.example .env
uv run python manage.py runserver
```
