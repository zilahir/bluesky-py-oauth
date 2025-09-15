NAME = bluesky-follower

.PHONY:
db-init:
	@echo "Initializing database..."
	@[ "${VIRTUAL_ENV}" ] || (echo "Need to be inside of virtualenv to use alembic!" && exit 1)
	cat schema.sql | docker exec -i bluesky-app-psql-1 psql postgres://postgres:postgres@psql:5432/bluesky
	alembic upgrade head

