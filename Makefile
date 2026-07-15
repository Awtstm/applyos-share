# ApplyOS — developer targets. Typst version is pinned in .typst-version.
# Fonts are vendored in assets/fonts/ and used exclusively (system fonts
# ignored) so PDFs are byte-stable across machines and CI.

TYPST_VERSION = $(shell cat .typst-version)
TYPST = typst compile --font-path assets/fonts --ignore-system-fonts

# render-cv / render-letter default to the committed example profile;
# for real data: make render-cv PROFILE=profile/profile.yaml TAG=real
PROFILE ?= profile/profile.example.yaml
TAG ?= example

.PHONY: check-typst render-example lint test ci

check-typst:
	@typst --version | grep -q "^typst $(TYPST_VERSION)" \
		|| { echo "ERROR: expected typst $(TYPST_VERSION), got: '$$(typst --version 2>/dev/null || echo not installed)'"; exit 1; }

render-example: check-typst
	@mkdir -p output
	$(TYPST) --input data='{"name": "ApplyOS"}' templates/typst/example.typ output/example.pdf
	@echo "OK: output/example.pdf"

render-cv: check-typst
	@mkdir -p output
	$(TYPST) --input data="$$(uv run python -m app.render_data cv --lang de --profile $(PROFILE))" templates/typst/cv.typ output/cv-$(TAG)-de.pdf
	$(TYPST) --input data="$$(uv run python -m app.render_data cv --lang en --profile $(PROFILE))" templates/typst/cv.typ output/cv-$(TAG)-en.pdf
	@echo "OK: output/cv-$(TAG)-{de,en}.pdf"

render-letter: check-typst
	@mkdir -p output
	$(TYPST) --input data="$$(uv run python -m app.render_data letter --lang de --profile $(PROFILE))" templates/typst/letter.typ output/letter-$(TAG)-de.pdf
	$(TYPST) --input data="$$(uv run python -m app.render_data letter --lang en --profile $(PROFILE))" templates/typst/letter.typ output/letter-$(TAG)-en.pdf
	@echo "OK: output/letter-$(TAG)-{de,en}.pdf"

lint:
	uv run ruff check .

test:
	uv run pytest

ci: lint test render-example
