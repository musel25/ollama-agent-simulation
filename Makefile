.PHONY: up down demo contracts logs

up:
	@mkdir -p contracts/deployments
	docker compose up --build -d
	@echo "Services starting... UI at http://localhost:8501"

down:
	docker compose down -v

logs:
	docker compose logs -f

contracts:
	@source .env && cd contracts && forge script script/Deploy.s.sol \
		--rpc-url http://localhost:8545 \
		--broadcast \
		--private-key $$DEPLOYER_PRIVATE_KEY

demo: _check_services
	@echo ""
	@echo "=== STEP 1: Catalog ==="
	@curl -sf http://localhost:8001/catalog_proxy | python3 -m json.tool
	@echo ""
	@echo "=== STEP 2: Consumer negotiation (LLM + chain, ~30-60s) ==="
	@curl -sf -X POST http://localhost:8001/chat \
		-H "Content-Type: application/json" \
		-d '{"message":"I need 100 Mbps for 10 minutes","model":"$(or $(OLLAMA_MODEL),qwen3:4b)"}' \
		| python3 -m json.tool
	@echo ""
	@echo "=== STEP 3: Provider inventory after purchase ==="
	@curl -sf http://localhost:8002/inventory | python3 -m json.tool

_check_services:
	@curl -sf http://localhost:8001/address > /dev/null || (echo "ERROR: consumer agent not running on :8001" && exit 1)
	@curl -sf http://localhost:8002/address > /dev/null || (echo "ERROR: provider agent not running on :8002" && exit 1)
	@echo "Services OK"
