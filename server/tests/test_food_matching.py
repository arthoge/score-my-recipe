"""Real catalogue regressions for French ingredients and conservative automatic matching."""

from unittest.mock import AsyncMock
import pytest
from api import food_matching, references, ciqual


@pytest.mark.parametrize(
    "name,ciqual_code,agribalyse_code",
    [
        ("noix de saint jacques", "10045", "10045"),
        ("noix de Saint-Jacques", "10045", "10045"),
        ("crème fraîche", "19410", "19410"),
        ("creme fraiche", "19410", "19410"),
        ("truffe", "20106", None),
        ("chair de homard", "10010", None),
        ("bouillon de crustacés", None, None),
    ],
)
@pytest.mark.asyncio
async def test_french_recipe_names_resolve_real_primary_foods(
    monkeypatch, name, ciqual_code, agribalyse_code
):
    """Recipe wording must resolve the ingredient, never a dish that contains it."""
    taxonomy = AsyncMock(side_effect=OSError("offline"))
    monkeypatch.setattr(references.off, "get_ingredients_taxonomy", taxonomy)
    result = await references.resolve_ingredient_references(query=name, lang="fr")
    assert (result.ciqual.code if result.ciqual else None) == ciqual_code
    assert (result.agribalyse.code if result.agribalyse else None) == agribalyse_code
    if ciqual_code:
        taxonomy.assert_not_awaited()
    if not agribalyse_code:
        assert result.source == "unmatched"


@pytest.mark.parametrize(
    "query,name",
    [
        ("noix de saint jacques", "Pizza aux fruits de mer"),
        ("truffe", "Boudin blanc truffé, cru"),
        ("truffe", "Truffes fantaisie"),
        ("homard, cru", "Homard, bouilli/cuit à l'eau"),
        ("pomme, crue", "Pomme, sèche"),
        ("crème fraîche", "Crème 15 à 20% MG, légère, semi-épaisse, UHT"),
        ("bouillon de crustacés", "Soupe de poissons et/ou crustacés"),
        ("tomate", "Pizza à la tomate"),
        ("huile d'olive", "Huile de lin"),
    ],
)
def test_automatic_matches_reject_dishes_and_changed_food_variants(query, name):
    """Coverage cannot be increased by changing food identity, preparation or fat content."""
    assert food_matching.automatic_rank(query, name) == 0


@pytest.mark.parametrize("name", ["pomme", "lait", "beurre", "lentilles", "huile d’olive"])
def test_common_ingredients_keep_plausible_correspondences(name):
    """New culinary matching must not regress ordinary ingredients in other recipes."""
    result = references._local_references("fr", name)
    assert result.ciqual and result.agribalyse
    assert not any(word in result.agribalyse.name.lower() for word in ["pizza", "cacao", "chèvre"])
    if name == "pomme":
        assert "crue" in result.agribalyse.name
    if name == "lentilles":
        assert "sèche" in result.agribalyse.name


@pytest.mark.asyncio
async def test_precise_local_foods_override_broad_taxonomy_proxies(monkeypatch):
    """An inherited seafood pizza mapping cannot outrank available scallop records."""
    proxy = AsyncMock(
        return_value=references.IngredientReferencesResponse(
            agribalyse=references.FoodReference(code="pizza", name="Pizza aux fruits de mer")
        )
    )
    monkeypatch.setattr(references, "ingredient_references", proxy)
    result = await references.resolve_ingredient_references(
        "en:scallop", "fr", "noix de saint jacques"
    )
    assert result.agribalyse.code == "10045"
    proxy.assert_not_awaited()


def test_cooked_lobster_remains_available_for_manual_selection():
    """A chef can choose the cooked reference explicitly; automatic raw matching remains conservative."""
    assert references.search_foods("chair de homard", 8).foods[0].code == "10009"
    assert ciqual.search_foods("chair de homard", 1)[0]["code"] == "10010"


def test_reordered_preparation_and_catalog_synonyms():
    """Preparation words and catalog alternative spellings do not hide a food identity."""
    from api import references

    for query in ("oignons", "emmental râpé", "grated emmental"):
        result = references._local_references("fr", query)
        assert result.ciqual is not None
        assert result.agribalyse is not None


@pytest.mark.parametrize("name", ["fresh cream", "fresh creme", "crème fraîche"])
def test_fresh_cream_prefers_refrigerated_generic_reference(name):
    """Freshness should outrank an unsupported regional designation in either language."""
    result = references._local_references("en", name)
    assert result.ciqual.code == "19410"
    assert result.agribalyse.code == "19410"


def test_onions_never_match_fish_with_onion_sauce():
    """A classifier must not turn a secondary sauce ingredient into the food identity."""
    dish = "Poisson blanc à la marinière (sauce aux oignons, vin blanc, moules)"
    assert food_matching.automatic_rank("oignons", dish) == 0
    result = references._local_references("fr", "oignons")
    assert result.agribalyse.code == "20034"


@pytest.mark.asyncio
async def test_white_onions_use_generic_taxonomy_reference(monkeypatch):
    """An unprepared subtype must not stop at a cooked catalog entry with no environmental link."""
    from tests.helpers import create_taxonomy, create_taxonomy_node

    parent = create_taxonomy_node(
        "en:onion", names={"fr": "oignon"}, properties={"ciqual_food_code": {"en": "20034"}}
    )
    child = create_taxonomy_node("en:white-onion", names={"fr": "oignons blancs"})
    child.add_parents([parent])
    taxonomy = create_taxonomy({parent.id: parent, child.id: child})
    monkeypatch.setattr(
        references.off, "get_ingredients_taxonomy", AsyncMock(return_value=taxonomy)
    )
    result = await references.resolve_ingredient_references(query="oignons blancs", lang="fr")
    assert result.ciqual.code == "20034"
    assert result.agribalyse.code == "20034"


@pytest.mark.parametrize(
    "query,name",
    [
        ("oignons blancs", "Oignon blanc ou jaune, sauté/poêlé sans matière grasse"),
        ("white onion", "White onion, fried"),
        ("carrot", "Carrot, roasted"),
    ],
)
def test_unspecified_preparation_does_not_invent_cooking(query, name):
    """Cooking changes composition; a matching variety name is not enough to assume it."""
    assert food_matching.automatic_rank(query, name) == 0


def test_flavoured_oil_is_not_silently_replaced_by_plain_oil():
    """Preserve meaningful additions when no matching generic catalog food exists."""
    result = references._local_references("fr", "huile d’olive à la truffe")
    assert result.ciqual is None
    assert result.agribalyse is None


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Beurre allégé 60%", True),
        ("Beurre 62%", True),
        ("Beurre 82%", False),
        ("Beurre 40%", False),
    ],
)
def test_catalog_fat_range_accepts_a_product_within_the_range(name, expected):
    """Catalog interval endpoints describe a range, not two mandatory label numbers."""
    assert (
        bool(
            food_matching.automatic_rank(
                "Beurre à 60-62% MG, à teneur réduite en matière grasse, doux", name
            )
        )
        is expected
    )


def test_uht_request_rejects_explicit_fresh_variant():
    """Declared processing conflicts are rejected in both directions."""
    assert food_matching.automatic_rank("Crème 30% MG, UHT", "Crème fraîche 30%") == 0
