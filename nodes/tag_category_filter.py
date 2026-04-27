import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

UNKNOWN_CATEGORY = "Unknown"
SUBCATEGORY_SUFFIX = "_二级分类"
TAG_COLUMN_CANDIDATES = ("tag", "name")
CATEGORY_COLUMN_CANDIDATES = ("category", "class", "分类")
SUBCATEGORY_COLUMN_CANDIDATES = ("subcategory", "二级分类", "sub_category")


def _normalize_key(value: str) -> str:
    return (value or "").strip().lower()


def _normalize_tag(tag: str) -> str:
    return (tag or "").strip()


def _read_csv_rows(csv_path: Path) -> List[dict]:
    # CSV parsing with a light encoding fallback for common UTF-8 variants.
    last_error = None
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            with csv_path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    return []
                return list(reader)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception:
            return []
    if last_error:
        return []
    return []


def _is_primary_category_csv(csv_path: Path) -> bool:
    stem = csv_path.stem
    return not (
        stem.endswith(SUBCATEGORY_SUFFIX)
        or stem.endswith(f"{SUBCATEGORY_SUFFIX}_review")
        or stem.endswith("_review")
    )


def load_tag_category_mapping(base_dir: Path) -> Tuple[Dict[str, str], List[str], List[str]]:
    # Build the tag -> category mapping from tags_classified/*.csv.
    tags_dir = base_dir / "tags_classified"
    mapping: Dict[str, str] = {}
    warnings: List[str] = []
    categories: List[str] = []

    if not tags_dir.exists() or not tags_dir.is_dir():
        warnings.append(f"tags_classified directory not found: {tags_dir}")
        return mapping, [UNKNOWN_CATEGORY], warnings

    csv_files = [csv_path for csv_path in sorted(tags_dir.glob("*.csv")) if _is_primary_category_csv(csv_path)]
    for csv_path in csv_files:
        file_category = csv_path.stem
        categories.append(file_category)
        rows = _read_csv_rows(csv_path)
        if not rows:
            warnings.append(f"Skipped empty or unreadable CSV: {csv_path.name}")
            continue

        sample_keys = {_normalize_key(key): key for key in rows[0].keys() if key is not None}
        tag_field = next((sample_keys[key] for key in TAG_COLUMN_CANDIDATES if key in sample_keys), None)
        category_field = next(
            (sample_keys[key] for key in CATEGORY_COLUMN_CANDIDATES if key in sample_keys),
            None,
        )

        if tag_field is None and len(sample_keys) == 1:
            only_key = next(iter(sample_keys.values()))
            tag_field = only_key

        if tag_field is None:
            warnings.append(f"No tag column found in CSV: {csv_path.name}")
            continue

        for row in rows:
            raw_tag = row.get(tag_field, "")
            tag = _normalize_tag(raw_tag)
            if not tag:
                continue

            normalized_tag = _normalize_tag(tag).lower()
            category_name = file_category
            if category_field:
                explicit_category = _normalize_tag(row.get(category_field, ""))
                if explicit_category:
                    category_name = explicit_category

            if normalized_tag not in mapping:
                mapping[normalized_tag] = category_name

    unique_categories = sorted(set(categories))
    if UNKNOWN_CATEGORY not in unique_categories:
        unique_categories.append(UNKNOWN_CATEGORY)
    return mapping, unique_categories, warnings


def load_tag_subcategory_mapping(base_dir: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, List[str]], List[str]]:
    tags_dir = base_dir / "tags_classified"
    mapping: Dict[str, Dict[str, str]] = {}
    subcategories: Dict[str, List[str]] = {}
    warnings: List[str] = []

    if not tags_dir.exists() or not tags_dir.is_dir():
        return mapping, subcategories, warnings

    for csv_path in sorted(tags_dir.glob(f"*{SUBCATEGORY_SUFFIX}.csv")):
        category = csv_path.stem[: -len(SUBCATEGORY_SUFFIX)]
        rows = _read_csv_rows(csv_path)
        if not rows:
            warnings.append(f"Skipped empty or unreadable subcategory CSV: {csv_path.name}")
            continue

        sample_keys = {_normalize_key(key): key for key in rows[0].keys() if key is not None}
        tag_field = next((sample_keys[key] for key in TAG_COLUMN_CANDIDATES if key in sample_keys), None)
        subcategory_field = next(
            (sample_keys[key] for key in SUBCATEGORY_COLUMN_CANDIDATES if key in sample_keys),
            None,
        )

        if tag_field is None or subcategory_field is None:
            warnings.append(f"No tag/subcategory columns found in CSV: {csv_path.name}")
            continue

        category_mapping: Dict[str, str] = {}
        category_subcategories: List[str] = []
        for row in rows:
            tag = _normalize_tag(row.get(tag_field, ""))
            subcategory = _normalize_tag(row.get(subcategory_field, ""))
            if not tag or not subcategory:
                continue

            normalized_tag = tag.lower()
            if normalized_tag not in category_mapping:
                category_mapping[normalized_tag] = subcategory
            if subcategory not in category_subcategories:
                category_subcategories.append(subcategory)

        if category_mapping:
            mapping[category] = category_mapping
            subcategories[category] = category_subcategories

    return mapping, subcategories, warnings


def _default_selected_categories(categories: List[str], keep_unclassified: bool) -> List[str]:
    selected = [category for category in categories if category != UNKNOWN_CATEGORY]
    if keep_unclassified:
        selected.append(UNKNOWN_CATEGORY)
    return selected


def _default_selected_subcategories(available_subcategories: Dict[str, List[str]]) -> Dict[str, List[str]]:
    return {category: list(items) for category, items in available_subcategories.items()}


def _safe_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_tags_input(tags_input) -> List[dict]:
    # Normalize supported input formats into a unified internal list.
    if tags_input is None:
        return []

    if isinstance(tags_input, list):
        payload = tags_input
    else:
        text = str(tags_input).strip()
        if not text:
            return []
        payload = None
        if text.startswith("["):
            try:
                decoded = json.loads(text)
                if isinstance(decoded, list):
                    payload = decoded
            except json.JSONDecodeError:
                payload = None

        if payload is None:
            return [{"tag": part.strip(), "score": None} for part in text.split(",") if part.strip()]

    normalized = []
    for item in payload:
        if isinstance(item, str):
            tag = item.strip()
            if tag:
                normalized.append({"tag": tag, "score": None})
            continue

        if not isinstance(item, dict):
            continue

        tag = _normalize_tag(item.get("tag") or item.get("name") or "")
        if not tag:
            continue

        normalized.append(
            {
                "tag": tag,
                "score": _safe_float(item.get("score")),
            }
        )
    return normalized


class DanbooruTagCategoryFilter:
    CATEGORY = "utils"
    FUNCTION = "filter_tags"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("filtered_tags_text", "filtered_tags_json")
    OUTPUT_NODE = True

    BASE_DIR = Path(__file__).resolve().parent.parent
    TAG_MAPPING, AVAILABLE_CATEGORIES, CATEGORY_LOAD_WARNINGS = load_tag_category_mapping(BASE_DIR)
    SUBCATEGORY_MAPPING, AVAILABLE_SUBCATEGORIES, SUBCATEGORY_LOAD_WARNINGS = load_tag_subcategory_mapping(BASE_DIR)
    LOAD_WARNINGS = CATEGORY_LOAD_WARNINGS + SUBCATEGORY_LOAD_WARNINGS
    AVAILABLE_CATEGORIES_JSON = json.dumps(AVAILABLE_CATEGORIES, ensure_ascii=False)
    AVAILABLE_SUBCATEGORIES_JSON = json.dumps(AVAILABLE_SUBCATEGORIES, ensure_ascii=False)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tags_input": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "forceInput": True,
                    },
                ),
                "min_score": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                    },
                ),
                "keep_unclassified": ("BOOLEAN", {"default": True}),
                "selected_categories_json": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "hidden": True,
                    },
                ),
                "available_categories_json": (
                    "STRING",
                    {
                        "default": cls.AVAILABLE_CATEGORIES_JSON,
                        "multiline": False,
                        "hidden": True,
                    },
                ),
                "selected_subcategories_json": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "hidden": True,
                    },
                ),
                "available_subcategories_json": (
                    "STRING",
                    {
                        "default": cls.AVAILABLE_SUBCATEGORIES_JSON,
                        "multiline": False,
                        "hidden": True,
                    },
                ),
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    @staticmethod
    def _resolve_selected_categories(
        selected_categories_json: str,
        keep_unclassified: bool,
        categories: List[str],
    ) -> List[str]:
        if not selected_categories_json:
            return _default_selected_categories(categories, keep_unclassified)

        try:
            decoded = json.loads(selected_categories_json)
        except json.JSONDecodeError:
            return _default_selected_categories(categories, keep_unclassified)

        if not isinstance(decoded, list):
            return _default_selected_categories(categories, keep_unclassified)

        known_categories = set(categories)
        return [str(item) for item in decoded if str(item) in known_categories]

    @staticmethod
    def _resolve_selected_subcategories(
        selected_subcategories_json: str,
        available_subcategories: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
        if not selected_subcategories_json:
            return _default_selected_subcategories(available_subcategories)

        try:
            decoded = json.loads(selected_subcategories_json)
        except json.JSONDecodeError:
            return _default_selected_subcategories(available_subcategories)

        if not isinstance(decoded, dict):
            return _default_selected_subcategories(available_subcategories)

        selected: Dict[str, List[str]] = {}
        for category, subcategories in available_subcategories.items():
            raw_items = decoded.get(category)
            if raw_items is None:
                selected[category] = list(subcategories)
                continue
            if not isinstance(raw_items, list):
                selected[category] = list(subcategories)
                continue

            known_subcategories = set(subcategories)
            selected[category] = [str(item) for item in raw_items if str(item) in known_subcategories]

        return selected

    def filter_tags(
        self,
        tags_input,
        min_score,
        keep_unclassified,
        selected_categories_json="",
        available_categories_json="",
        selected_subcategories_json="",
        available_subcategories_json="",
    ):
        del available_categories_json
        del available_subcategories_json

        categories = list(self.AVAILABLE_CATEGORIES)
        selected_categories = self._resolve_selected_categories(
            selected_categories_json,
            keep_unclassified,
            categories,
        )
        selected_set = set(selected_categories)
        selected_subcategories = self._resolve_selected_subcategories(
            selected_subcategories_json,
            self.AVAILABLE_SUBCATEGORIES,
        )

        normalized_items = []
        for item in _parse_tags_input(tags_input):
            # min_score only applies to tags that actually carry a score.
            score = item.get("score")
            if score is not None and score < min_score:
                continue

            tag = item["tag"]
            category = self.TAG_MAPPING.get(tag.lower(), UNKNOWN_CATEGORY)
            subcategory = self.SUBCATEGORY_MAPPING.get(category, {}).get(tag.lower())
            normalized_items.append(
                {
                    "tag": tag,
                    "score": score,
                    "category": category,
                    "subcategory": subcategory,
                }
            )

        filtered_items = []
        for item in normalized_items:
            category = item["category"]
            if category not in selected_set:
                continue

            if category in self.AVAILABLE_SUBCATEGORIES:
                selected_subcategory_set = set(selected_subcategories.get(category, []))
                if item["subcategory"] not in selected_subcategory_set:
                    continue

            filtered_items.append(item)

        filtered_tags_text = ", ".join(item["tag"] for item in filtered_items)
        filtered_tags_json = json.dumps(filtered_items, ensure_ascii=False)
        return filtered_tags_text, filtered_tags_json
