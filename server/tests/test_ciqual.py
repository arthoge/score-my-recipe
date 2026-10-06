"""Validate official CIQUAL identities and independent bilingual search."""

import pytest
from api import ciqual


def test_bundled_catalog_and_search():
    """The standalone release includes foods beyond Agribalyse and prefers the ingredient itself."""
    assert len(ciqual.get_foods()) == 3484
    food = ciqual.search_foods("tomato", 1)[0]
    assert food["code"] == "20385"
    assert ciqual.food_name(food, "en").startswith("Tomato,")
    assert ciqual.food_name(food, "fr").startswith("Tomate ")
    assert ciqual.search_foods("   ") == []
    assert ciqual.search_foods("xxxzzzzz") == []
    assert ciqual.search_foods("ÉPINARD", 1)[0]["name_fr"].startswith("Épinard")


def test_parse_official_xml():
    """Preserve identities while removing source whitespace, even without an English name."""
    assert ciqual.parse_foods(
        b"<TABLE><ALIM><alim_code> 12 </alim_code><alim_nom_fr> Pomme </alim_nom_fr></ALIM></TABLE>"
    ) == [{"code": "12", "name_fr": "Pomme", "name_en": ""}]


@pytest.mark.parametrize(
    "xml",
    [
        b"<TABLE/>",
        b"<TABLE><ALIM><alim_nom_fr>Pomme</alim_nom_fr></ALIM></TABLE>",
        b"<TABLE><ALIM><alim_code>12</alim_code></ALIM></TABLE>",
        b"<TABLE>"
        + b"<ALIM><alim_code>12</alim_code><alim_nom_fr>Pomme</alim_nom_fr></ALIM>" * 2
        + b"</TABLE>",
    ],
)
def test_invalid_catalog(xml):
    """Reject missing identities and duplicate codes instead of quietly creating false matches."""
    with pytest.raises(ValueError):
        ciqual.parse_foods(xml)


def test_pinned_release_checksum(tmp_path):
    """Do not replace the trusted catalog with an unexpected external payload."""
    target = tmp_path / "foods.json"
    with pytest.raises(ValueError, match="checksum"):
        ciqual.write_catalog(b"<TABLE/>", target)
    assert not target.exists()
