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
or red-meat proportions, or unsupported cooking are excluded. With usable
ingredients remaining, `partial` results are normalized by their prepared mass,
not the total mass of excluded ingredients. Nutrition details can exist without
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
