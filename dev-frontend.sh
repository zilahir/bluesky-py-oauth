#!/bin/bash

echo "🚀 Frontend Development Helper"
echo "=============================="

case "$1" in
"install")
	echo "📦 Installing dependencies and rebuilding container..."
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache frontend
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d frontend
	;;
"rebuild")
	echo "🔨 Rebuilding frontend container..."
	docker-compose stop frontend
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache frontend
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d frontend
	;;
"logs")
	echo "📋 Showing frontend logs..."
	docker-compose logs -f frontend
	;;
"shell")
	echo "🐚 Opening shell in frontend container..."
	docker-compose exec frontend sh
	;;
"clean")
	echo "🧹 Cleaning up volumes and rebuilding..."
	docker-compose stop frontend
	docker volume rm bluesky-py-oauth_frontend_node_modules 2>/dev/null || true
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache frontend
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d frontend
	;;
*)
	echo "Usage: $0 {install|rebuild|logs|shell|clean}"
	echo ""
	echo "Commands:"
	echo "  install  - Install new dependencies and rebuild"
	echo "  rebuild  - Rebuild the container (after changes)"
	echo "  logs     - Show frontend container logs"
	echo "  shell    - Open shell in frontend container"
	echo "  clean    - Clean volumes and rebuild from scratch"
	echo ""
	echo "For normal development:"
	echo "  docker-compose -f docker-compose.yml -f docker-compose.dev.yml up"
	;;
esac
