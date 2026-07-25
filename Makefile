.PHONY: install dev build test stress security lint run-edge run-test clean

install:
	pip install -r requirements.txt

dev:
	cd src/agui && npm install

build:
	cd src/agui && npm run build

test:
	pytest tests/ -v

stress:
	pytest tests/stress/ -v

security:
	pytest tests/security/ -v

lint:
	python -m py_compile main.py
	python -m py_compile src/gateway/server.py
	python -m py_compile src/servers/stream_server.py
	python -m py_compile src/servers/inference_server.py
	python -m py_compile src/servers/rule_server.py
	python -m py_compile src/testing/testing_agent.py

run-edge:
	python3 main.py --host 0.0.0.0 --port 9000

run-test:
	python3 src/testing/testing_agent.py --host 192.168.1.10 --output test-report.json

clean:
	rm -rf src/agui/dist
	rm -f test-report.json