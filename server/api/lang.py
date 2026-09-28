"""Business logic around languages."""


def two_letter_lang_code(lang: str) -> str:
    """Convert a language code to a 2-letter code (e.g. ``"fr-FR"`` -> ``"fr"``)."""
    return lang.replace("_", "-").split("-")[0]
