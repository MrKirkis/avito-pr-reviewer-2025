run:
	uvicorn main:app --host 0.0.0.0 --port 8080 --reload

up:
	docker-compose up --build -d

down:
	docker-compose down

test:
	pytest -v
