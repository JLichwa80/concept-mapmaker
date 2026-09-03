import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from concept_mapmaker.builder import SCAFFOLD_FILES, build_map, find_spec, parse, run_init


class BuilderTests(unittest.TestCase):
    def test_bullet_becomes_concept_with_description(self):
        markdown = """# Demo

## Branch

- **Concept**: Description
"""
        root, descriptions = parse(markdown)
        concept = root["children"][0]["children"][0]
        self.assertEqual(concept["label"], "Concept")
        self.assertEqual(descriptions[concept["id"]], "Description")

    def test_star_token_marks_node(self):
        root, _ = parse("# Demo\n\n## Branch\n\n- **Concept** -*-: Description\n")
        concept = root["children"][0]["children"][0]
        self.assertTrue(concept["mark"])

    @patch("concept_mapmaker.builder.render_pdf")
    def test_build_uses_packaged_template_and_project_output(self, render_pdf):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.md"
            source.write_text("# Sample\n\n## Topic\n\nA description.\n", encoding="utf-8")
            build_map(source, {"page_title": "Browser title"}, project_root=root)

            html = (root / "web" / "sample.html").read_text(encoding="utf-8")
            self.assertIn("<title>Browser title</title>", html)
            self.assertNotRegex(html, r"__[A-Z][A-Z0-9_]*__")
            self.assertTrue((root / "web" / "downloads" / "sample.md").is_file())
            render_pdf.assert_called_once()

    def test_find_spec_discovers_config_beside_doc(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            doc = root / "sample.md"
            doc.write_text("# Sample\n", encoding="utf-8")
            self.assertIsNone(find_spec(doc, root))

            config = root / "config.yaml"
            config.write_text("title: Sample\n", encoding="utf-8")
            self.assertEqual(find_spec(doc, root), config)

    def test_run_init_writes_then_skips_scaffold(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "project"
            run_init(dest)
            for name in SCAFFOLD_FILES:
                self.assertTrue((dest / name).is_file(), name)

            sentinel = "# edited by hand\n"
            (dest / "map.md").write_text(sentinel, encoding="utf-8")
            run_init(dest)
            self.assertEqual((dest / "map.md").read_text(encoding="utf-8"), sentinel)


if __name__ == "__main__":
    unittest.main()

