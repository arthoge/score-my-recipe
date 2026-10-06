# Score My Recipe — Three-Day Hackathon Plan

This document is the shared implementation guide for the Open Food Facts hackathon. It records the agreed scope and team responsibilities; it is not a claim that these features have already been implemented.

For a new coding chat, start with:

> Read AGENTS.md, docs/technical-architecture.md and docs/hackathon-plan.md. We are working on Developer [A/B/C/D]'s Day [1/2/3] tasks. Check the current implementation before making changes.

## 1. Context and goal

Score My Recipe already has a FastAPI backend, a SvelteKit frontend, Open Food Facts ingredient parsing, a single-recipe editor and an Agribalyse-based Green-Score calculation. The hackathon extends this foundation for restaurant and canteen chefs.

The target workflow is:

**Import CSV → review ingredients and preparation → analyze recipes → compare substitutions → select dishes → export a PDF menu.**

Every business operation must also be available through the API. Follow the [existing architecture](technical-architecture.md): business logic belongs in the backend; the frontend handles presentation and interaction. Keep FastAPI, Pydantic, SvelteKit, DaisyUI and the repository's current conventions.

We will start with the interface to make the workflow visible to the whole team. The frontend initially uses clearly labelled sample responses while the backend is developed in parallel. Sample scores must never be presented as real calculations.

### Existing foundation and planned additions

| Area | Existing foundation | Hackathon work |
| --- | --- | --- |
| Recipes | OFF parsing and single-recipe editing | CSV import, review and multiple-recipe results |
| Green-Score | Agribalyse calculation and environmental adjustments | Explanations and data coverage |
| Nutrition | CIQUAL identifiers in some mappings | Versioned composition data and nutrient aggregation |
| Preparation | Ingredient quantities | Raw/cooked/drained states, documented yields and final weight |
| Nutri-Score | No recipe calculation | OFF adapter for algorithm 2023 and component explanations |
| Suggestions | Search for environmentally scorable ingredients | Explicit substitution rules and full recipe comparison |
| PDF | No menu export | Selected dishes and detailed annexes |
| API | Existing routes, schemas and generated types | Contracts for all new operations |

### MVP scope

- Food dishes imported using the supplied CSV format.
- Editable ingredient matching, quantities and preparation details.
- Green-Score and Nutri-Score with independent availability states and explanations.
- A small, documented preparation catalogue.
- Two initial substitution rules.
- Selected recipes exported as a backend-generated A4 PDF.
- Browser-local storage of the current batch, without accounts or a server database.

Allergens, traces and vegetarian/vegan indications are a complementary task only after the main workflow works. Shared recipe libraries, arbitrary CSV formats, general cooking coverage, dietary certifications, gluten-free claims and comprehensive additive analysis are outside the MVP.

## 2. User interface

### Import page: `/import`

- Explain the expected CSV structure and provide a downloadable template and example.
- State that quantities are grams of edible ingredients.
- Upload the file and display recipe-level and row-level diagnostics.
- Allow valid recipes to proceed even when other recipes contain errors.

### Review step

Reuse or extend the existing `/score` editor for corrections, keeping the recipe connected to its imported batch.

- Show recipe name, portions and every ingredient.
- Allow editing ingredient names, quantities, nutrition references, state and preparation profile.
- Show suggested matches separately from confirmed references.
- Offer generic CIQUAL foods and precisely identified OFF products where appropriate.
- Ask the chef to resolve ambiguous matches and missing ingredient quantities.
- Show a prepared-weight estimate only when a documented profile applies; label it as estimated.
- Accept an optional measured prepared ingredient weight and an optional final dish weight.
- Keep corrections in the local batch and invalidate previous analyses when a recipe changes.

Do not invent an ingredient quantity when it is absent. An environmental taxonomy match is not automatically a reliable nutrition reference.

### Results page: `/results`

- Display recipe name, both scores when available, data quality and selection controls.
- Provide actions to correct a recipe, open explanations and compare substitutions.
- Show nutrition per 100 g and per portion, preparation assumptions and missing data.
- Compare the original with a separately analyzed variant before the chef applies it.
- Preserve the original recipe when creating a variant.
- Export selected dishes in their displayed order.

## 3. Shared contracts and backend design

Agree on request models and example responses during the first team session. Developer B owns shared Pydantic models, route registration and OpenAPI generation. Other developers provide focused service functions instead of editing the same central files.

### Recipe models

Use an editable draft model for unresolved imports and a validated recipe model for analysis. Reuse existing ingredient structures and aliases wherever possible.

A recipe includes `id`, `name`, `portions`, `lang`, `country`, ingredients, optional `finalWeightG` and optional `finalYieldFactor`.

Ingredient additions include:

- Quantity state: `raw`, `cooked` or `drained`.
- Nutrition reference: CIQUAL code or OFF barcode.
- Confirmation status for proposed references.
- Optional preparation profile.
- Optional measured prepared weight.

Do not accept both final weight and final yield factor for the same transformation. Quantities refer to edible parts; automatic handling of bones, shells and peel is deferred.

### Analysis result

Return the normalized recipe, environmental results, nutrition per 100 g and per portion, Nutri-Score version and component points, prepared masses, final weight, sources, data versions, assumptions and warnings.

Each score has its own status:

| Status | Meaning |
| --- | --- |
| `computed` | Calculation succeeded; assumptions remain visible |
| `incomplete` | Required data is missing |
| `unsupported` | Preparation or category is outside supported coverage |
| `dependency_error` | An external dependency failed |

Distinguish measured weights from estimated weights. A missing nutrient value must remain missing, rather than becoming zero.

### Planned API

| Route | Purpose |
| --- | --- |
| `POST /v1/recipes/import-csv` | Return editable recipes, diagnostics and proposed matches |
| `GET /v1/nutrition/foods` | Find generic nutrition references |
| `GET /v1/nutrition/products` | Look up precisely identified OFF products |
| `GET /v1/preparation-profiles` | List supported profiles and sources |
| `POST /v1/recipes/analyze` | Analyze one recipe |
| `POST /v1/recipes/analyze-batch` | Return an analysis or error for each recipe |
| `POST /v1/recipes/recommendations` | Return analyzed variants and differences |
| `POST /v1/menus/export-pdf` | Analyze selected recipes and return a PDF |

Keep existing routes compatible. Keep HTTP handlers thin, with separate services for import, nutrition data, preparation, analysis, recommendations and PDF generation. Regenerate schemas and TypeScript types with `just generate-openapi`.

### CSV format

One row per ingredient, grouped by `recipe_id`:

```csv
recipe_id;recipe_name;portions;ingredient;quantity_g;state;ciqual_code;barcode;preparation_profile;final_weight_g
```

Nutrition identifiers, preparation profile and final weight are optional. Repeated recipe metadata must agree. Support UTF-8 with BOM, comma or semicolon separators, quoted cells and French decimal numbers. Diagnostics identify recipe, row and field. Reuse OFF parsing and taxonomies for ingredients without references, retaining uncertain matches for confirmation.

## 4. Nutrition, cooking and scores

### Restaurant recipe methodology: pilot report

The [French Ministry of Health's restaurant pilot report](https://sante.gouv.fr/IMG/pdf/bilan_etudes_pilotes_nutri-score_rhf.pdf) is an additional recipe-method reference, alongside the updated algorithm FAQ. Section 1 (pp. 7–10) describes five stages: list ingredients and quantities, establish nutrition per 100 g, account for edible parts, account for cooking yields, then calculate recipe nutrition and Nutri-Score.

The scoring unit is each component as served, rather than an average for a tray or menu. Annex 1 (p. 17) provides a pasta-recipe example; Annex 2 (pp. 18–23) supplies edible-part and cooking-yield coefficients used in the pilots.

Use this report for recipe preparation methodology. Keep algorithm 2023 as the implementation target and check historical examples against the updated rules before treating their grades as expected results.

**Source review remaining:** the full PDF could not be retrieved during this plan update. The indexed methodology and contents were accessible; exact coefficient definitions and annex calculations still require inspection before implementation.

#### Implementation decisions following this review

- In the MVP, one recipe represents one served component. Import a separately served main, side and sauce as separate recipes; ingredients mixed into one served dish remain one recipe.
- Keep the existing edible-weight CSV convention. Add a clear review acknowledgement that entered quantities exclude inedible parts. Gross purchase weights require correction before analysis; automatic edible-part conversion remains deferred.
- Use Annex 2 as the first candidate source when documenting the four initial preparation profiles. Inspect the precise food and process definitions and compare with the underlying Bognár source before adopting a coefficient. A broad pilot coefficient does not automatically expand our supported coverage.
- Make the preparation trace auditable: entered state/weight, edible-weight assumption, prepared reference, yield source, prepared mass and final normalization weight.
- UI and PDF show a grade for each selected served component. Do not produce a menu-wide Nutri-Score.
- Separate historical composition checks from algorithm-2023 grade tests. Record the data edition and algorithm version for each reference fixture.

### Nutrition references

Load a versioned local copy of CIQUAL 2025 with a reproducible acquisition command. Use CIQUAL for generic foods and OFF for products identified by barcode. Preserve the chef's explicit selections; replacing an identified product with an approximate generic reference requires confirmation.

### Cooking and final weight

Treat prepared mass and prepared composition as separate concerns:

1. Convert raw edible mass to prepared mass using a measured value or a documented yield.
2. Use a nutrition reference matching the prepared food and process.

The initial catalogue covers only:

- Long-grain white rice, boiled.
- Dried egg pasta, boiled.
- Dried lentils, boiled.
- Peeled potatoes, steamed.

Review Annex 2 of the restaurant pilot report and the applicable Bognár tables when selecting yields. Record the source, table, starting-weight definition and cooking conditions. Do not apply a profile indiscriminately to an entire food family. The catalogue still requires matching prepared nutrition references; a yield coefficient alone does not establish nutrient retention or cover unsupported processes.

Calculation rules:

- An already cooked or drained ingredient uses its entered weight and a matching prepared reference.
- A raw ingredient with a supported profile uses its measured prepared weight, otherwise its documented yield.
- Prepared CIQUAL references do not receive a second nutrient-retention correction.
- Water absorption included in a yield must not be counted again as added water.
- Without a final transformation, final dish weight is the sum of prepared masses.
- For a final transformation limited to water, use measured final weight or a final yield factor.
- Nutrient totals remain unchanged during a final water-only transformation.
- Calculate per-100-g composition as `total nutrient amount × 100 / final dish weight`.
- Calculate per-portion amounts from total nutrient amounts and the number of portions.

Frying, discarded salted liquid, removed juices and lost or absorbed fat are outside automatic coverage. A final weight measurement does not resolve these changes. Return `unsupported` when the necessary preparation/composition relationship is unavailable.

### Nutri-Score

Use the OFF calculation engine through its non-persisting `product/test` mode. On Day 1, verify the deployed service accepts the required nutrition, category and ingredient inputs and exposes the algorithm 2023 result.

- Calculate from the complete prepared recipe, never by averaging ingredient grades.
- Return the 2023 letter, numerical score and component points.
- Handle fruit, vegetable and legume proportions according to official rules, including dried or concentrated forms.
- Validate known examples against official reference calculations.
- Keep nutrition and environmental results available independently.
- Use timeouts, caching and call limits. A cached response must match the same calculation inputs.
- If OFF fails and no matching cached result exists, return `dependency_error`.

If the deployed OFF contract is incompatible, raise the integration issue with the OFF team. Do not improvise another algorithm or use fictional scores.

### Green-Score

Reuse the existing methodology and weight basis. Expose environmental adjustments, principal contributions and coverage by ingredient count and weight. Make clear that the existing calculation does not incorporate the new final cooking-yield treatment. Changes to environmental cooking methodology require a separate discussion with the maintainer.

## 5. Substitutions and PDF

### Initial substitution rules

- Reduce an identified salt ingredient quantity by 20%.
- Replace identified full-fat cream with reduced-fat cream at equal quantity.

Use explicit references and rules, rather than guessing eligibility from ingredient text alone. Each variant uses the same analysis service as the original. Return environmental and nutrition differences and available grade changes. Explain that culinary equivalence requires the chef's judgment.

Do not silently reuse the original recipe's measured final weight. Re-estimate the variant where supported or ask for a new measurement. An incomplete variant must not claim a certain score improvement.

### PDF export

Generate an A4 PDF in the backend using ReportLab. Accept selected recipes, their order, a title and language. Recompute analyses with the shared service; do not trust browser-supplied scores.

Include:

- A menu page containing the selected dishes and available scores.
- Annexes with quantified ingredients, nutrition and preparation assumptions.
- Generation date, data sources and calculation versions.
- Visible indications of estimates, incomplete information and unavailable scores.
- Official score graphics where applicable, without substituting arbitrary letters for missing results.

## 6. Team responsibilities and avoiding conflicts

| Developer | Owns | Hands off to |
| --- | --- | --- |
| A | Nutrition data, preparation and OFF Nutri-Score services | B, through service inputs and outputs |
| B | Shared models, CSV import, orchestration, API routes and substitutions | C and D, through stable API/service contracts |
| C | Frontend pages, components, local batch state and API interactions | Team, through a usable workflow |
| D | PDF service, demo recipes and integration validation | B for API wiring; C for export interaction |

Agree on module boundaries and function signatures before parallel work. B coordinates changes to shared models and routes. A and D work in their own service modules; C works in frontend files. Generated API types are updated through the agreed generation command, not independently hand-edited.

Use two short team check-ins each day, integrate at least daily and keep PRs focused. Branch from `main`, use Conventional Commits and follow repository disclosure requirements. Avoid moving or reformatting another developer's files during the hackathon.

## 7. Daily plan per developer

### Day 1 — Make the workflow visible and establish contracts

**Together, first hour:** sketch the three screens, agree on recipe and analysis models, define module ownership and prepare shared example responses.

**Developer A — Make sure the nutrition approach works**

- Review the pilot methodology and Annexes 1–2; document its relationship to our prepared-reference approach and algorithm 2023.
- Verify OFF `product/test` with a known composition and inspect the explicit 2023 result.
- Set up reproducible CIQUAL acquisition and nutrition lookup.
- Identify the prepared food references needed for the initial cooking profiles.
- Give B the nutrition/preparation service contract and reference fixtures.

**Developer B — Make recipes enter the system**

- Define shared Pydantic request and response models with the team.
- Document that one recipe is one served component and CSV quantities are edible weights; carry preparation provenance in the analysis contract.
- Implement CSV parsing, grouping, validation and partial-success diagnostics.
- Return editable drafts with uncertain matches and missing values visible.
- Expose the import route and generate the initial API schema/types.

**Developer C — Build the visible journey first**

- Create import, review and results screens using clearly labelled sample data.
- Explain separate served components and ask the chef to confirm edible quantities in the review step.
- Add editable ingredient rows, preparation fields and missing-data indicators.
- Store the batch locally and connect real CSV import as soon as B provides it.
- Ensure corrections update the corresponding recipe in the batch.

**Developer D — Prepare the demo and PDF structure**

- Create a ten-recipe CSV and cases covering valid imports, corrections and missing data.
- Prepare an Annex 1-inspired pasta fixture after A verifies its inputs; keep historical and updated algorithm expectations distinct.
- Agree on the menu and annex layout with C.
- Start PDF rendering with sample analyses behind the service contract.
- Prepare the end-to-end acceptance checklist.

**End-of-day checkpoint:** the complete UI journey is visible; a real CSV can reach the review step; sample scores are clearly marked; OFF compatibility has been assessed.

### Day 2 — Connect real calculations and explanations

**Developer A — Calculate the prepared recipe**

- Implement the four documented preparation profiles and compatible prepared references.
- Calculate prepared masses, nutrient totals, per-100-g and per-portion values.
- Support measured final weight and supported water-only yield adjustments.
- Integrate the OFF 2023 result, explanations, source versions and error handling.
- Test measured versus estimated weights, missing values and double-correction risks.

**Developer B — Assemble the complete analysis API**

- Combine A's nutrition service with the existing Green-Score engine.
- Implement single-recipe and batch analysis with independent score states.
- Expose nutrition-reference lookup and preparation-profile endpoints.
- Return environmental coverage, assumptions and actionable warnings.
- Update shared schemas and generated frontend types.

**Developer C — Replace samples with real results**

- Connect review corrections and analysis requests to the API.
- Add reference selection and preparation profile interactions.
- Show both scores, nutrition details, weight provenance and incomplete states.
- Handle batch progress and individual recipe failures.
- Invalidate an analysis when its recipe changes.

**Developer D — Render real PDF content**

- Use B's shared analysis service for selected recipes.
- Implement ordered menu pages and detailed annexes.
- Verify accents, pagination, sources and visible incomplete/estimated information.
- Coordinate the export request/response with B and C.

**End-of-day checkpoint:** UI and API analyze a recipe with estimated yield, a recipe with measured final weight and a recipe with incomplete nutrition data; the PDF service renders actual analysis results.

### Day 3 — Complete comparisons, export and validation

**Developer A — Validate calculation behavior**

- Compare reference cases with official Nutri-Score examples.
- Verify the pasta fixture's mass/nutrition trace separately from its algorithm-2023 grade.
- Check component rules, required nutrient values and supported preparation boundaries.
- Verify OFF timeout, matching-cache and dependency-failure behavior.
- Fix calculation defects found during integration.

**Developer B — Add substitutions and finish API integration**

- Implement the salt-reduction and cream-replacement rules.
- Reanalyze variants through the shared service and return differences.
- Preserve originals and handle variant final-weight changes explicitly.
- Wire the PDF endpoint to D's service.
- Finalize OpenAPI/type generation and API acceptance cases.

**Developer C — Finish the chef's workflow**

- Add original-versus-variant comparison and explicit variant application.
- Complete selection, displayed order and PDF download.
- Polish errors, incomplete states, loading behavior and small-screen layouts.
- Run the full journey with the team's demonstration CSV.

**Developer D — Validate and prepare the demonstration**

- Run the complete acceptance scenario through the UI and API.
- Verify a separately served main and side keep their own grades in the results and PDF, with no overall menu grade.
- Check PDF selection, ordering, nutrition and incomplete-data visibility.
- Coordinate integration fixes and repository checks with each owner.
- Prepare a reproducible demonstration and document remaining limitations.
- Only after the core workflow passes, consider declared allergens/traces and vegetarian/vegan indications with unknown states retained.

**Final checkpoint:** import ten recipes, correct one match, analyze estimated and measured weights, explain the scores, apply a substitution and export three selected dishes. Reproduce the same workflow through API calls.

### If only three developers are available

- A keeps nutrition, preparation and Nutri-Score.
- B also takes PDF generation, using the same analysis service.
- C also prepares demonstration recipes and coordinates manual workflow validation.
- Keep PDF layout simple and defer complementary allergen/diet work.

## 8. Validation and definition of done

Automated tests use fixtures and do not depend on live OFF calls. If a demonstration uses fixture responses, label that explicitly.

| Area | Required coverage |
| --- | --- |
| CSV | Separators, BOM, French decimals, quoted cells, invalid quantities, conflicting metadata and partial success |
| Matching | Explicit references, ambiguous matches, unknown foods and incompatible raw/prepared references |
| Preparation | Water loss, rehydration, measured/estimated weights and no double correction |
| Nutrition | Missing distinct from zero, consistent units, portions and preserved totals during water-only loss |
| Nutri-Score | Reference cases, component boundaries, plant proportion rules and explicit 2023 selection |
| Green-Score | Existing calculations unchanged; coverage and explanations consistent |
| OFF | Valid response, missing result, timeout, matching cache and failure without invented scores |
| Substitutions | Full reanalysis, original preserved, final weight reconsidered and no certain improvement for incomplete results |
| PDF | Exact selection/order, accents, pagination and visible incomplete information |
| UI/API | Identical recipe inputs give identical results |
| Restaurant methodology | Edible-weight acknowledgement, auditable cooking trace, versioned pasta fixture and separate served-component grades without a menu average |

Before a PR, run the applicable repository checks: pytest, Ruff, ty, frontend lint, Svelte/TypeScript checks, Vitest, translation checks, build and OpenAPI consistency. Each owner verifies their module; the team completes integration checks before the demonstration.

The prototype is finished when the final acceptance scenario passes, limitations are visible in the API, UI and PDF, and required checks pass.

## 9. Reference resources

These resources informed the plan. Verify deployed contracts and the exact source rows during implementation.

- [Project architecture](technical-architecture.md)
- [Contribution guide](CONTRIBUTING.md)
- [CIQUAL 2025](https://ciqual.anses.fr/cms/fr/la-table-ciqual-2025)
- [Restaurant Nutri-Score pilot report: methodology and Annexes 1–2](https://sante.gouv.fr/IMG/pdf/bilan_etudes_pilotes_nutri-score_rhf.pdf)
- [Bognár yield and retention tables](https://www.fao.org/uploads/media/bognar_bfe-r-02-03.pdf)
- [Official updated Nutri-Score FAQ](https://www.santepubliquefrance.fr/sites/default/files/rdd/document/FAQ-updatedAlgo-FR_V11.pdf)
- [OFF API v3 specification, including product test mode](https://github.com/openfoodfacts/openfoodfacts-server/blob/main/docs/api/ref/api-v3.yaml)
- [OFF API usage guidance](https://openfoodfacts.github.io/openfoodfacts-server/api/)
- [ReportLab user guide](https://docs.reportlab.com/reportlab/userguide/ch1_intro/)
