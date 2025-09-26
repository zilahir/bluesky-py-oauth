NAME = bluesky-follower

.PHONY: db-init install add
db-init:
	@echo "Initializing database..."
	@[ "${VIRTUAL_ENV}" ] || (echo "Need to be inside of virtualenv to use alembic!" && exit 1)
	cat schema.sql | docker exec -i bluesky-app-psql-1 psql postgres://postgres:postgres@psql:5432/bluesky
	alembic upgrade head

# Install all deps locally + rebuild inside container
install:
	pnpm install
	docker compose exec frontend pnpm rebuild

# Add a new dep (usage: make add pkg=react-query)
add:
	pnpm add $(pkg)
	docker compose exec frontend pnpm rebuild
