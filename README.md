# concept-mapmaker

Build interactive concept maps from Markdown and a small optional YAML presentation spec.
Each build creates an HTML map, a downloadable Markdown copy, and a PDF.

The HTML is a single generated file, but it loads D3 and Markmap from jsDelivr when opened.

## Install

```bash
pip install concept-mapmaker
```

PDF generation is included in the default installation.

For local development:

```bash
python -m pip install -e ".[dev]"
```

## Build and preview

Run commands from the root of your content project:

```bash
concept-map build my-map.md
concept-map serve my-map.html
```

Or start from a scaffold:

```bash
concept-map init          # writes map.md + config.yaml + map.css into the current folder
```

The default project layout is one flat folder:

```text
my-project/
  my-map.md
  config.yaml         # optional; auto-discovered beside the doc
  map.css             # optional; custom colors, auto-discovered beside the doc
  web/                # generated
    my-map.html
    downloads/
      my-map.md
      my-map.pdf
```

Useful alternatives:

```bash
concept-map build my-map.md --spec presentation.yaml
concept-map build my-map.md --output public/map.html
concept-map serve
concept-map serve public/map.html --port 8000
```

## Markdown authoring contract

- Headings (`#` through `######`) define structure.
- Bullets written as `- **Name**: description` define concepts.
- Two spaces of bullet indentation add one level beneath the current heading.
- A paragraph directly under a heading becomes that heading node's description.
- A `-*-` token on a heading or concept marks that node with a star.

## YAML spec

Every field is optional:

| Key | Purpose | Default |
|---|---|---|
| `title` | Header brand and panel eyebrow | `Map` |
| `subtitle` | Small header subtitle | Empty |
| `page_title` | Browser tab title | `title` |
| `legend` | Ordered branch-type matching + labels | One neutral color, no legend |

Example:

```yaml
title: Coffee Map
subtitle: A Tiny Example Map

legend:
  - {match: '^1\.', key: beans, label: Beans}
  - {match: '^2\.', key: brewing, label: Brewing}
```

Each legend entry is a branch type: the first `match` regex that hits a node's label sets its
branch, and the subtree inherits it. Branches are colored from a built-in palette in order (the
palette lives in the display template). With no legend, all nodes use one neutral color and the
legend is hidden.

## Custom colors (`map.css`)

To override colors, drop a `map.css` beside the source doc (or in the project root). It is
appended after the generated branch bindings, so its rules win. Redefine a palette slot, or a
specific branch:

```css
:root { --pal-1: #b5179e; }        /* recolor the first branch type */
:root { --branch-brewing: #0e7c86; } /* recolor one branch by key */
```

See `examples/map.css` for a copy-paste starting point (`concept-map init` also writes one).

## Python API

```python
from concept_mapmaker import build_map, load_spec

spec = load_spec("config.yaml")
build_map("my-map.md", spec, output="web/my-map.html")
```

Writable output always goes to the caller's project; package installation files are read-only.
The display template is bundled inside the installed wheel.

## Build a distribution

```bash
python -m build
python -m twine check dist/*
```

Try the wheel in a clean environment and publish to TestPyPI before the first production
release. Choose and add a `LICENSE` file before publishing publicly.

The worked example lives in `examples/`:

```bash
concept-map build examples/demo.md --spec examples/config.yaml
```
