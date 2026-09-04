# concept-mapmaker

[![PyPI version](https://img.shields.io/pypi/v/concept-mapmaker.svg)](https://pypi.org/project/concept-mapmaker/)
[![Python versions](https://img.shields.io/pypi/pyversions/concept-mapmaker.svg)](https://pypi.org/project/concept-mapmaker/)
[![License: MIT](https://img.shields.io/pypi/l/concept-mapmaker.svg)](https://github.com/JLichwa80/concept-mapmaker/blob/main/LICENSE)

Build interactive concept maps from Markdown and a small optional YAML presentation spec.
Each build creates an HTML map, a downloadable Markdown copy, and a PDF.

The HTML is a single generated file, but it loads D3 and Markmap from jsDelivr when opened.

![A generated concept map: a color-coded Markmap tree with a legend and an info panel](https://raw.githubusercontent.com/JLichwa80/concept-mapmaker/main/docs/images/overview.png)

Branch types are color-coded from the legend; clicking any node reveals its description in the
side panel, with a copyable deep link:

![Clicking a node highlights it and shows its description in the side panel](https://raw.githubusercontent.com/JLichwa80/concept-mapmaker/main/docs/images/node-selected.png)

## Install

```bash
pip install concept-mapmaker
```

Requires Python 3.10+. PDF generation is included in the default installation.

## Quickstart

Run these from your content project's folder. `init` scaffolds a starter map, `build` renders it,
and `serve` previews the result over HTTP:

```bash
concept-map init          # writes map.md + config.yaml + map.css into the current folder
concept-map build map.md  # -> web/map.html (+ web/downloads/*.md/.pdf)
concept-map serve         # preview at http://127.0.0.1:8080
```

A project is one flat folder — a source doc plus two optional files, and a generated `web/`:

```text
my-project/
  my-map.md
  config.yaml         # optional; presentation spec, auto-discovered beside the doc
  map.css             # optional; custom colors, auto-discovered beside the doc
  web/                # generated
    my-map.html
    downloads/
      my-map.md
      my-map.pdf
```

## CLI reference

```bash
concept-map init                                     # scaffold map.md + config.yaml + map.css
concept-map build my-map.md                          # -> web/my-map.html
concept-map build my-map.md --spec presentation.yaml # explicit spec (else config.yaml beside doc)
concept-map build my-map.md --output public/map.html # override the output path
concept-map build my-map.md --template custom.html   # custom node-display layout
concept-map serve                                    # preview the newest map in web/
concept-map serve public/map.html --port 8000        # preview a specific file / port
```

The bundled template *is* the default look; `--template` is a layout-only extension point for
supplying your own node-display HTML. See "Python API" for passing extra `__KEY__` values a custom
template needs.

## Markdown authoring contract

- Headings (`#` through `######`) define structure.
- Bullets written as `- **Name**: description` define concepts.
- Two spaces of bullet indentation add one level beneath the current heading.
- A paragraph directly under a heading becomes that heading node's description.
- A `-*-` token on a heading or concept marks that node with a star.

The map shown above comes straight from these rules. Its source (`examples/demo.md`) begins:

```markdown
# Coffee

A tiny example map — beans, ways to brew, and a few drinks.

## 1. Beans

The two species behind almost all coffee.

- **Arabica**: Smoother and sweeter with more aroma; most specialty coffee.
- **Robusta**: More caffeine and a bolder, more bitter cup; common in espresso blends.
```

`# Coffee` becomes the root (its paragraph is the root's description); each `## N.` heading is a
branch whose numbering the legend matches on (below); and each `- **Name**: description` bullet is
a clickable concept node with the text shown in the side panel. Build it yourself with:

```bash
concept-map build examples/demo.md --spec examples/config.yaml
concept-map serve web/demo.html
```

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

To embed the engine, `build_map` exposes three optional extension seams: `template` (a path to a
custom node-display template), `parse_fn` (swap in a different input parser), and `extra_context`
(supply or override `__KEY__` values your custom template consumes):

```python
build_map("my-map.md", spec, output="web/my-map.html",
          template="custom.html", extra_context={"FOOTER": "© 2026"})
```

## Contributing and releasing

Development setup, the test suite, and the maintainer release process (Trusted Publishing to
TestPyPI/PyPI) are documented in [`CONTRIBUTING.md`](CONTRIBUTING.md). The worked example lives in
`examples/`.
