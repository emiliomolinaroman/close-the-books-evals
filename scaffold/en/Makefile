# Adapt to the real files on hackathon day
check:
	python3 src/validate.py && touch out/.check_passed

submit:
	@test -f out/.check_passed || (echo "Run make check first" && exit 1)
	@echo "Upload out/ as the organizers instruct"
