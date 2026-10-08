"""Conservative automatic food matching, separate from broad manual search suggestions."""

from functools import lru_cache
import re
import unicodedata

STOP_WORDS = frozenset("de du des la le les a au aux et en d l of the with and ou or mg".split())
DESCRIPTORS = frozenset(
    "saute sautee poele poelee fried sauteed roasted baked roti rotie "
    "raw cru crue cooked cuit cuite bouilli bouillie fresh frais fraiche refrigerated chilled dried dry sec seche "
    "light legere leger reduced reduit reduite allege allegee epaisse epais fluide semi entier whole average aliment moyen "
    "fat thick prepacked grated rape rapee sliced tranche tranchee shredded hache hachee rayon uht pasteurise pasteurisee pasteurised pasteurized preemballe preemballee "
    "drained egoutte egouttee surgele surgelee frozen minimum vierge virgin extra tout type all".split()
)
DISH_MARKERS = frozenset(
    "dessert chocolate chocolat cacao cocoa fantaisie confiserie confectionery cheese fromage "
    "chantilly patissiere anglaise glacee melange combinee blended blend mixture".split()
)
CLASSIFIERS = frozenset({"champignon", "mushroom", "poisson", "fish", "fruit", "legume"})


@lru_cache(maxsize=32768)
def normalize(text: str) -> str:
    """Cache accent-insensitive names; catalogue text is reused across every ingredient."""
    text = text.strip().lower().replace("’", "'").replace("œ", "oe")
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


@lru_cache(maxsize=32768)
def words(text: str) -> tuple[str, ...]:
    """Cache punctuation-insensitive tokens and common English/French singular forms."""
    values = re.findall(r"[a-z]+|\d+(?:\.\d+)?", normalize(text))
    return tuple(
        word[:-1]
        if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us"))
        else word
        for word in values
        if word not in STOP_WORDS
    )


@lru_cache(maxsize=8192)
def recipe_name(text: str) -> str:
    """Translate culinary naming conventions into catalogue words, without changing food codes."""
    text = normalize(text)
    text = re.sub(r"^chair\s+(?:de\s+|d')", "", text)
    text = re.sub(r"^flesh\s+of\s+", "", text)
    text = re.sub(r"\b(?:st[.\s-]+|saint[\s-]+)jacques\b", "saint jacques", text)
    text = re.sub(r"\bnoix\s+(?:de\s+)?saint jacques\b", "coquille saint jacques noix", text)
    text = text.replace("creme de lait", "creme")
    text = re.sub(r"^.+?\s+ou (?:specialite|preparation|produit) a base de\s+", "", text)
    return text


@lru_cache(maxsize=32768)
def features(text: str) -> tuple[tuple[str, ...], frozenset[str], frozenset[str]]:
    """Keep the primary food identity distinct from its preparation and flavouring mentions."""
    text = recipe_name(text)
    clauses = text.split(",")
    head = words(re.split(r"\b(?:ou|or)\b", clauses[0])[0])
    if len(head) == 1 and head[0] in CLASSIFIERS and len(clauses) > 1:
        head += words(clauses[1])
    all_words = frozenset(words(text))
    identity = tuple(word for word in head if word not in DESCRIPTORS and not word.isdigit())
    return identity, all_words, all_words & DESCRIPTORS


def automatic_rank(query: str, name: str) -> float:
    """Reject different primary foods and conflicting preparations before ranking plausible variants."""
    if not query.strip() or not name.strip():
        return 0.0
    if normalize(query) == normalize(name):
        return 1.0
    identity, terms, states = features(query)
    target, target_terms, target_states = features(name)
    if not identity or not target:
        return 0.0
    # A food within a prepared dish is not a correspondence for that ingredient.
    if identity[0] != target[0] and not (
        (target[0] in CLASSIFIERS and len(target) > 1 and identity[0] == target[1])
        or (target[0] in identity and identity[0] in target_terms)
    ):
        return 0.0
    if not set(identity) <= target_terms:
        return 0.0
    unexpected = (target_terms & DISH_MARKERS) - terms
    # A category appended to a specific food name is not an added ingredient.
    if target[0] in identity:
        unexpected -= {"cheese", "fromage"}
    if unexpected:
        return 0.0
    raw, cooked = (
        {"raw", "cru", "crue"},
        {
            "cooked",
            "cuit",
            "cuite",
            "bouilli",
            "bouillie",
            "saute",
            "sautee",
            "poele",
            "poelee",
            "fried",
            "sauteed",
            "roasted",
            "baked",
            "roti",
            "rotie",
        },
    )
    dry = {"dried", "dry", "sec", "seche"}
    fresh = {"fresh", "frais", "fraiche", "refrigerated", "chilled"}
    light = {"light", "legere", "leger", "reduced", "reduit", "reduite", "allege", "allegee"}
    for requested, conflicting in (
        (raw, cooked | dry),
        (cooked, raw | dry),
        (dry, cooked | raw),
        (fresh, {"uht"}),
        ({"uht"}, fresh),
    ):
        if states & requested and target_states & conflicting:
            return 0.0
    numbers = {float(word) for word in terms if re.fullmatch(r"\d+(?:\.\d+)?", word)}
    target_numbers = {float(word) for word in target_terms if re.fullmatch(r"\d+(?:\.\d+)?", word)}
    ranges = [
        (float(low), float(high))
        for low, high in re.findall(r"(\d+(?:\.\d+)?)\s*(?:-|à|to)\s*(\d+(?:\.\d+)?)", query)
    ]
    for low, high in ranges:
        if not any(low <= number <= high for number in target_numbers):
            return 0.0
        numbers -= {low, high}
    if not numbers <= target_numbers:
        return 0.0
    # A declared fat percentage can establish a reduced-fat variant even when
    # its commercial label omits the catalog's descriptive wording.
    if states & light and not target_states & light and not (numbers or ranges):
        return 0.0
    score = 0.93 - 0.04 * len(set(target) - set(identity) - CLASSIFIERS)
    # Prefer the named cut/part and the generic food over added flavourings or species.
    extra = target_terms - terms - DESCRIPTORS - STOP_WORDS - CLASSIFIERS
    score -= 0.01 * sum(not word.isdigit() for word in extra)
    if target_states & light and not states & light:
        score -= 0.16
    if states & fresh and target_states & fresh:
        score += 0.04
    if not states & (raw | cooked | dry):
        score += 0.015 if target_states & raw else 0
        score -= 0.16 if target_states & cooked else 0
    if "average" in target_terms or {"aliment", "moyen"} <= target_terms:
        score += 0.02
    return score if score >= 0.8 else 0.0
