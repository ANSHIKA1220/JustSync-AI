set -eu

alembic upgrade head

if [ "${PROVISION_DEMO_TENANT:-true}" = "true" ]; then
  python -c "from app.database import SessionLocal; from app.seed import provision_demo_tenant; db=SessionLocal(); provision_demo_tenant(db); db.close(); print('Demo tenant provisioned')"
fi

if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
  python -m app.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
