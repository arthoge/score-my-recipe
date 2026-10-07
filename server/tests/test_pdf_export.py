"""Printable export contracts: server scores, partial data, layout and input bounds."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import nutrition, pdf_export, types
from api.api import app


def report_flowables(story):
    """Flatten recipe containers when inspecting their existing layout details."""
    return [
        flow
        for block in story
        for flow in (block._content if isinstance(block, pdf_export.KeepTogether) else [block])
    ]


def recipe(**changes):
    """A bounded export recipe with a single canonical ingredient."""
    return pdf_export.ExportRecipe.model_validate(
        {
            "name": "Rice bowl",
            "portions": 2,
            "country": "FR",
            "ingredients": [
                {"id": "rice", "name": "Rice", "quantity_g": 100, "ciqual_code": "9119"}
            ],
            **changes,
        }
    )


@pytest.mark.asyncio
async def test_scores_are_calculated_from_current_inputs(monkeypatch):
    """Both algorithms receive the same quantity; selected country and portions survive export."""
    green = AsyncMock(return_value=types.GreenScoreResponse(numeric_score=90, letter_grade="A"))
    nutritional = AsyncMock(return_value=nutrition.NutritionResponse(status="incomplete"))
    monkeypatch.setattr(pdf_export.score, "compute_green_score", green)
    monkeypatch.setattr(pdf_export.nutrition, "analyze", nutritional)
    report = await pdf_export.calculate_report(recipe())
    assert report[1].numeric_score == 90
    assert green.call_args.args[0][0].weight == 100
    assert green.call_args.kwargs["country"] == "FR"
    assert nutritional.call_args.args[0].ingredients[0].quantity_g == 100
    assert nutritional.call_args.args[0].portions == 2
    with pytest.raises(ValidationError):
        recipe(nutri_score={"score": -10}, green_score=100)


@pytest.mark.asyncio
async def test_one_failed_score_preserves_the_other(monkeypatch):
    """An upstream failure must not invent a grade or drop the independent result."""
    monkeypatch.setattr(
        pdf_export.score, "compute_green_score", AsyncMock(side_effect=OSError("offline"))
    )
    monkeypatch.setattr(
        pdf_export.nutrition,
        "analyze",
        AsyncMock(return_value=nutrition.NutritionResponse(status="incomplete")),
    )
    report = await pdf_export.calculate_report(recipe())
    assert report[1] is None
    assert report[2].status == "incomplete"


def test_prepared_mass_excludes_zero_quantity():
    """Measured positive weights override estimates; zero quantity contributes no mass."""
    item = recipe(
        ingredients=[
            {"id": "a", "name": "Rice", "quantity_g": 100, "prepared_weight_g": 250},
            {"id": "b", "name": "Unused", "quantity_g": 0, "prepared_weight_g": 500},
            {"id": "c", "name": "Unknown", "quantity_g": None},
        ]
    )
    assert pdf_export.prepared_mass(item) == 250


def test_pdf_content_pagination_and_escaped_names(monkeypatch):
    """Long reports render across pages; user markup is printed literally and unknowns stay unknown."""
    original = pdf_export.SimpleDocTemplate
    monkeypatch.setattr(pdf_export, "StandardEncryption", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        pdf_export,
        "SimpleDocTemplate",
        lambda *args, **kwargs: original(*args, **kwargs, pageCompression=0),
    )
    item = recipe(
        name="Soup <b> & rice",
        ingredients=[
            {"id": str(i), "name": f"Ingredient {i}", "quantity_g": 100} for i in range(100)
        ],
    )
    pdf = pdf_export.render_pdf([(item, None, None)] * 3)
    assert pdf.startswith(b"%PDF-")
    assert pdf.count(b"/Type /Page\n") >= 2
    assert b"(Soup <)" in pdf and b"(> & rice)" in pdf
    assert b"No information available" in pdf
    assert b"Score unavailable" not in pdf
    assert b"Per portion" in pdf
    assert b"%%EOF" in pdf


def test_print_enabled_and_editing_restricted():
    """A normal download is encrypted with an empty opening password and owner restrictions."""
    pdf = pdf_export.render_pdf([(recipe(), None, None)])
    assert b"/Encrypt" in pdf
    assert b"/P -60" in pdf


@pytest.mark.parametrize(
    "changes",
    [
        {"portions": 0},
        {"country": "France"},
        {"ingredients": []},
        {"ingredients": [{"id": "a", "quantity_g": -1}]},
        {"ingredients": [{"id": "a", "quantity_g": 100}, {"id": "a", "quantity_g": 200}]},
    ],
)
def test_invalid_export_inputs(changes):
    """Reject invalid masses, portions and ambiguous ingredient identifiers before computation."""
    with pytest.raises(ValidationError):
        recipe(**changes)


def test_binary_download_contract(monkeypatch):
    """The browser receives a PDF attachment and invalid empty selections get a validation response."""
    export = AsyncMock(return_value=b"%PDF-1.4\n%%EOF")
    monkeypatch.setattr(pdf_export, "export_pdf", export)
    client = TestClient(app)
    response = client.post("/v1/recipes/export", json={"recipes": [recipe().model_dump()]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "recipes.pdf" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"%PDF-")
    assert client.post("/v1/recipes/export", json={"recipes": []}).status_code == 422


def test_compact_report_layout(monkeypatch):
    """Keep ingredient names compact, score illustrations uncaptioned, and caveats below titles."""
    from types import SimpleNamespace

    from reportlab.platypus import Paragraph, Spacer, Table

    captured = []

    def capture_story(self, story, **kwargs):
        """Inspect the printable flow before ReportLab consumes it."""
        captured.extend(report_flowables(story))

    monkeypatch.setattr(pdf_export.SimpleDocTemplate, "build", capture_story)
    item = recipe(
        ingredients=[
            {"id": "rice", "name": "Rice", "quantity_g": 100},
            {"id": "salt", "name": "Salt", "quantity_g": None},
        ]
    )
    nutritional = SimpleNamespace(
        nutri_score=SimpleNamespace(grade="a", score=-2),
        excluded_ingredients=[],
        nutrients_per_100g={},
        nutrients_per_portion={},
        additives=[],
        allergens=[],
    )
    green = types.GreenScoreResponse(numeric_score=90, letter_grade="A")
    pdf_export.render_pdf([(item, green, nutritional)])
    intro = [flow for flow in captured if isinstance(flow, Paragraph)][:3]
    assert [flow.getPlainText() for flow in intro] == [
        "Rice bowl",
        "Based on available ingredient and product data. Information may be missing or inaccurate.",
        "Ingredients: Rice, Salt",
    ]
    tables = [flow for flow in captured if isinstance(flow, Table)]
    for box in tables[0]._cellvalues[0]:
        assert box.width > 0
        assert box.height == pytest.approx(pdf_export.SCORE_ILLUSTRATION_HEIGHT)
        assert not isinstance(box, Paragraph)
    assert len(tables[0]._cellvalues) == 1
    assert tables[0]._cellStyles[0][0].leftPadding == 0
    assert tables[0]._cellStyles[0][0].alignment == "LEFT"
    assert isinstance(captured[1], Spacer)
    assert captured[1].height == 12
    assert isinstance(captured[-1], Spacer)
    assert captured[-1].height == 20
    nutrition_index = captured.index(tables[1])
    assert isinstance(captured[nutrition_index + 1], Spacer)
    assert captured[nutrition_index + 1].height == 8
    assert captured[nutrition_index + 2].getPlainText().startswith("Additives:")
    # Only the labels use the heavier font; lists retain the paragraph's regular font.
    for paragraph, label in (
        (intro[2], "Ingredients:"),
        (captured[nutrition_index + 2], "Additives:"),
        (captured[nutrition_index + 3], "Allergens:"),
    ):
        assert paragraph.frags[0].text == label
        assert paragraph.frags[0].fontName == "RecipeSansBold"
        assert all(fragment.fontName == "RecipeSans" for fragment in paragraph.frags[1:])
    assert not any(
        isinstance(flow, Paragraph) and flow.getPlainText() == "Recipes" for flow in captured
    )


@pytest.mark.parametrize("available", ["neither", "green", "nutri"])
def test_missing_score_boxes_are_omitted(monkeypatch, available):
    """Omit unavailable scores and put the sole available illustration in the left column."""
    from types import SimpleNamespace
    from reportlab.platypus import Table, Paragraph

    captured = []

    def capture_story(self, story, **kwargs):
        """Capture score cells without needing to decode encrypted PDF content."""
        captured.extend(report_flowables(story))

    monkeypatch.setattr(pdf_export.SimpleDocTemplate, "build", capture_story)
    green = (
        types.GreenScoreResponse(numeric_score=90, letter_grade="A")
        if available == "green"
        else None
    )
    nutritional = (
        SimpleNamespace(
            nutri_score=SimpleNamespace(grade="a", score=-2),
            excluded_ingredients=[],
            nutrients_per_100g={},
            nutrients_per_portion={},
            additives=[],
            allergens=[],
        )
        if available == "nutri"
        else None
    )
    pdf_export.render_pdf([(recipe(), green, nutritional)])
    tables = [flow for flow in captured if isinstance(flow, Table)]
    assert len(tables) == (1 if available == "neither" else 2)
    if available != "neither":
        assert len(tables[0]._cellvalues[0]) == 1
        box = tables[0]._cellvalues[0][0]
        assert len(tables[0]._cellvalues) == 1
        assert not isinstance(box, Paragraph)
        assert tables[0].hAlign == "LEFT"
        assert tables[0]._cellStyles[0][0].leftPadding == 0
        assert tables[0]._cellStyles[0][0].alignment == "LEFT"


@pytest.mark.parametrize(
    "green_excluded,nutri_excluded", [(True, True), (True, False), (False, True)]
)
@pytest.mark.parametrize("grade", ["a", "b", "c", "d", "e"])
def test_score_illustrations_and_exclusion_subtitles_align(
    monkeypatch, green_excluded, nutri_excluded, grade
):
    """Different logo proportions and missing subtitles must not shift either shared row."""
    from types import SimpleNamespace

    from reportlab.platypus import Table

    captured = []

    def capture_story(self, story, **kwargs):
        """Capture and lay out score cells using ReportLab's actual row sizing."""
        captured.extend(report_flowables(story))

    monkeypatch.setattr(pdf_export.SimpleDocTemplate, "build", capture_story)
    green = types.GreenScoreResponse(
        numeric_score=90,
        letter_grade="A",
        missing_ingredient_ids=["rice"] if green_excluded else [],
    )
    nutritional = SimpleNamespace(
        nutri_score=SimpleNamespace(grade=grade),
        excluded_ingredients=["rice"] if nutri_excluded else [],
        excluded_weight_percent=100,
        nutrients_per_100g={},
        nutrients_per_portion={},
        additives=[],
        allergens=[],
    )
    pdf_export.render_pdf([(recipe(), green, nutritional)])
    scores = next(flow for flow in captured if isinstance(flow, Table))
    scores.wrap(600, 800)
    illustrations, subtitles = scores._cellvalues
    assert illustrations[0][0].height == pytest.approx(illustrations[1][0].height)
    assert len(subtitles) == 2
    for index, excluded in enumerate((green_excluded, nutri_excluded)):
        assert scores._cellStyles[1][index].valign == "TOP"
        assert scores._cellStyles[1][index].topPadding == 3
        if excluded:
            assert subtitles[index][0].getPlainText() == (
                "1 ingredient(s) excluded (100% of recipe weight)."
            )
        else:
            assert subtitles[index] == ""


def record_pdf_paragraph_pages(monkeypatch):
    """Record actual paragraph page numbers as ReportLab draws the document."""
    pages = []
    original = pdf_export.Paragraph.draw

    def draw(paragraph):
        """Keep the real rendering while recording its page placement."""
        pages.append((paragraph.getPlainText(), paragraph.canv.getPageNumber()))
        return original(paragraph)

    monkeypatch.setattr(pdf_export.Paragraph, "draw", draw)
    return pages


def test_recipes_that_fit_a_page_are_not_cut(monkeypatch):
    """Compact recipes share pages, but each recipe's title and final content stay together."""
    from types import SimpleNamespace

    pages = record_pdf_paragraph_pages(monkeypatch)
    reports = [
        (
            recipe(name=f"Recipe {i}"),
            None,
            SimpleNamespace(
                nutri_score=None,
                nutrients_per_100g={},
                nutrients_per_portion={},
                additives=[],
                allergens=[f"en:recipe-{i}"],
            ),
        )
        for i in range(5)
    ]
    pdf_export.render_pdf(reports)
    for i in range(5):
        title_page = next(page for text, page in pages if text == f"Recipe {i}")
        last_page = next(page for text, page in pages if text == f"Allergens: Recipe {i}")
        assert title_page == last_page
    title_pages = [page for text, page in pages if text.startswith("Recipe ")]
    assert len(set(title_pages)) > 1
    assert len(set(title_pages)) < 5


def test_oversized_recipe_starts_fresh_then_spans_pages(monkeypatch):
    """A recipe taller than a page moves off the previous recipe's page before splitting."""
    pages = record_pdf_paragraph_pages(monkeypatch)
    large = recipe(
        name="Oversized recipe",
        ingredients=[
            {"id": str(i), "name": ("Long ingredient description " * 5) + str(i), "quantity_g": 100}
            for i in range(100)
        ],
    )
    pdf_export.render_pdf([(recipe(name="Small recipe"), None, None), (large, None, None)])
    assert next(page for text, page in pages if text == "Small recipe") == 1
    assert next(page for text, page in pages if text == "Oversized recipe") == 2
    assert max(page for text, page in pages if text.startswith("Allergens:")) > 2


@pytest.mark.parametrize(
    "filename", ["green-score-a.svg", "nutri-score-a.svg", "nutri-score-e.svg"]
)
def test_score_illustrations_scale_by_height(filename):
    """Different logo proportions share the target height without a width constraint."""
    original = pdf_export.svg2rlg(str(pdf_export.ASSETS / filename))
    drawing = pdf_export.illustration(filename, height=36)
    assert drawing.height == pytest.approx(36)
    assert drawing.width / drawing.height == pytest.approx(original.width / original.height)


@pytest.mark.parametrize(
    "labels,expected",
    [
        ([], "Ingredients: Rice, Salt"),
        (["Organic"], "Ingredients: Rice (Organic), Salt"),
        (["Organic", "Fair trade"], "Ingredients: Rice (Organic, Fair trade), Salt"),
        (["Bio <b> & local"], "Ingredients: Rice (Bio <b> & local), Salt"),
        (["  ", " Organic "], "Ingredients: Rice (Organic), Salt"),
    ],
)
def test_ingredient_labels_in_printed_list(monkeypatch, labels, expected):
    """Print each ingredient's labels without changing unlabelled ingredients or interpreting markup."""
    captured = []

    def capture_story(self, story, **kwargs):
        """Inspect the rendered ingredient paragraph and its escaped text."""
        captured.extend(report_flowables(story))

    monkeypatch.setattr(pdf_export.SimpleDocTemplate, "build", capture_story)
    item = recipe(
        ingredients=[
            {
                "id": "rice",
                "name": "Rice",
                "quantity_g": 100,
                "labels": [{"id": None, "label": label, "isInTaxonomy": False} for label in labels],
            },
            {"id": "salt", "name": "Salt", "quantity_g": 1},
        ]
    )
    pdf_export.render_pdf([(item, None, None)])
    paragraph = next(
        flow
        for flow in captured
        if isinstance(flow, pdf_export.Paragraph) and flow.getPlainText().startswith("Ingredients:")
    )
    assert paragraph.getPlainText() == expected
    assert all(fragment.fontName == "RecipeSans" for fragment in paragraph.frags[1:])
