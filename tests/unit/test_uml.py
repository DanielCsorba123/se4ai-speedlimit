"""The UML code diagrams in docs/10-uml.md must name things that exist in the code (Task 12, step 3)."""
import dataclasses
import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UML = ROOT / "docs" / "10-uml.md"
TYPE_MODULES = ["speedlimit.domain", "speedlimit.model", "speedlimit.decide", "speedlimit.drift",
                "speedlimit.cleaning", "speedlimit.air_quality"]


def _blocks(diagram_id: str):
    text = UML.read_text(encoding="utf-8")
    section = text.split(f"<!-- {diagram_id} -->", 1)[1].split("```", 2)[1]
    for name, body in re.findall(r"class (\w+)\s*\{(.*?)\}", section, flags=re.S):
        yield name, body


def _resolve_type(name):
    for mod in TYPE_MODULES:
        m = importlib.import_module(mod)
        if hasattr(m, name):
            return getattr(m, name)
    raise AssertionError(f"type {name} not found in {TYPE_MODULES}")


def test_uml_document_has_all_diagrams():
    text = UML.read_text(encoding="utf-8")
    for d in ("U01", "U02", "U03", "U04", "U05", "U06"):
        assert f"<!-- {d} -->" in text, d
    assert text.count("```mermaid") >= 6


@pytest.mark.parametrize("name_body", list(_blocks("U03")), ids=lambda nb: nb[0])
def test_u03_type_fields_exist(name_body):
    name, body = name_body
    cls = _resolve_type(name)
    fields = {f.name for f in dataclasses.fields(cls)}
    listed = re.findall(r"^\s*\+(\w+)\s*:", body, flags=re.M)
    assert listed, f"{name}: no fields listed"
    assert set(listed) <= fields, f"{name}: unknown fields {set(listed) - fields}"


@pytest.mark.parametrize("name_body", list(_blocks("U02M")), ids=lambda nb: nb[0])
def test_u02_module_functions_exist(name_body):
    name, body = name_body
    mod = importlib.import_module(f"speedlimit.{name}")
    funcs = re.findall(r"^\s*\+(\w+)\(", body, flags=re.M)
    assert funcs, f"{name}: no functions listed"
    missing = [f for f in funcs if not callable(getattr(mod, f, None))]
    assert not missing, f"speedlimit.{name} lacks {missing}"
