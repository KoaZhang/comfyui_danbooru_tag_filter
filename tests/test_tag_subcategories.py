import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "classify_tag_subcategories.py"
SPEC = importlib.util.spec_from_file_location("classify_tag_subcategories", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TagSubcategoryScriptTests(unittest.TestCase):
    def test_validate_batch_result_rejects_mismatched_order(self):
        with self.assertRaisesRegex(ValueError, "tag 不匹配"):
            MODULE.validate_batch_result(
                ["hairband", "earrings"],
                [
                    {"tag": "earrings", "subcategory": "耳饰"},
                    {"tag": "hairband", "subcategory": "头饰/发饰"},
                ],
                MODULE.CLOTHING_CONFIG.subcategories,
            )

    def test_validate_batch_result_rejects_invalid_subcategory(self):
        with self.assertRaisesRegex(ValueError, "类目非法"):
            MODULE.validate_batch_result(
                ["hairband"],
                [{"tag": "hairband", "subcategory": "帽子"}],
                MODULE.CLOTHING_CONFIG.subcategories,
            )

    def test_parse_response_text_supports_code_fence(self):
        parsed = MODULE.parse_response_text(
            """```json
            [{"tag":"hairband","subcategory":"头饰/发饰"}]
            ```"""
        )
        self.assertEqual(parsed[0]["subcategory"], "头饰/发饰")

    def test_read_tags_uses_single_column_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "single_column.csv"
            csv_path.write_text("tag\nhairband\n\nheels\n", encoding="utf-8")
            self.assertEqual(MODULE.read_tags(csv_path), ["hairband", "heels"])

    def test_load_checkpoint_filters_unknown_categories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"
            path.write_text(
                json.dumps({"hairband": "头饰/发饰", "mystery": "帽子"}, ensure_ascii=False),
                encoding="utf-8",
            )
            loaded = MODULE.load_checkpoint(path, MODULE.CLOTHING_CONFIG.subcategories)
            self.assertEqual(loaded, {"hairband": "头饰/发饰"})

    def test_classify_tags_resume_short_circuits_when_checkpoint_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "服饰.csv"
            output_path = tmp / "out.csv"
            review_path = tmp / "review.csv"
            checkpoint_path = tmp / "checkpoint.json"

            input_path.write_text("tag\nhairband\nearrings\n", encoding="utf-8")
            checkpoint_path.write_text(
                json.dumps({"hairband": "头饰/发饰", "earrings": "耳饰"}, ensure_ascii=False),
                encoding="utf-8",
            )

            args = MODULE.build_parser(default_config_key="clothing", allow_config_override=False).parse_args(
                [
                    "--base-url",
                    "https://example.invalid/v1",
                    "--model",
                    "fake-model",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--review",
                    str(review_path),
                    "--checkpoint",
                    str(checkpoint_path),
                ]
            )
            args = MODULE.apply_config_defaults(args, MODULE.CLOTHING_CONFIG)

            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
                exit_code = MODULE.classify_tags(args, MODULE.CLOTHING_CONFIG)

            self.assertEqual(exit_code, 0)
            with output_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(
                rows,
                [
                    ["tag", "subcategory"],
                    ["hairband", "头饰/发饰"],
                    ["earrings", "耳饰"],
                ],
            )

    def test_find_duplicate_tags_reports_unique_duplicates(self):
        duplicates = MODULE.find_duplicate_tags(["hairband", "earrings", "hairband", "hairband"])
        self.assertEqual(duplicates, ["hairband"])

    def test_person_features_prompt_contains_expected_categories(self):
        prompt = MODULE.build_user_prompt(MODULE.PERSON_FEATURES_CONFIG, ["aqua_hair", "slit_pupils"])
        self.assertIn("Danbooru 人物本身的特征 tag", prompt)
        self.assertIn("头发/发型", prompt)
        self.assertIn("眼睛/瞳孔", prompt)
        self.assertIn("生殖/私密部位", prompt)

    def test_person_features_paths_are_configured(self):
        config = MODULE.get_config("person_features")
        self.assertEqual(config.output_path, Path("tags_classified/人物本身的特征_二级分类.csv"))
        self.assertEqual(config.review_path, Path("tags_classified/人物本身的特征_二级分类_review.csv"))
        self.assertEqual(config.checkpoint_path, Path("tags_classified/.人物本身的特征_二级分类_checkpoint.json"))


if __name__ == "__main__":
    unittest.main()
