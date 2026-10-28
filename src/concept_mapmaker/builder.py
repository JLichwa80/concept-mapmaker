"""Generic builder for the interactive concept maps.

Renders a markdown doc (headings for structure, `- **Name**: desc` bullets for concepts, a
paragraph (or `>` Markdown block) under a heading as its description, and a `-*-` token to star a node) into a
self-contained interactive HTML map. You pass the source doc; everything else is optional:

  * input markdown  — the source doc, passed as the positional argument
  * output HTML     — defaults to `web/<input-stem>.html`; override with `--output`
  * spec (YAML)     — per-map presentation (title, subtitle, legend branch types).
                      Auto-found at `config.yaml` beside the doc, or named with `--spec`.

The display template defaults to the bundled `templates/default.html`, which holds the default
color palette; the spec's `legend` are ordered `{match, key, label}` rules that a node takes by
the first rule whose regex matches its label (else it inherits its parent / stays structural), and
each legend key is bound to a palette slot at build time. A project `map.css` can override the
colors. The node-display template is an extension point: pass a custom one via `--template` (or
`load_template(path)` / `build_map(..., template=…)`), supply any extra `__KEY__` values it needs
via `extra_context`, and style with CSS — the engine stays presentation-agnostic.

Usage after installation:
    concept-map build demo.md                          # -> web/demo.html
    concept-map build demo.md --output web/x.html
    concept-map build demo.md --spec config.yaml
    concept-map build demo.md --template custom.html   # custom node-display layout
"""
import re
import json
import html
import shutil
from importlib import resources
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
NAME_RE = re.compile(r"^\*\*(.+?)\*\*:?\s*(.*)$")
# An `<a id>` anchor authored on its own line as an explicit link target; the parser skips it
# so it never becomes a node.
QUOTE_RE = re.compile(r"^>\s?(.*)$")
ANCHOR_ONLY_RE = re.compile(r'^<a id="[^"]*">\s*</a>$')

# A template placeholder is an ALL-CAPS token wrapped in double underscores, e.g. __DATA__.
# (JS internals like `g.__data__` are lower-case, so they never match.)
_PLACEHOLDER_RE = re.compile(r"__[A-Z][A-Z0-9_]*__")


# --- Markdown rendering -----------------------------------------------------------------

# Authors may backslash-escape punctuation in the source (e.g. `A\*`) so markdown doesn't read
# it as syntax; we resolve those escapes ourselves or the backslash leaks into the map.
MD_ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")


def md_unescape(text: str) -> str:
    """Resolve markdown backslash-escapes (`\\*` -> `*`) so labels/desc show the intended char."""
    return MD_ESCAPE_RE.sub(r"\1", text)


# The spec is a fixed-name `config.yaml` (or `.yml`) — one per project folder.
SPEC_EXTS = ("yaml", "yml")


def find_spec(input_file, project_root):
    """Locate an optional `config.yaml` (or `.yml`) beside the doc, then in the project root.

    Mirrors how `load_map_css` finds `map.css`, so a project is one flat folder: `<doc>.md` +
    optional `config.yaml` + optional `map.css`. Returns the path, or None if absent."""
    for d in (Path(input_file).parent, Path(project_root)):
        for ext in SPEC_EXTS:
            cand = d / f"config.{ext}"
            if cand.is_file():
                return cand
    return None


# --- Download doc -----------------------------------------------------------------------
# Each build copies the source `.md` to web/downloads/<stem>.md and renders a matching PDF
# (render_pdf) that the map's Download button links to.


def render_pdf(md_path, pdf_path):
    """Render the download markdown to the PDF the map's Download button points at.

    Uses the default `markdown-pdf` dependency (PyMuPDF-based, with no LaTeX requirement).
    The import guard provides a useful message for damaged or manually trimmed installs."""
    try:
        from markdown_pdf import MarkdownPdf, Section
    except ImportError:
        print(f"  note: skipping {pdf_path.name} - run `pip install markdown-pdf` to render PDFs")
        return
    md = Path(md_path).read_text(encoding="utf-8")
    pdf = MarkdownPdf(toc_level=2)                 # build a table of contents from #/## headings
    pdf.add_section(Section(md, toc=True))
    pdf.save(str(pdf_path))
    print(f"  download: {pdf_path}")


# --- Parsing ----------------------------------------------------------------------------

# Explicit star marker: an author writes `-*-` anywhere on a node's line (heading or bullet)
# to flag it as noteworthy; the map shows a small `*` on that node. The token is removed from
# the displayed label/description.
MARK_TOKEN = "-*-"


def take_mark(text):
    """Return (text_without_token, is_marked): strip any `-*-` marker and report if it was
    present. Leftover double spaces from removing an inline token are collapsed."""
    if MARK_TOKEN not in text:
        return text, False
    cleaned = re.sub(r"\s{2,}", " ", text.replace(MARK_TOKEN, "")).strip()
    return cleaned, True


def parse(md: str):
    """Return (tree_root, descriptions) from the markdown.

    Headings build the tree; `- **Name**: desc` bullets add concept nodes; a plain paragraph
    under a heading becomes that heading's description. An explicit `-*-` token stars a node.
    """
    root = {"id": 0, "label": "Map", "children": []}  # overwritten by the doc's H1 when present
    descriptions = {}
    counter = [0]
    stack = [(-1, root)]  # (depth, node); root at -1 so top headings attach to it
    heading_depth = -1
    last_node = None
    prev_quote = False

    def new_node(depth, label, desc):
        counter[0] += 1
        node = {"id": counter[0], "label": label, "children": []}
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1]["children"].append(node)
        stack.append((depth, node))
        if desc:
            descriptions[node["id"]] = desc
        return node

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        h = HEADING_RE.match(line)
        if h:
            depth = len(h.group(1)) - 1
            title, marked = take_mark(h.group(2).strip())
            heading_depth = depth
            if depth == 0:
                root["label"] = title
                last_node = root
            else:
                last_node = new_node(depth, title, "")
            if marked:
                last_node["mark"] = True
            prev_quote = False
            continue

        b = BULLET_RE.match(line)
        if b:
            inner, marked = take_mark(b.group(2).strip())
            indent = len(b.group(1))
            depth = heading_depth + 1 + indent // 2
            m = NAME_RE.match(inner)
            label, desc = (m.group(1).strip(), m.group(2).strip()) if m else (inner, "")
            last_node = new_node(depth, label, desc)
            if marked:
                last_node["mark"] = True
            prev_quote = False
            continue

        stripped = line.strip()

        # An explicit `<a id>` GitHub link target authored on its own line — not content.
        if ANCHOR_ONLY_RE.match(stripped):
            continue

        if last_node is not None:
            nid = last_node["id"]
            q = QUOTE_RE.match(stripped)
            if q:
                # A `>` block is the node's Markdown description (headings, lists, tables...).
                sep = "" if prev_quote or not descriptions.get(nid) else "\n\n"
                descriptions[nid] = descriptions.get(nid, "") + sep + q.group(1) + "\n"
                prev_quote = True
                continue
            # Plain paragraph -> the current node's description.
            sep = "\n\n" if prev_quote else " "
            descriptions[nid] = (descriptions.get(nid, "").rstrip("\n") + sep + stripped).strip()
        prev_quote = False

    return root, {i: d.strip() for i, d in descriptions.items()}


# --- Branch assignment (data-driven) ----------------------------------------------------

# The default palette lives in the template's `:root` as `--pal-1`..`--pal-N`; keep this count
# in sync with it. Legend keys are bound to slots in order (cycling past N); a project `map.css`
# can override any `--pal-*` or `--branch-<key>`.
PALETTE_SIZE = 8


def build_branch_css(branch_keys):
    """Bind each legend key to a palette slot for the template's `__BRANCHCSS__` block.

    Emits `--branch-<key>:var(--pal-N)` (so JS color reads resolve for the legend, connectors,
    and panel accent) plus `.pill.b-<key>{--nc:var(--branch-<key>)}`. Hues live in the template
    palette; keys cycle past PALETTE_SIZE. No keys => "" => nodes use --branch-navy."""
    if not branch_keys:
        return ""
    vars_ = [f"    --branch-{k}:var(--pal-{i % PALETTE_SIZE + 1});"
             for i, k in enumerate(branch_keys)]
    rules = [f"  .markmap-foreign span.pill.b-{k}{{--nc:var(--branch-{k})}}" for k in branch_keys]
    root = "  :root{\n" + "\n".join(vars_) + "\n  }"
    return "\n".join([root, *rules])


def assign_from_rules(root, rules):
    """Map each node id -> branch key, or None (structural).

    `rules` is an ordered list of `(compiled_regex, key)`. A node with no branch yet takes
    the first rule whose regex matches its label; otherwise it stays None and its children
    are tested the same way. Once a node has a branch, its whole subtree inherits it. This
    lets a label prefix (e.g. section numbers like `2.1`) drive coloring purely from the
    spec's `legend`.
    """
    out = {}

    def walk(node, branch):
        out[node["id"]] = branch
        for c in node["children"]:
            b = branch
            if b is None:
                label = c["label"].strip()
                for rx, key in rules:
                    if rx.match(label):
                        b = key
                        break
            walk(c, b)

    walk(root, None)
    return out


# --- Tree -> markmap data ---------------------------------------------------------------

# Custom fold affordance: a sibling of the pill (kept OUTSIDE it so a click doesn't hit the
# pill's selection test). markmap positions it; open/closed is pure CSS off `.markmap-fold`.
# Bigger/easier target than markmap's native fold circle. Emitted only for nodes with children.
CHEVRON = ('<span class="fold-toggle" aria-hidden="true">'
           '<svg viewBox="0 0 12 12"><path d="M7.5 2 L3.5 6 L7.5 10"/></svg></span>')


def to_markmap(node, branch_of):
    """Render the tree into markmap node objects.

    Parents get the fold `CHEVRON`. Our build-time id rides in markmap's `payload` (preserved
    across renders), so the template identifies a clicked node via `node.payload.id` with no
    HTML parsing. Each pill carries a `b-<key>` class (or plain `pill`); the template CSS colors it.
    """
    label = html.escape(md_unescape(node["label"]))
    key = branch_of.get(node["id"])
    cls = f"pill b-{key}" if key else "pill"
    # Small star on nodes flagged with `-*-` (see take_mark), so they stand out without clicking.
    star = '<span class="adv" title="Noteworthy">*</span>' if node.get("mark") else ""
    toggle = CHEVRON if node["children"] else ""
    return {
        "content": f'<span class="{cls}">{label}{star}</span>{toggle}',
        "payload": {"id": node["id"]},
        "children": [to_markmap(c, branch_of) for c in node["children"]],
    }


# --- Deep-link maps ---------------------------------------------------------------------

def slugify(text: str) -> str:
    """Label -> URL-fragment slug, e.g. `2.4.5 Reinforcement Learning [..]` -> `reinforcement-learning`.
    Drops bracketed/parenthetical tags and leading section numbers to keep links short and readable."""
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)      # strip [..] and (..) tags
    text = re.sub(r"^[\d][\d.]*\s+", "", text.strip())      # strip leading section code "2.4.5 " (only when followed by space, so "1D CNNs" is kept)
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "node"


def build_link_maps(root):
    """Return (labels, slugs): id->label and id->unique-slug for deep links."""
    labels, slugs, seen = {}, {}, {}

    def walk(node):
        nid = str(node["id"])
        labels[nid] = node["label"]
        base = slugify(node["label"])
        slug, i = base, 2
        while slug in seen:
            slug = f"{base}-{i}"
            i += 1
        seen[slug] = True
        slugs[nid] = slug
        for c in node["children"]:
            walk(c)

    walk(root)
    return labels, slugs


# --- Templating -------------------------------------------------------------------------

def load_template(name_or_path=None):
    """Return the text of a display (node-display) template.

    `name_or_path` None → the bundled `templates/default.html` (the tool's default look, still the
    default for every map). Pass a path to plug in a **custom** node-display template — the map's
    look is then yours. Extensibility is layout-only: pass any extra `__KEY__` values your template
    needs via `build`/`build_map`'s `extra_context`, and style with a project `map.css` or the
    template's own CSS. The engine itself stays presentation-agnostic."""
    if name_or_path is None:
        template = resources.files("concept_mapmaker").joinpath("templates/default.html")
        return template.read_text(encoding="utf-8")
    p = Path(name_or_path)
    if p.is_file():
        return p.read_text(encoding="utf-8")
    raise SystemExit(f"Template not found: {name_or_path}")


def script_json(value):
    """JSON for embedding in an inline <script>: `</` is escaped so text such as `</script>`
    in a label or description can't end the script block early."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_template(template, context):
    """Fill `__KEY__` placeholders from `context` (values already stringified) and return
    the result. Warns if any `__UPPER__` placeholder is left unresolved — the usual sign a
    template references a name the spec/engine didn't supply."""
    out = template
    for key, val in context.items():
        out = out.replace(f"__{key}__", val)
    missing = sorted(set(_PLACEHOLDER_RE.findall(out)))
    if missing:
        print(f"  warning: unresolved template placeholders: {', '.join(missing)}")
    return out


def build_context(root, descriptions, spec, input_file, download_pdf_href, map_css=""):
    """Turn a parsed doc + spec into the placeholder dict a display template consumes.

    Returns `(context, slugs)`. `context` maps placeholder name -> stringified value (JSON
    for the data blobs). Colors are not here: pills carry branch-key classes and `META`
    carries the branch key, both resolved to hex by the template's CSS/JS. `map_css` is an
    optional project stylesheet appended after the generated branch bindings to override them.
    """
    legend = spec.get("legend", [])
    rules = [(re.compile(b["match"]), b["key"]) for b in legend]
    label_of = {b["key"]: b["label"] for b in legend}
    branch_of = assign_from_rules(root, rules)

    meta = {str(nid): {"k": k, "b": label_of[k]}
            for nid, k in branch_of.items() if k in label_of}
    palette = [[b["key"], b["label"]] for b in legend]

    # Bind each legend key to a palette slot; hues live in the template. An optional project
    # map.css is appended after to override via the cascade. No legend => "" => --branch-navy.
    branch_css = build_branch_css([b["key"] for b in legend])
    if map_css:
        branch_css = (branch_css + "\n" + map_css).strip()

    labels, slugs = build_link_maps(root)
    stem = Path(input_file).stem

    # `title` drives the tab title, header brand, and panel eyebrow; defaults to "Map". The SVG
    # download name and map hint are fixed here, not spec fields.
    title = str(spec.get("title") or "Map")
    page_title = str(spec.get("page_title") or title)

    kicker = title
    context = {
        "PAGETITLE": html.escape(page_title),
        "BRAND": html.escape(title),
        "SUBTITLE": html.escape(str(spec.get("subtitle", ""))),
        "HINT": "Click a node to read about it",
        "KICKER": html.escape(kicker),
        "KICKERJSON": script_json(kicker),
        "DLNAME": script_json(f"{stem}.svg"),
        "DLPDF": html.escape(download_pdf_href, quote=True),
        "BRANCHCSS": branch_css,
        "DATA": script_json(to_markmap(root, branch_of)),
        "DESC": script_json(descriptions),
        "META": script_json(meta),
        "LABELS": script_json(labels),
        "SLUGS": script_json(slugs),
        "PALETTE": script_json(palette),
    }
    return context, slugs


# --- Build ------------------------------------------------------------------------------

def build(input_file, output, template, spec, download_pdf_href,
          *, parse_fn=parse, extra_context=None, map_css=""):
    """Parse `input_file`, render `template` with the derived context + spec, write `output`.

    Seams for reuse: `parse_fn` (a different input md shape; must return
    `(root, descriptions)`) and `extra_context` (extra `__KEY__` values for a custom
    template). `map_css` is optional project CSS appended after the generated branch bindings.
    Returns the id->slug map.
    """
    md = Path(input_file).read_text(encoding="utf-8")
    root, descriptions = parse_fn(md)
    context, slugs = build_context(
        root, descriptions, spec, input_file, download_pdf_href, map_css
    )
    if extra_context:
        context.update(extra_context)
    html_out = render_template(template, context)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")
    print(f"Parsed {len(descriptions)} described nodes; "
          f"wrote {out} ({len(html_out)//1024} KB)")
    return slugs


def resolve_input(arg, project_root=None):
    """Resolve an input path from the caller's directory, never the installed package."""
    project_root = Path(project_root or Path.cwd())
    for cand in (Path(arg), project_root / arg):
        if cand.is_file():
            return cand.resolve()
    raise SystemExit(f"Input markdown not found: {arg}")


def load_spec(spec_ref):
    """Load a YAML spec dict from a path, or {} when there's no spec (pure defaults)."""
    if not spec_ref:
        return {}
    try:
        import yaml
    except ImportError:
        raise SystemExit("Reading a spec needs PyYAML; reinstall concept-mapmaker.")
    data = yaml.safe_load(Path(spec_ref).read_text(encoding="utf-8"))
    return data or {}


def load_map_css(input_file, project_root):
    """Optional project CSS appended after the generated branch bindings at `__BRANCHCSS__`.

    Looks for `map.css` in the project root and beside the input doc; any found are
    concatenated (project root first) so their rules override the template's `--pal-*` palette
    via the cascade. Absent => "" (the template's default palette stands)."""
    seen, parts = set(), []
    for d in (Path(project_root), Path(input_file).parent):
        cand = (d / "map.css").resolve()
        if cand in seen:
            continue
        seen.add(cand)
        if cand.is_file():
            parts.append(cand.read_text(encoding="utf-8").strip())
    return "\n".join(p for p in parts if p)


def build_map(input_file, spec, *, output=None, project_root=None,
              template=None, parse_fn=parse, extra_context=None):
    """Build one map from a passed `input_file` (Path) and a presentation `spec` dict.

    Output defaults to `<project_root>/web/<input-stem>.html`; pass `output` to override.
    Generated Markdown and PDF downloads live beside it in `downloads/`. All writable paths
    belong to the caller's project, never the installed Python package.

    Extension seams (for consumers embedding the engine): `template` overrides the bundled
    node-display template (a path, resolved by `load_template`), `parse_fn` swaps in a different
    input parser, and `extra_context` supplies/overrides `__KEY__` values the custom template
    consumes. All optional — defaults reproduce the standard build exactly.
    """
    project_root = Path(project_root or Path.cwd()).resolve()
    input_file = Path(input_file).resolve()
    out = Path(output) if output else project_root / "web" / f"{input_file.stem}.html"
    if not out.is_absolute():
        out = project_root / out

    downloads_dir = out.parent / "downloads"
    dl_md = downloads_dir / f"{input_file.stem}.md"
    dl_pdf = downloads_dir / f"{input_file.stem}.pdf"
    slugs = build(
        input_file,
        out,
        load_template(template),
        spec,
        f"downloads/{dl_pdf.name}",
        parse_fn=parse_fn,
        extra_context=extra_context,
        map_css=load_map_css(input_file, project_root),
    )

    downloads_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_file, dl_md)
    print(f"  download: {dl_md}")
    render_pdf(dl_md, dl_pdf)
    return slugs


def run_build(input_arg, *, spec=None, output=None, project_root=None, template=None):
    """Build one map from a CLI-style request: resolve the input and its spec, then build.

    `spec` is an explicit spec path, or None to auto-discover `config.yaml` beside the doc.
    `output` overrides the default `web/<input-stem>.html`. `template` overrides the bundled
    node-display template with a custom one (a path). Called by the `concept-map` CLI.
    """
    project_root = Path(project_root or Path.cwd()).resolve()
    input_file = resolve_input(input_arg, project_root)
    spec_ref = spec or find_spec(input_file, project_root)
    if spec_ref and not Path(spec_ref).is_absolute():
        spec_ref = project_root / spec_ref
    build_map(
        input_file,
        load_spec(spec_ref),
        output=output,
        project_root=project_root,
        template=template,
    )


# Starter files copied by `concept-map init`, bundled at templates/scaffold/ in the wheel.
SCAFFOLD_FILES = ("map.md", "config.yaml", "map.css")


def run_init(dest="."):
    """Scaffold a starter project (`map.md` + `config.yaml` + `map.css`) into `dest`.

    Copies the bundled `templates/scaffold/` assets, skipping any file that already exists so a
    re-run never clobbers work. Called by the `concept-map init` CLI."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    scaffold = resources.files("concept_mapmaker").joinpath("templates/scaffold")
    written, skipped = [], []
    for name in SCAFFOLD_FILES:
        target = dest / name
        if target.exists():
            skipped.append(name)
            continue
        target.write_text(scaffold.joinpath(name).read_text(encoding="utf-8"), encoding="utf-8")
        written.append(name)
    if written:
        print(f"Created {', '.join(written)} in {dest.resolve()}")
    if skipped:
        print(f"Skipped (already present): {', '.join(skipped)}")
    print("Next: concept-map build map.md")
