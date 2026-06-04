.PHONY: up up-real down demo contracts logs clab-up clab-down demo-real

up:
	@mkdir -p contracts/deployments
	docker compose up --build -d --remove-orphans
	@echo "Services starting... UI at http://localhost:8501"

up-real:
	@SDN_MOCK=false $(MAKE) up

down:
	docker compose down

down-clean:
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
		-d '{"message":"I need 5 Mbps for 10 minutes","model":"$(or $(OLLAMA_MODEL),llama3.2:3b)"}' \
		| python3 -m json.tool
	@echo ""
	@echo "=== STEP 3: Provider inventory after purchase ==="
	@curl -sf http://localhost:8002/inventory | python3 -m json.tool

_check_services:
	@for i in $$(seq 1 30); do \
	  curl -sf http://localhost:8001/address > /dev/null 2>&1 && \
	  curl -sf http://localhost:8002/address > /dev/null 2>&1 && \
	  echo "Services OK" && exit 0; \
	  sleep 1; \
	done; \
	echo "ERROR: agents not ready on :8001/:8002 after 30s"; exit 1

CLAB_REPO ?= ../srl-gnmi-bandwidth-poc

clab-up:
	@test -d $(CLAB_REPO) || (echo "ERROR: brother repo not at $(CLAB_REPO)"; exit 1)
	cd $(CLAB_REPO) && bash scripts/deploy.sh
	cd $(CLAB_REPO) && bash scripts/push-config.sh
	@echo "ContainerLab ready."

clab-down:
	cd $(CLAB_REPO) && bash scripts/destroy.sh

demo-real: _check_services
	@echo ""
	@echo "=== Running demo with REAL SDN (SDN_MOCK=false) ==="
	@docker compose stop provider-agent
	@SDN_MOCK=false docker compose up -d provider-agent
	@sleep 5
	@$(MAKE) demo
	@echo ""
	@echo "=== Verifying medium tier on ce3 → ce4 (expected ~5 Mbps) ==="
	@docker exec clab-bandwidth-poc-ce4 iperf3 -s -1 -p 5201 >/dev/null &
	@sleep 1
	@docker exec clab-bandwidth-poc-ce3 iperf3 -c 192.168.4.10 -p 5201 -t 5 -u -b 15M -J | python3 -c "import sys, json; d=json.load(sys.stdin); print('Sender Mbps:', d['end']['sum']['bits_per_second']/1e6)"
