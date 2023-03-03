dist=dist

build: test
	@rm -rf ${dist}
	@pip install -r requirements.txt -t ${dist}
	@cp index.py ${dist}/
	@cd ${dist}; zip -qr partitioner.zip .

test:
	@pytest
