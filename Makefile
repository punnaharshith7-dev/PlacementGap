.PHONY: dev test eval eval-heldout ablate chaos calibrate seed demo

dev:
	docker compose up -d --build

test:
	docker compose exec -T api pytest -q tests

eval:
	docker compose exec -T api python -m evals.runner

eval-heldout:
	docker compose exec -T api python -m evals.runner --heldout --confirm

ablate:
	docker compose exec -T api python -m evals.ablations --heldout --confirm

chaos:
	docker compose exec -T api python -m evals.chaos --chaos-rate 0.3

calibrate:
	docker compose exec -T api python -m evals.calibrate

seed:
	docker compose exec -T api python -m evals.seed

demo:
	docker compose exec -T api python -m evals.demo
