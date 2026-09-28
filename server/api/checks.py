"""Some high level checks (that are not self contained)"""

import api.off as off
from api.recipes import two_letter_lang_code


async def check_language_code(lang: str) -> bool:
    """Check if the language code is valid (exists in the OFF languages taxonomy).

    The code is normalized to its 2-letter form first (e.g. ``"en-US"`` ->
    ``"en"``) so that language codes carrying a region suffix are accepted, the
    business logic already normalizes them the same way.
    """

    languages = await off.languages_by_code()
    return two_letter_lang_code(lang) in languages


async def check_country_code(country: str) -> bool:
    """Check if the country code is valid (exists in the OFF countries taxonomy)"""

    countries = await off.origins_by_country_code()
    return country in countries
