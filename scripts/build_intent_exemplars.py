"""
Build intent exemplars JSON using the MASSIVE dataset (and curated fallbacks).

Usage examples:

  # Run inside the API container (internet required for first download):
  docker compose exec api python scripts/build_intent_exemplars.py \
      --langs en he --per-intent 40 --out /app/data/intent_exemplars.json

  # Or locally in your venv:
  python scripts/build_intent_exemplars.py --langs en he --per-intent 40 --out seeds/intent_exemplars.json

The output JSON has the shape:
{
  "symptom": ["...", "..."],
  "meds": ["...", "..."],
  "appointment": ["...", "..."],
  "routine": ["...", "..."]
}

Supervisor loads it via INTENT_EXEMPLARS_PATH.
"""

from __future__ import annotations
import argparse
import json
import random
import re
from collections import defaultdict
import logging

try:
    from datasets import load_dataset, Dataset  # Added Dataset
except Exception:
    raise SystemExit("Install `datasets` (pip install datasets) to run this script.")


CURATED = {
    "symptom": [
        # English
        "I have a fever",
        "my head hurts",
        "I feel dizzy",
        "stomach ache since morning",
        "I have chills and sore throat",
        "I'm nauseous and tired",
        # Hebrew
        "יש לי חום",
        "כואב לי הראש",
        "בחילה וסחרחורת",
        "כואבת לי הבטן",
        "צמרמורת וכאבי גרון",
    ],
    "meds": [
        # English
        "refill my prescription",
        "took ibuprofen 200mg",
        "set a reminder to take my pill",
        "when should I take my medication?",
        # Hebrew
        "אני צריך מרשם לתרופה",
        "נטלתי תרופה",
        "תזכיר לי לקחת תרופה בבוקר",
    ],
    "appointment": [
        # seed in case MASSIVE yields few
        "book a lab appointment tomorrow",
        "schedule a doctor visit",
        "find a clinic near me",
        "reschedule my appointment",
        "קבע תור לרופא",
        "קבע תור לבדיקות דם",
        "בטל תור למרפאה",
    ],
    "routine": [
        "set a reminder for water every 2 hours",
        "weekly check-in on mood",
        "add a to-do for vitamins",
        "הוסף תזכורת לשתייה",
        "בדיקה שבועית",
        "משימה יומית",
    ],
}


def locale_matches(locale: str, langs: list[str]) -> bool:
    loc = (locale or "").lower()
    for lang_code in langs:
        lang_code_lower = lang_code.lower()
        if loc == lang_code_lower or loc.startswith(lang_code_lower + "-"):
            return True
    return False


def map_massive_intent(label: str) -> str | None:
    """Map MASSIVE intent labels to our buckets.
    This is heuristic and safe: we only return a bucket when the label clearly matches.
    """
    s = (label or "").lower()
    if any(k in s for k in ["appointment", "schedule", "reschedul", "book"]):
        return "appointment"
    if any(k in s for k in ["reminder", "alarm", "todo", "task", "note_"]):
        return "routine"
    # MASSIVE does not have strong medication/symptom intents; we rely on CURATED for those
    return None


def collect_from_massive(langs: list[str], per_intent: int) -> dict[str, list[str]]:
    ds: Dataset = load_dataset(
        "AmazonScience/massive", "all_1.1", split="train", trust_remote_code=True
    )
    buckets = defaultdict(list)
    for row in ds:  # row is a dictionary-like object
        # Ensure locale is a string, providing a default empty string if None
        locale_val: str = str(row.get("locale", ""))
        if not locale_matches(locale_val, langs):
            continue

        intent_id = row.get("intent")
        # Access features directly from ds, which is typed as Dataset
        intent_str = ds.features["intent"].int2str(intent_id)
        intent = map_massive_intent(intent_str)
        if not intent:
            continue

        utt = (row.get("utt") or "").strip()
        if not utt:
            continue
        buckets[intent].append(utt)
    # sample per bucket
    for k, arr in buckets.items():
        random.shuffle(arr)
        buckets[k] = arr[:per_intent]
    return buckets


def main():
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--langs",
        nargs="+",
        default=["en", "he"],
        help="language codes or prefixes, e.g. en he",
    )
    ap.add_argument("--per-intent", type=int, default=40)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    logging.info(
        f"Building intent exemplars for langs={args.langs}, per_intent={args.per_intent}, dataset=AmazonScience/massive"
    )
    buckets = {k: list(v) for k, v in CURATED.items()}
    from_massive = collect_from_massive(args.langs, args.per_intent)
    for k, arr in from_massive.items():
        buckets.setdefault(k, [])
        buckets[k].extend(arr)

    # dedupe and trim
    for k, arr in buckets.items():
        seen = set()
        ded = []
        for s in arr:
            s2 = re.sub(r"\s+", " ", s.strip())
            if s2 and s2 not in seen:
                seen.add(s2)
                ded.append(s2)
        # cap size to per-intent*2 (mix curated + dataset)
        buckets[k] = ded[: args.per_intent * 2]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(buckets, f, ensure_ascii=False, indent=2)
    logging.info(f"Wrote exemplars → {args.out}")
    logging.info("Done writing intent exemplars.")


if __name__ == "__main__":
    main()
