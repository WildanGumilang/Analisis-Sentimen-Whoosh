# Jalankan dari root project. Tiap tahap dijalankan terpisah, dengan pemeriksaan hasil di antaranya.
PY = .venv/Scripts/python

scrape-test:
	$(PY) src/scrape.py --limit 20
scrape:
	$(PY) src/scrape.py
preprocess:
	$(PY) src/preprocess.py
filter:
	$(PY) src/filter.py
baseline:
	$(PY) src/baseline.py
label-prep:
	$(PY) src/label_prep.py
label-merge:
	$(PY) src/label_merge.py
evaluate:
	$(PY) src/evaluate.py
analyze:
	$(PY) src/analyze.py
	$(PY) src/analyze_extended.py

.PHONY: scrape-test scrape preprocess filter baseline label-prep label-merge evaluate analyze
