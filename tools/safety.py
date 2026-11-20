"""Generation policy shared by all engines. No CLI option may disable these constants."""

ALL_AGES_SUFFIX = (
    "All ages, fully clothed, non-explicit. Respect the characters and their creators."
)
NEGATIVE_PROMPT = (
    "nsfw, nude, explicit sexual content, upskirt, degrading depiction, "
    "text, watermark, signature"
)

# うちの例（AIニケちゃん）のキャラ ID。公式ガイドラインの表記・小物の決まりをかけるのに使う。自分のキャラに合わせて書き替える。
NIKE_IDS = frozenset({"nike", "nikechan", "AIニケちゃん"})

# Fail closed for unrecognised destinations when PH3 ancestry is present.
PH3_ALLOWED_PUBLISH = frozenset({"print_jp"})
