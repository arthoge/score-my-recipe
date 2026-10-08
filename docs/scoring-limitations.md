# Scoring behaviour and limitations

## Green Score

The API weights Agribalyse EF impacts by entered ingredient quantities and applies
label, origin, transport and fresh-produce seasonality modifiers. The UI requests
`accountedWeights=scorable`: unmatched ingredients are excluded from the EF weight
denominator. The resulting score describes that subset. Its excluded-weight
percentage is coverage, not an accuracy or confidence percentage.

World/unspecified country or origin uses a conservative transport modifier
(default −7). Origin bonuses are separate. Freshness and seasonality are manual
boolean inputs: no preparation-date calendar or Unknown seasonality exists.
Seasonality currently considers all marked fresh ingredients, even ingredients
without an EF match; this should be included in recipe-methodology validation.

## Nutri-Score

Complete Open Food Facts product nutrition is preferred. Incomplete product
composition can use a complete selected Ciqual reference as a whole composition;
successful fallback is exposed in API assumptions and highlighted in the editor.
Product lookup errors are not silently replaced by generic food data.

Missing analytical values stay unknown. Quantified upper limits use documented
conservative bounds. Ingredients with missing required nutrients, unknown plant
proportions, or unsupported cooking are excluded. An unknown red-meat proportion
is checked at both mass-weighted bounds: when the numeric Nutri-Score and grade match, the
ingredient remains included and the API reports `red_meat_score_invariant`.
Otherwise the ingredient is excluded without fabricating its meat percentage.
With usable ingredients remaining, `partial` results are normalized by their
prepared mass, not the total mass of excluded ingredients. Nutrition details can exist without
a grade. Missing quantity and zero quantity rows are excluded; unknown mass
cannot be reflected accurately in the excluded-weight percentage.

The standard recipe UI always requests the meals category. The API still supports
specialized cheese/fat algorithms; beverages remain unsupported. The 2023 grade
is calculated through OFF's reserved, non-persisting product/test endpoint. OFF
availability and upstream algorithm behaviour are external dependencies. A live
contract check and offline tests exist, but broad official-calculator recipe
benchmarking is still required.

## Prepared weights and matching

Only four reviewed Bognár 2002 yield profiles exist: boiled basmati/white long-grain
rice, dried egg pasta, dried lentils and steamed peeled potatoes. Unsupported
weight transformations use the entered quantity. Rice, pasta and lentils have
reviewed cooked Ciqual nutrition counterparts. The potato weight factor does not
supply a reviewed nutrition counterpart. There is no general nutrient-retention,
evaporation, oil uptake or edible-waste model.

The total prepared weight is the sum of ingredient weights, not a separately
measured recipe yield. Manual ingredient weights can be replaced on edits to
calculation inputs. Portions divide nutrition totals; they do not change the
per-100-g Nutri-Score grade.

Automatic OFF product selection uses the first eligible search hit and does not
verify brand or semantic confidence. Taxonomy inheritance can produce broad food
references. Chefs must review matches; improving this selection is a release
priority. Volume/count conversion relies on available taxonomy density and weight
properties; unsupported units cannot be reliably converted.

## External calculation dependencies

The new product-search and Nutri-Score adapters currently target production OFF
URLs independently of the SDK environment setting. Live contract verification
and offline tests exist, but broad official-calculator recipe benchmarking is
still needed. These feature limitations are tracked in [TODO.md](../TODO.md).

## Make it better suggestions

The improvement dialog compares whole-recipe numeric scores for each proposed
swap. Green Score improvement is `(after - before) / abs(before) × 100`;
Nutri-Score improvement is `(before - after) / abs(before) × 100`, because fewer
Nutri-Score points are better. These percentages do not measure distances between
letter grades. A zero baseline or unavailable score displays a dash.

Candidates are discovered from CIQUAL food categories, base food names and
preparation descriptions, plus real Open Food Facts products in the original
product's category. There is no predefined food-code substitution list. Missing
CIQUAL references are resolved from existing environmental selections or the
established ingredient taxonomy correspondence before calculating the baseline;
explicit food/product choices are preserved and unrecognized free text is not
silently assigned a food.

Candidates are shortlisted separately by nutrient composition and Agribalyse
impact, then verified with the full recipe algorithms. The matching and ranking
rules still encode assumptions; catalog category membership does not guarantee
culinary suitability. This is a bounded search, not an exhaustive optimizer.

The search also tests 10% and 20% reductions for concentrated ingredients identified
by their composition (at least 70 g sugar, 60 g fat or 50 g salt per 100 g).
Quantities are displayed in the dialog. These can change taste or texture and
require the cook's judgment. Other food substitutions preserve quantities and
clear old product certifications and origins. Comparable OFF swaps retain the
generic environmental food reference; they do not establish product-specific
lifecycle data. Explicitly cooked/drained foods, unsupported cooking
transformations and manually measured prepared portions are not substituted
automatically.

A score can be compared when the same ingredients are covered on both sides,
including a partial recipe score. When a replacement makes an excluded ingredient
scorable, the comparison is recalculated on the original included rows to keep
the denominator consistent. New exclusions are rejected. Missing scores remain unknown.

A verified improvement in at least one available score is required. A worsening
in the other score is shown as a negative percentage; such trade-offs start
unchecked. A selected combination must still improve at least one score.
The empty state distinguishes unsupported substitutions, unavailable score data,
and alternatives that were evaluated without improving the available scores.
The search is bounded to 100 active ingredient rows and 60 candidates, with four
concurrent requests. Selected changes are recalculated together before they are
applied, since individual improvements cannot simply be added together.
