"""Future engine policy. No CLI option may disable these constants."""

ALL_AGES_SUFFIX = (
    "All ages, fully clothed, non-explicit. Respect the characters and their creators."
)
NEGATIVE_PROMPT = (
    "nsfw, nude, explicit sexual content, upskirt, degrading depiction, "
    "text, watermark, signature"
)

# Fail closed for unrecognised destinations when PH3 ancestry is present.
PH3_ALLOWED_PUBLISH = frozenset({"print_jp"})
