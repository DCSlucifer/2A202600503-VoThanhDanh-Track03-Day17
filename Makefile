.PHONY: install test bench bench-openai run clean

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

bench:
	python -m scripts.run_benchmark

bench-openai:
	AGENT_RUNTIME__MODE=openai AGENT_EMBEDDING__MODE=openai python -m scripts.run_benchmark

run:
	python -m agent.cli chat

clean:
	rm -rf outputs/runs/* outputs/reports/* outputs/chroma outputs/episodic
