"""Compact, server-calculated recipe reports for A4 printing."""

import asyncio
import logging
import secrets
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, Field, model_validator
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from svglib.svglib import svg2rlg

from api import nutrition, preparation, score, types

logger = logging.getLogger(__name__)
ASSETS = Path(__file__).parent / "resources" / "pdf"
SCORE_ILLUSTRATION_HEIGHT = 36
pdfmetrics.registerFont(TTFont("RecipeSans", str(ASSETS / "LiberationSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("RecipeSansBold", str(ASSETS / "LiberationSans-Bold.ttf")))
pdfmetrics.registerFontFamily("RecipeSans", normal="RecipeSans", bold="RecipeSansBold")


class ExportIngredient(nutrition.NutritionIngredient):
    """One canonical ingredient input for both score calculations and the printed list."""

    codified_ingredient: types.TaxonomyItem | None = None
    agribalyse_code: str | None = None
    labels: list[types.TaxonomyItem] = Field(default_factory=list)
    origin: types.TaxonomyItem | None = None
    is_fresh_plant: bool = False
    is_in_season: bool = False


class ExportRecipe(nutrition.NutritionRequest):
    """Recipe inputs only; browser-supplied scores are rejected."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    ingredients: list[ExportIngredient] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ingredients(self):
        """Keep exclusion counts and reference matching unambiguous."""
        if len({row.id for row in self.ingredients}) != len(self.ingredients):
            raise ValueError("Ingredient IDs must be unique within each recipe")
        return self


class ReportTranslations(BaseModel):
    """Bounded presentation text from the website locale; API clients default to English."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Recipes", min_length=1, max_length=500)
    subtitle: str = Field(
        default="Based on available ingredient and product data. Information may be missing or inaccurate.",
        min_length=1,
        max_length=500,
    )
    ingredients: str = Field(default="Ingredients", min_length=1, max_length=500)
    unnamed_ingredient: str = Field(default="Unnamed ingredient", min_length=1, max_length=500)
    exclusions: str = Field(
        default="{count} ingredient(s) excluded ({percent}% of recipe weight).",
        min_length=1,
        max_length=500,
    )
    nutrition: str = Field(default="Nutrition", min_length=1, max_length=500)
    per_100g: str = Field(default="Per 100 g", min_length=1, max_length=500)
    per_portion: str = Field(default="Per portion", min_length=1, max_length=500)
    additives: str = Field(default="Additives", min_length=1, max_length=500)
    allergens: str = Field(default="Allergens", min_length=1, max_length=500)
    no_information: str = Field(default="No information available", min_length=1, max_length=500)
    energy_kj: str = Field(default="Energy", min_length=1, max_length=500)
    fat: str = Field(default="Fat", min_length=1, max_length=500)
    saturated_fat: str = Field(default="Saturated fat", min_length=1, max_length=500)
    carbohydrates: str = Field(default="Carbohydrates", min_length=1, max_length=500)
    sugars: str = Field(default="Sugars", min_length=1, max_length=500)
    fiber: str = Field(default="Fibre", min_length=1, max_length=500)
    proteins: str = Field(default="Proteins", min_length=1, max_length=500)
    salt: str = Field(default="Salt", min_length=1, max_length=500)


class ExportRequest(BaseModel):
    """A bounded selection of recipe drafts to export together."""

    recipes: list[ExportRecipe] = Field(min_length=1, max_length=20)
    translations: ReportTranslations = Field(default_factory=ReportTranslations)


async def calculate_report(recipe: ExportRecipe):
    """Run the existing score algorithms independently, preserving available results."""
    green_inputs = [
        types.RecipeIngredientInput(
            id=row.id,
            name=row.name,
            weight=row.quantity_g or 0,
            codified_ingredient=row.codified_ingredient
            or types.TaxonomyItem(id=row.name, label=row.name, is_in_taxonomy=False),
            agribalyse_code=row.agribalyse_code,
            labels=row.labels,
            origin=row.origin,
            is_fresh_plant=row.is_fresh_plant,
            is_in_season=row.is_in_season,
        )
        for row in recipe.ingredients
    ]
    results = await asyncio.gather(
        score.compute_green_score(green_inputs, country=recipe.country),
        nutrition.analyze(
            nutrition.NutritionRequest(
                ingredients=recipe.ingredients, portions=recipe.portions, category=recipe.category
            )
        ),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, Exception):
            raise result
        if isinstance(result, Exception):
            logger.warning("Recipe export calculation unavailable: %s", result)
    return recipe, *(None if isinstance(result, Exception) else result for result in results)


def illustration(filename: str, width: float | None = None, *, height: float | None = None):
    """Scale a bundled SVG to a requested height or width while preserving its aspect ratio."""
    drawing = svg2rlg(str(ASSETS / filename))
    if drawing is None:
        raise ValueError(f"Invalid PDF illustration: {filename}")
    if width is None:
        if height is None:
            raise ValueError("An illustration width or height is required")
        factor = height / drawing.height
    else:
        factor = width / drawing.width
        if height is not None:
            factor = min(factor, height / drawing.height)
    drawing.scale(factor, factor)
    drawing.width *= factor
    drawing.height *= factor
    return drawing


def prepared_mass(recipe: ExportRecipe) -> float:
    """Sum current measured masses or backend estimates; zero-quantity rows contribute nothing."""
    return sum(
        row.prepared_weight_g
        or preparation.estimate_prepared_weight(row).prepared_weight_g
        or row.quantity_g
        for row in recipe.ingredients
        if row.quantity_g is not None and row.quantity_g > 0
    )


def ingredient_description(
    ingredient: ExportIngredient, unnamed: str = "Unnamed ingredient"
) -> str:
    """Append readable ingredient labels in parentheses, preserving their display order."""
    name = ingredient.name or unnamed
    labels = [label.label.strip() for label in ingredient.labels if label.label.strip()]
    return f"{name} ({', '.join(labels)})" if labels else name


def render_pdf(reports, translations: ReportTranslations | None = None) -> bytes:
    """Flow compact recipes across A4 pages with print permission and editing restrictions."""
    labels = translations or ReportTranslations()
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=12 * mm,
        title=labels.title,
        author="Open Food Facts",
        encrypt=StandardEncryption(
            "",
            ownerPassword=secrets.token_urlsafe(32),
            canPrint=1,
            canModify=0,
            canCopy=0,
            canAnnotate=0,
            strength=128,
        ),
    )
    normal = ParagraphStyle(
        "RecipeText", fontName="RecipeSans", fontSize=9, leading=12, spaceAfter=3
    )
    small = ParagraphStyle(
        "RecipeSmall", parent=normal, fontSize=7.5, leading=10, textColor=colors.HexColor("#555555")
    )
    heading = ParagraphStyle(
        "RecipeHeading",
        parent=normal,
        fontName="RecipeSansBold",
        fontSize=12,
        leading=15,
        spaceBefore=8,
        spaceAfter=5,
        keepWithNext=True,
    )

    def text(value, style=normal):
        """Escape user content before ReportLab's paragraph markup parser sees it."""
        return Paragraph(escape(str(value)), style)

    def labelled_text(label, value, style=normal):
        """Emphasize list labels while keeping escaped list contents in regular weight."""
        return Paragraph(f"<b>{escape(label)}:</b> {escape(str(value))}", style)

    def table(data, widths, header=False):
        """Style readable compact tables, repeating nutrition headers across page breaks."""
        result = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if header:
            commands += [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
            ]
        result.setStyle(TableStyle(commands))
        return result

    def exclusions(count, percent):
        """Match the website's partial-result disclosure."""
        return text(
            labels.exclusions.replace("{count}", str(count)).replace("{percent}", f"{percent:.0f}"),
            small,
        )

    story = [illustration("open-food-facts.svg", 110), Spacer(1, 12)]
    for recipe, green, nutritional in reports:
        recipe_story = []
        mass = prepared_mass(recipe)
        intro = [
            text(recipe.name, heading),
            text(
                labels.subtitle,
                small,
            ),
        ]
        ingredients = [
            ingredient_description(row, labels.unnamed_ingredient) for row in recipe.ingredients
        ]
        intro.append(labelled_text(labels.ingredients, ", ".join(ingredients)))
        recipe_story.extend([*intro, Spacer(1, 3)])
        green_box = []
        if green and green.numeric_score is not None and green.letter_grade:
            key = green.letter_grade.lower().replace("+", "-plus")
            green_box += [
                illustration(f"green-score-{key}.svg", height=SCORE_ILLUSTRATION_HEIGHT),
            ]
            excluded = [row for row in recipe.ingredients if row.id in green.missing_ingredient_ids]
            if excluded:
                total = sum(row.quantity_g or 0 for row in recipe.ingredients)
                share = sum(row.quantity_g or 0 for row in excluded) / total * 100 if total else 0
                green_box.append(exclusions(len(excluded), share))
        nutri_box = []
        if nutritional and nutritional.nutri_score:
            grade = nutritional.nutri_score
            nutri_box += [
                illustration(
                    f"nutri-score-{grade.grade.lower()}.svg", height=SCORE_ILLUSTRATION_HEIGHT
                ),
            ]
            if nutritional.excluded_ingredients:
                nutri_box.append(
                    exclusions(
                        len(nutritional.excluded_ingredients), nutritional.excluded_weight_percent
                    )
                )
        score_boxes = [box for box in (green_box, nutri_box) if box]
        if score_boxes:
            # Shared rows align both logos and subtitles, including when only one
            # score has exclusions. Keep those rows together across page breaks.
            score_rows = [[box[0] for box in score_boxes]]
            if any(len(box) > 1 for box in score_boxes):
                score_rows.append([box[1] if len(box) > 1 else "" for box in score_boxes])
            score_table = table(score_rows, [doc.width / 2] * len(score_boxes))
            # Match the text and nutrition table's outer left edge without a cell inset.
            score_table.setStyle(
                TableStyle(
                    [
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("NOSPLIT", (0, 0), (-1, -1)),
                    ]
                )
            )
            recipe_story.extend([score_table, Spacer(1, 5)])
        nutrients = [
            ("energy_kj", labels.energy_kj),
            ("fat", labels.fat),
            ("saturated_fat", labels.saturated_fat),
            ("carbohydrates", labels.carbohydrates),
            ("sugars", labels.sugars),
            ("fiber", labels.fiber),
            ("proteins", labels.proteins),
            ("salt", labels.salt),
        ]
        rows = [
            [
                text(labels.nutrition),
                text(labels.per_100g),
                text(f"{labels.per_portion} ({mass / recipe.portions:g} g)"),
            ]
        ]
        for key, label in nutrients:

            def value(values):
                """Keep unknown nutrients visibly unavailable, never coerce them to zero."""
                amount = (values or {}).get(key)
                return text(
                    "—" if amount is None else f"{amount:.2f} {'kJ' if key == 'energy_kj' else 'g'}"
                )

            rows.append(
                [
                    text(label),
                    value(nutritional.nutrients_per_100g if nutritional else None),
                    value(nutritional.nutrients_per_portion if nutritional else None),
                ]
            )
        recipe_story.append(
            table(rows, [doc.width * 0.4, doc.width * 0.3, doc.width * 0.3], header=True)
        )
        recipe_story.append(Spacer(1, 8))
        for field in ("additives", "allergens"):
            tags = getattr(nutritional, field, []) if nutritional else []
            names = [
                tag.split(":", 1)[-1].replace("-", " ").upper()
                if field == "additives"
                else tag.split(":", 1)[-1].replace("-", " ").capitalize()
                for tag in tags
            ]
            recipe_story.append(
                labelled_text(
                    getattr(labels, field),
                    ", ".join(names) or labels.no_information,
                    small,
                )
            )
        recipe_story.append(Spacer(1, 20))

        # KeepTogether moves the full block to a fresh page if space is insufficient,
        # then allows normal paragraph/table splitting if it exceeds a full page.
        story.append(KeepTogether(recipe_story))

    def footer(canvas, document):
        """Number printed pages without taking space from the recipe content."""
        canvas.setFont("RecipeSans", 7)
        canvas.drawRightString(A4[0] - 12 * mm, 6 * mm, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


async def export_pdf(request: ExportRequest) -> bytes:
    """Bound upstream concurrency and keep PDF rendering off FastAPI's event loop."""
    semaphore = asyncio.Semaphore(2)

    async def calculate(recipe):
        """Limit concurrent recipe calculations for a multi-recipe export."""
        async with semaphore:
            return await calculate_report(recipe)

    reports = await asyncio.gather(*(calculate(recipe) for recipe in request.recipes))
    return await asyncio.to_thread(render_pdf, reports, request.translations)
