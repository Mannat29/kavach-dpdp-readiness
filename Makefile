.PHONY: run seed test

run:
	flask --app app run --debug

seed:
	python -m app.seed

test:
	pytest tests/ -v
