# Ajustar el sábado a los ficheros reales
check:
	python3 src/validate.py && touch out/.check_passed

submit:
	@test -f out/.check_passed || (echo "Falta make check" && exit 1)
	@echo "Subir out/ segun indique la organizacion"
