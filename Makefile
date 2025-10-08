.PHONY: help build up down restart logs shell health clean

help:
	@echo "INET Dashboard - Docker Commands"
	@echo "================================="
	@echo "make build    - Build Docker image"
	@echo "make up       - Start containers"
	@echo "make down     - Stop containers"
	@echo "make restart  - Restart containers"
	@echo "make logs     - View logs"
	@echo "make shell    - Open shell in container"
	@echo "make health   - Check health status"
	@echo "make clean    - Remove containers and images"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Dashboard starting at http://localhost:5000"
	@echo "Run 'make logs' to view logs"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

shell:
	docker-compose exec inet-dashboard /bin/bash

health:
	@echo "Container Status:"
	@docker ps --filter name=inet-dashboard
	@echo "\nHealth Check:"
	@curl -s http://localhost:5000/health | python -m json.tool || echo "Dashboard not responding"

clean:
	docker-compose down -v
	docker rmi inet-dash_inet-dashboard 2>/dev/null || true

