"""Testy parsera atlas-roslin w ``scripts/build_plants_bs4.py`` (bez sieci)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_build_plants():
    root = Path(__file__).resolve().parents[1]
    scripts = str(root / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    path = root / "scripts" / "build_plants_bs4.py"
    spec = importlib.util.spec_from_file_location("build_plants_bs4", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_atlas_skorowidz_extracts_polish_common_name():
    mod = _load_build_plants()
    html = (
        '<html><body>'
        '<a href="/gatunki/Abelia_chinensis.htm">'
        "— ✦ Abelia chinensis R.Br. - abelia chińska"
        "</a>"
        "</body></html>"
    )
    names = mod.names_from_atlas_skorowidz_html(html)
    assert "abelia chińska" in names
    assert "abelia chinensis r br" not in names


def test_atlas_skips_latin_only_segment():
    mod = _load_build_plants()
    html = (
        '<html><body>'
        '<a href="/gatunki/Urtica_dioica.htm">'
        "— ** Urtica dioica L. - pokrzywa zwyczajna"
        "</a>"
        "</body></html>"
    )
    names = mod.names_from_atlas_skorowidz_html(html)
    assert "pokrzywa zwyczajna" in names


def test_atlas_skips_arrow_synonym_lines():
    mod = _load_build_plants()
    html = (
        '<html><body>'
        '<a href="/gatunki/x.htm">stare ⟶ nowe - coś polskiego</a>'
        "</body></html>"
    )
    assert not mod.names_from_atlas_skorowidz_html(html)


def test_atlas_ignores_non_gatunki_links():
    mod = _load_build_plants()
    html = '<html><body><a href="/cookies.htm">ciasteczka</a></body></html>'
    assert not mod.names_from_atlas_skorowidz_html(html)


def test_atlas_skips_meta_tokens():
    mod = _load_build_plants()
    html = '<html><body><a href="/gatunki/x.htm">coś - mszaków</a></body></html>'
    assert "mszaków" not in mod.names_from_atlas_skorowidz_html(html)
