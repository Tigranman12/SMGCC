.PHONY: test test-smgcc test-cc test-cola lint clean

test:
	python3 -m unittest discover -s tests -v

test-smgcc:
	python3 -m unittest tests.test_smgcc -v

test-cc:
	python3 -m unittest tests.test_cc -v

test-cola:
	python3 -m unittest tests.test_cola -v

lint:
	python3 -m py_compile smgcc/peg.py
	python3 -m py_compile smgcc/grammar.py
	python3 -m py_compile smgcc/calc.py
	python3 -m py_compile smgcc/driver.py

clean:
	rm -rf __pycache__ smgcc/__pycache__ tests/__pycache__ cola/__pycache__
	rm -rf .pytest_cache
	rm -rf build dist *.egg-info
	find . -name "*.pyc" -delete
