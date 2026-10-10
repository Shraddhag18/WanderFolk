import ast
import re
import unittest
from pathlib import Path


def load_parse_names():
    source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text()
    module = ast.parse(source, filename="app.py")
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "parse_names"
    )
    namespace = {"re": re}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["parse_names"]


parse_names = load_parse_names()


class ParseNames(unittest.TestCase):
    def test_splits_mixed_delimiters_and_discards_empty_values(self):
        self.assertEqual(parse_names("  Priya,,\n, Arjun\n\n"), ["Priya", "Arjun"])
        self.assertEqual(parse_names("\n, ,\n"), [])

    def test_preserves_first_unicode_spelling_while_deduplicating_case_insensitively(self):
        self.assertEqual(parse_names("Élodie, éLODIE\n李雷, 李雷"), ["Élodie", "李雷"])

    def test_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            parse_names(None)


if __name__ == "__main__":
    unittest.main()
