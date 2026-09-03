# Contributing to concept-mapmaker

Thanks for your interest in improving `concept-mapmaker`. This is a small, deliberately
minimal tool — please keep changes focused and the dependency footprint light.

## Development setup

```bash
git clone https://github.com/JLichwa80/concept-mapmaker.git
cd concept-mapmaker
python -m pip install -e ".[dev]"
```

## Running the tests

```bash
python -m pytest tests/ -q
```

Run a single test while iterating:

```bash
python -m pytest tests/test_builder.py::BuilderTests::test_bullet_becomes_concept_with_description
```

## Try your change end to end

```bash
concept-map build examples/demo.md   # -> web/demo.html (+ web/downloads/*)
concept-map serve web/demo.html      # preview at http://127.0.0.1:8080
```

## Guidelines

- **Keep it minimal.** Runtime deps are intentionally just `PyYAML` and `markdown-pdf`;
  `server.py` is pure stdlib. Discuss any new dependency in an issue first.
- **The display template is fixed.** `templates/default.html` *is* the tool's look; restyle by
  editing it directly rather than adding template-selection options.
- **Writable output belongs to the caller's project** — never write into the installed package.
- **Preserve the authoring contract** (headings = structure, `- **Name**: desc` = concepts,
  `-*-` = star) and the `mm.renderData()` fold gotcha noted in `CLAUDE.md`.
- Add or update a test for any behavior change, and keep `python -m twine check dist/*` green.

## Submitting changes

1. Fork and branch from `main`.
2. Make the change with tests; run `python -m pytest tests/ -q`.
3. Open a pull request describing the motivation and behavior change.

## Release process (maintainers)

Publishing runs on GitHub Actions via Trusted Publishing — no tokens are stored.

1. **Dry run to TestPyPI:** Actions tab → *Publish* → *Run workflow* (manual dispatch).
   Then verify in a clean environment:
   ```bash
   pip install -i https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ concept-mapmaker
   concept-map --version
   ```
2. **Bump `version`** in `pyproject.toml` (PyPI versions are permanent and cannot be reused).
3. **Publish to PyPI:** cut a GitHub Release for the new tag — the workflow builds and uploads
   automatically.
   ```bash
   gh release create v0.1.0 --title "v0.1.0" --notes "..."
   ```
