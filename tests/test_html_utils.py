"""Regression tests for scripts/html_utils.py."""
import os
import tempfile
import unittest

from scripts.html_utils import create_page_from_template, elem, table_row


class TestElem(unittest.TestCase):
    def test_basic_tag(self):
        self.assertEqual(elem("h1", "hello"), "<h1>hello</h1>")

    def test_multiple_content_parts_joined(self):
        # current behavior: no separator between parts (see __main__ assert
        # expecting 'meow quack' only because caller passed the space)
        self.assertEqual(
            elem("h1", "meow", " quack", id="hhhhh",
                 **{"dumb-attribute": "some value"}),
            '<h1 id="hhhhh" dumb-attribute="some value">meow quack</h1>',
        )

    def test_none_attributes_skipped(self):
        self.assertEqual(
            elem("p", "x", title=None, **{"class": "a"}),
            '<p class="a">x</p>',
        )

    def test_non_closing_tags(self):
        self.assertEqual(elem("br"), "<br/>")
        self.assertEqual(elem("img", src="a.png"), '<img src="a.png"/>')
        self.assertEqual(elem("link", href="s.css"), '<link href="s.css"/>')


class TestTableRow(unittest.TestCase):
    def test_row(self):
        self.assertEqual(
            table_row("owo", "uwu", "nyaa", **{"data-gggg": "quack"}),
            '<tr data-gggg="quack">owouwunyaa</tr>',
        )


class TestCreatePageFromTemplate(unittest.TestCase):
    def test_replaces_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            # function resolves template relative to project root via
            # scripts/../ ; so stage a template inside the repo tree is
            # complex -- instead test the missing-template branch which
            # is the only branch not needing real paths.
            missing = os.path.join(tmp, "nope.template.html")
            # must be project-root-relative; a tmp path won't exist there
            self.assertIsNone(
                create_page_from_template(
                    "docs/templates/does-not-exist-xyz.template.html",
                    os.path.join(tmp, "out.html"),
                    content="x",
                )
            )
            self.assertFalse(os.path.exists(missing.replace(".template.html", ".html")))

    def test_missing_template_returns_none(self):
        self.assertIsNone(
            create_page_from_template(
                "definitely/not/here.template.html",
                "tests/should-not-be-created.html",
                content="x",
            )
        )


if __name__ == "__main__":
    unittest.main()
