.PHONY: up down api frontend lnd help

help:
	@echo "Kuberbolt Development Commands:"
	@echo "  make up       - Start the entire local stack (LND, API, Frontend)"
	@echo "  make down     - Stop all running services"
	@echo "  make api      - Start only the FastAPI backend"
	@echo "  make frontend - Start only the React frontend"
	@echo "  make lnd      - Start only the Lightning nodes via Docker"

up:
	@echo "🚀 Starting Lightning Infrastructure..."
	@cd lightning-infra && docker compose -f docker-compose.lnd.yml up -d
	@echo "✅ LND is running in the background."
	@echo "👉 Now, please open two new terminal windows and run:"
	@echo "   Terminal 1: make api"
	@echo "   Terminal 2: make frontend"

down:
	@echo "🛑 Stopping Lightning Infrastructure..."
	@cd lightning-infra && docker compose -f docker-compose.lnd.yml down

api:
	uvicorn api.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

lnd:
	cd lightning-infra && docker compose -f docker-compose.lnd.yml up -d
