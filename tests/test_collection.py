import ast
from pathlib import Path


def test_legacy_demos_guard_execution():
    for path in Path("examples").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert any(isinstance(node, ast.If) for node in tree.body), path.name
        for node in tree.body:
            if isinstance(node, ast.Assign):
                assert not isinstance(node.value, ast.Call), path.name
