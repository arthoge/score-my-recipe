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


@pytest.mark.parametrize(
    "query,code",
    [
        ("lentilles", "20359"),
        ("huile d’olive", "17270"),
        ("pomme", "13396"),
    ],
)
def test_short_names_prefer_generic_food_over_dishes_and_processed_variants(query, code):
    """Common plural and punctuated names resolve to the ingredient's own catalog row."""
    assert ciqual.search_foods(query, 1)[0]["code"] == code


def test_fuzzy_search_does_not_match_only_a_shared_adjective():
    """Fresh cream cannot become fresh mint because both names contain 'fraîche'."""
    assert ciqual._match_rank("creme fraiche", "menthe, fraiche") == 0
    assert all(food["code"] != "11027" for food in ciqual.search_foods("crème fraîche"))
