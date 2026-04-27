import csv
import json
import tempfile
import unittest
from pathlib import Path

from nodes.tag_category_filter import (
    UNKNOWN_CATEGORY,
    DanbooruTagCategoryFilter,
    load_tag_category_mapping,
    load_tag_subcategory_mapping,
)


class TagCategoryFilterTests(unittest.TestCase):
    def test_primary_category_loader_excludes_subcategory_and_review_csvs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tags_dir = root / "tags_classified"
            tags_dir.mkdir()

            (tags_dir / "服饰.csv").write_text("tag\nhairband\n", encoding="utf-8")
            (tags_dir / "人物本身的特征.csv").write_text("tag\naqua_hair\n", encoding="utf-8")
            (tags_dir / "服饰_二级分类.csv").write_text(
                "tag,subcategory\nhairband,头饰/发饰\n",
                encoding="utf-8",
            )
            (tags_dir / "服饰_二级分类_review.csv").write_text("tag,issue\n", encoding="utf-8")

            mapping, categories, warnings = load_tag_category_mapping(root)

            self.assertEqual(mapping["hairband"], "服饰")
            self.assertEqual(mapping["aqua_hair"], "人物本身的特征")
            self.assertIn(UNKNOWN_CATEGORY, categories)
            self.assertNotIn("服饰_二级分类", categories)
            self.assertNotIn("服饰_二级分类_review", categories)
            self.assertEqual(warnings, [])

    def test_subcategory_loader_preserves_first_seen_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tags_dir = root / "tags_classified"
            tags_dir.mkdir()

            with (tags_dir / "服饰_二级分类.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["tag", "subcategory"])
                writer.writerow(["hairband", "头饰/发饰"])
                writer.writerow(["earrings", "耳饰"])
                writer.writerow(["tiara", "头饰/发饰"])

            mapping, subcategories, warnings = load_tag_subcategory_mapping(root)

            self.assertEqual(mapping["服饰"]["hairband"], "头饰/发饰")
            self.assertEqual(mapping["服饰"]["earrings"], "耳饰")
            self.assertEqual(subcategories["服饰"], ["头饰/发饰", "耳饰"])
            self.assertEqual(warnings, [])

    def test_default_subcategory_selection_keeps_existing_behavior(self):
        node = self._make_filter_node()

        text, payload = node.filter_tags(
            "hairband, earrings, aqua_hair, smile, mystery_tag",
            0.0,
            True,
        )

        self.assertEqual(text, "hairband, earrings, aqua_hair, smile, mystery_tag")
        decoded = json.loads(payload)
        self.assertEqual(decoded[0]["subcategory"], "头饰/发饰")
        self.assertEqual(decoded[3]["subcategory"], None)
        self.assertEqual(decoded[4]["category"], UNKNOWN_CATEGORY)

    def test_subcategory_selection_filters_inside_selected_primary_category(self):
        node = self._make_filter_node()

        text, _payload = node.filter_tags(
            "hairband, earrings, aqua_hair, smile, mystery_tag",
            0.0,
            True,
            selected_categories_json=json.dumps(["服饰", "人物本身的特征", "表情", UNKNOWN_CATEGORY], ensure_ascii=False),
            selected_subcategories_json=json.dumps(
                {
                    "服饰": ["耳饰"],
                    "人物本身的特征": ["头发/发型"],
                },
                ensure_ascii=False,
            ),
        )

        self.assertEqual(text, "earrings, aqua_hair, smile, mystery_tag")

    def test_primary_category_must_be_selected_even_when_subcategory_is_selected(self):
        node = self._make_filter_node()

        text, _payload = node.filter_tags(
            "hairband, earrings, aqua_hair, smile, mystery_tag",
            0.0,
            True,
            selected_categories_json=json.dumps(["表情", UNKNOWN_CATEGORY], ensure_ascii=False),
            selected_subcategories_json=json.dumps({"服饰": ["头饰/发饰", "耳饰"]}, ensure_ascii=False),
        )

        self.assertEqual(text, "smile, mystery_tag")

    def test_explicit_empty_primary_selection_returns_empty_result(self):
        node = self._make_filter_node()

        text, payload = node.filter_tags(
            "hairband, earrings, aqua_hair, smile, mystery_tag",
            0.0,
            True,
            selected_categories_json="[]",
        )

        self.assertEqual(text, "")
        self.assertEqual(json.loads(payload), [])

    @staticmethod
    def _make_filter_node():
        node = DanbooruTagCategoryFilter()
        node.TAG_MAPPING = {
            "hairband": "服饰",
            "earrings": "服饰",
            "aqua_hair": "人物本身的特征",
            "smile": "表情",
        }
        node.AVAILABLE_CATEGORIES = ["人物本身的特征", "服饰", "表情", UNKNOWN_CATEGORY]
        node.SUBCATEGORY_MAPPING = {
            "服饰": {
                "hairband": "头饰/发饰",
                "earrings": "耳饰",
            },
            "人物本身的特征": {
                "aqua_hair": "头发/发型",
            },
        }
        node.AVAILABLE_SUBCATEGORIES = {
            "服饰": ["头饰/发饰", "耳饰"],
            "人物本身的特征": ["头发/发型"],
        }
        return node


if __name__ == "__main__":
    unittest.main()
