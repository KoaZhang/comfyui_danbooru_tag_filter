#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
from urllib import error, request

DEFAULT_TIMEOUT = 60
DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_RETRIES = 3
TAG_COLUMN_CANDIDATES = ("tag", "name")


@dataclass(frozen=True)
class ClassificationConfig:
    key: str
    display_name: str
    input_path: Path
    output_path: Path
    review_path: Path
    checkpoint_path: Path
    subcategories: Tuple[str, ...]
    category_guide: str
    system_prompt: str


CLOTHING_CONFIG = ClassificationConfig(
    key="clothing",
    display_name="服饰",
    input_path=Path("tags_classified/服饰.csv"),
    output_path=Path("tags_classified/服饰_二级分类.csv"),
    review_path=Path("tags_classified/服饰_二级分类_review.csv"),
    checkpoint_path=Path("tags_classified/.服饰_二级分类_checkpoint.json"),
    subcategories=(
        "头饰/发饰",
        "耳饰",
        "颈饰",
        "手饰",
        "腿饰/脚饰",
        "上装",
        "下装",
        "套装/连体/制服",
        "内衣/泳装/睡衣",
        "内裤",
        "袜子",
        "鞋子",
        "其他",
    ),
    category_guide="""
- 头饰/发饰：帽子、头巾、发箍、发夹、发带、角饰、头花等头部或头发上的装饰。
- 耳饰：耳环、耳坠、耳钉、耳夹等耳部饰品。
- 颈饰：项链、项圈、领结、领带、围巾、披肩、choker 等颈部饰品或颈部穿戴。
- 手饰：手套、手环、手镯、戒指、臂环、袖套等手部或手臂饰品。
- 腿饰/脚饰：脚环、腿环、护腿、膝饰、脚链等腿脚部饰品，但不包括袜子和鞋子。
- 上装：衬衫、T恤、毛衣、胸衣、夹克、大衣、斗篷、马甲等上半身主要服装。
- 下装：裙子、裤子、短裤、腰布、围裙等下半身主要服装。
- 套装/连体/制服：整套服装、连体服、制服、校服、cosplay 套装、角色专属 outfit、特殊 module 或成套服装。
- 内衣/泳装/睡衣：文胸、连体泳衣、比基尼上装、睡袍、睡裙、浴袍、吊带睡衣等。
- 内裤：胖次、三角裤、四角裤、丁字裤、灯笼裤等下身贴身内衣。
- 袜子：丝袜、短袜、过膝袜、裤袜、连裤袜、腿袜等。
- 鞋子：高跟鞋、靴子、凉鞋、拖鞋、运动鞋等各类鞋履。
- 其他：难以稳定归类的服饰标签，或过于模糊、泛化、跨部位的词。
""".strip(),
    system_prompt="""你是一个严谨的 Danbooru 服饰标签细分助手。\
你的任务是把给定的 tag 精确归入固定的中文二级类目之一。\
禁止发明新类目，禁止漏掉 tag，禁止打乱顺序。""",
)

PERSON_FEATURES_CONFIG = ClassificationConfig(
    key="person_features",
    display_name="人物本身的特征",
    input_path=Path("tags_classified/人物本身的特征.csv"),
    output_path=Path("tags_classified/人物本身的特征_二级分类.csv"),
    review_path=Path("tags_classified/人物本身的特征_二级分类_review.csv"),
    checkpoint_path=Path("tags_classified/.人物本身的特征_二级分类_checkpoint.json"),
    subcategories=(
        "头发/发型",
        "眼睛/瞳孔",
        "脸部/头部特征",
        "体型/身材",
        "皮肤/体表",
        "胸部特征",
        "四肢/手脚",
        "生殖/私密部位",
        "年龄/性别/身份",
        "种族/兽化/幻想特征",
        "异常解剖/附加器官",
        "纹身/疤痕/穿孔/标记",
        "其他",
    ),
    category_guide="""
- 头发/发型：发色、发长、刘海、辫子、卷发、双马尾、呆毛、发际线、鬓角、胡子以外的头发样式。
- 眼睛/瞳孔：眼睛颜色、瞳孔形状、眼白、异瞳、发光眼、额外瞳孔、眼部特殊纹样。
- 脸部/头部特征：耳朵、鼻子、嘴、牙齿、舌头、睫毛、眉毛、胡须、脸型、头部轮廓与普通头面部器官。
- 体型/身材：身高、胖瘦、肌肉、曲线、比例、年龄感以外的整体体格和躯干轮廓。
- 皮肤/体表：肤色、雀斑、晒痕、鳞片、毛皮、体毛、指甲、角质、皮肤纹理、体表颜色或覆盖物。
- 胸部特征：乳房、乳头、乳晕、胸型、泌乳等胸部相关特征。
- 四肢/手脚：手、手指、手臂、腿、脚、脚趾、机械手脚、肢体长度或局部形态。
- 生殖/私密部位：阴部、臀部、肛门、阴毛、阴茎、睾丸、阴蒂等私密身体部位。
- 年龄/性别/身份：年龄阶段、性别表达、性别状态、男性化/女性化、少年少女、成年人、身份类生理设定。
- 种族/兽化/幻想特征：精灵、恶魔、天使、龙人、兽耳、尾巴、角、翅膀、非人种族、幻想生物器官。
- 异常解剖/附加器官：额外眼睛、额外手臂、额外尾巴、分裂身体、附加器官、非正常解剖结构或数量异常。
- 纹身/疤痕/穿孔/标记：纹身、胎记、疤痕、缝线、穿孔、印记、特殊面部或身体标识。
- 其他：无法稳定归类、语义过泛、跨多个部位且不适合放入上述类目的词。
""".strip(),
    system_prompt="""你是一个严谨的 Danbooru 人物特征标签细分助手。\
你的任务是把给定的 tag 精确归入固定的中文二级类目之一。\
禁止发明新类目，禁止漏掉 tag，禁止打乱顺序。""",
)

CONFIGS: Dict[str, ClassificationConfig] = {
    CLOTHING_CONFIG.key: CLOTHING_CONFIG,
    PERSON_FEATURES_CONFIG.key: PERSON_FEATURES_CONFIG,
}


def get_config(config_key: str) -> ClassificationConfig:
    try:
        return CONFIGS[config_key]
    except KeyError as exc:
        raise ValueError(f"未知配置: {config_key}") from exc


def normalize_tag(value: str) -> str:
    return (value or "").strip()


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def chunked(items: Sequence[str], size: int) -> Iterable[List[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def read_tags(csv_path: Path) -> List[str]:
    rows = []
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            with csv_path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    raise ValueError(f"CSV 缺少表头: {csv_path}")

                field_map = {str(name).strip().lower(): name for name in reader.fieldnames if name}
                tag_field = next((field_map[key] for key in TAG_COLUMN_CANDIDATES if key in field_map), None)
                if tag_field is None and len(field_map) == 1:
                    tag_field = next(iter(field_map.values()))
                if tag_field is None:
                    raise ValueError(f"CSV 未找到 tag 列: {csv_path}")

                for row in reader:
                    tag = normalize_tag(row.get(tag_field, ""))
                    if tag:
                        rows.append(tag)
                return rows
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法读取 CSV 编码: {csv_path}")


def find_duplicate_tags(tags: Sequence[str]) -> List[str]:
    seen = set()
    duplicates = []
    duplicate_seen = set()
    for tag in tags:
        if tag in seen and tag not in duplicate_seen:
            duplicates.append(tag)
            duplicate_seen.add(tag)
        seen.add(tag)
    return duplicates


def build_user_prompt(config: ClassificationConfig, tags: Sequence[str]) -> str:
    categories_text = "\n".join(f"- {name}" for name in config.subcategories)
    tags_json = json.dumps(list(tags), ensure_ascii=False)
    return f"""
请将下面的 Danbooru {config.display_name} tag 归入固定类目。

可选类目只有这些：
{categories_text}

分类规则：
{config.category_guide}

额外约束：
1. 输出必须是 JSON 数组。
2. 数组长度必须与输入 tag 数量完全一致。
3. 输出顺序必须与输入顺序完全一致。
4. 每个元素格式必须是 {{"tag":"原tag","subcategory":"类目"}}。
5. subcategory 必须严格从给定类目中选择，不要输出解释文本。

输入 tags:
{tags_json}
""".strip()


def extract_message_content(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("API 响应缺少 choices")

    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)

    raise ValueError("API 响应缺少可解析的 message.content")


def parse_response_text(text: str) -> List[dict]:
    cleaned = strip_code_fence(text)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("模型输出不是 JSON 数组")
    return parsed


def validate_batch_result(
    expected_tags: Sequence[str],
    parsed: Sequence[dict],
    allowed_subcategories: Sequence[str],
) -> List[Tuple[str, str]]:
    if len(parsed) != len(expected_tags):
        raise ValueError(f"模型输出数量不匹配: expected={len(expected_tags)} actual={len(parsed)}")

    allowed_set = set(allowed_subcategories)
    validated = []
    for index, (expected_tag, item) in enumerate(zip(expected_tags, parsed), start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 项不是对象")

        raw_tag = normalize_tag(str(item.get("tag", "")))
        subcategory = normalize_tag(str(item.get("subcategory", "")))

        if raw_tag != expected_tag:
            raise ValueError(f"第 {index} 项 tag 不匹配: expected={expected_tag} actual={raw_tag}")
        if subcategory not in allowed_set:
            raise ValueError(f"第 {index} 项类目非法: {subcategory}")

        validated.append((raw_tag, subcategory))
    return validated


def request_subcategories(
    tags: Sequence[str],
    *,
    config: ClassificationConfig,
    base_url: str,
    model: str,
    api_key: str,
    timeout: int,
) -> List[Tuple[str, str]]:
    endpoint = f"{normalize_base_url(base_url)}/chat/completions"
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": build_user_prompt(config, tags)},
        ],
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = request.Request(endpoint, data=body, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw_text = response.read().decode(charset)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"请求失败: {exc}") from exc

    payload = json.loads(raw_text)
    message_text = extract_message_content(payload)
    parsed = parse_response_text(message_text)
    return validate_batch_result(tags, parsed, config.subcategories)


def load_checkpoint(checkpoint_path: Path, allowed_subcategories: Sequence[str]) -> Dict[str, str]:
    if not checkpoint_path.exists():
        return {}

    with checkpoint_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"checkpoint 格式错误: {checkpoint_path}")

    allowed_set = set(allowed_subcategories)
    normalized = {}
    for key, value in data.items():
        tag = normalize_tag(str(key))
        subcategory = normalize_tag(str(value))
        if tag and subcategory in allowed_set:
            normalized[tag] = subcategory
    return normalized


def save_checkpoint(checkpoint_path: Path, mapping: Dict[str, str]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("w", encoding="utf-8", newline="") as handle:
        json.dump(mapping, handle, ensure_ascii=False, indent=2, sort_keys=True)


def write_output(output_path: Path, tags: Sequence[str], mapping: Dict[str, str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("tag", "subcategory"))
        for tag in tags:
            writer.writerow((tag, mapping[tag]))


def write_review(review_path: Path, review_rows: Sequence[Tuple[str, str]]) -> None:
    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("tag", "issue"))
        for tag, issue in review_rows:
            writer.writerow((tag, issue))


def apply_config_defaults(args: argparse.Namespace, config: ClassificationConfig) -> argparse.Namespace:
    if args.input is None:
        args.input = config.input_path
    if args.output is None:
        args.output = config.output_path
    if args.review is None:
        args.review = config.review_path
    if args.checkpoint is None:
        args.checkpoint = config.checkpoint_path
    return args


def classify_tags(args: argparse.Namespace, config: ClassificationConfig) -> int:
    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        print(f"环境变量 {args.api_key_env} 未设置", file=sys.stderr)
        return 2

    tags = read_tags(args.input)
    if args.limit is not None:
        tags = tags[: args.limit]
    if not tags:
        print("输入标签为空，无需处理", file=sys.stderr)
        return 1

    duplicates = find_duplicate_tags(tags)
    if duplicates:
        preview = ", ".join(duplicates[:10])
        print(f"输入中存在重复 tag，已停止执行: {preview}", file=sys.stderr)
        return 1

    completed = load_checkpoint(args.checkpoint, config.subcategories) if args.resume else {}
    missing = [tag for tag in tags if tag not in completed]
    review_rows: List[Tuple[str, str]] = []

    if not missing:
        write_output(args.output, tags, completed)
        write_review(args.review, review_rows)
        print(f"全部标签已在 checkpoint 中，直接写出 {args.output}")
        return 0

    total = len(tags)
    for batch_index, batch in enumerate(chunked(missing, args.batch_size), start=1):
        last_error = None
        for attempt in range(1, args.max_retries + 1):
            try:
                result = request_subcategories(
                    batch,
                    config=config,
                    base_url=args.base_url,
                    model=args.model,
                    api_key=api_key,
                    timeout=args.timeout,
                )
                completed.update(result)
                if args.resume:
                    save_checkpoint(args.checkpoint, completed)
                processed = sum(1 for tag in tags if tag in completed)
                print(f"[batch {batch_index}] success {len(result)} tags (processed {processed}/{total})")
                break
            except Exception as exc:
                last_error = exc
                print(
                    f"[batch {batch_index}] attempt {attempt}/{args.max_retries} failed: {exc}",
                    file=sys.stderr,
                )
                if attempt < args.max_retries:
                    time.sleep(min(attempt, 3))
        else:
            assert last_error is not None
            fallback_issue = f"fallback_to_其他_after_retries: {last_error}"
            for tag in batch:
                completed[tag] = "其他"
                review_rows.append((tag, fallback_issue))
            if args.resume:
                save_checkpoint(args.checkpoint, completed)
            print(
                f"[batch {batch_index}] fallback {len(batch)} tags to 其他 after {args.max_retries} failures",
                file=sys.stderr,
            )

    unresolved = [tag for tag in tags if tag not in completed]
    if unresolved:
        print(f"仍有未完成标签: {len(unresolved)}", file=sys.stderr)
        return 1

    write_output(args.output, tags, completed)
    write_review(args.review, review_rows)
    print(f"已写出 {args.output}")
    print(f"已写出 {args.review}")
    if args.resume:
        print(f"checkpoint 已更新: {args.checkpoint}")
    return 0


def build_parser(default_config_key: str = "clothing", allow_config_override: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="使用 OpenAI 兼容接口细分 Danbooru 标签二级类目")
    if allow_config_override:
        parser.add_argument(
            "--config",
            choices=sorted(CONFIGS),
            default=default_config_key,
            help="分类配置，决定默认输入输出和固定类目",
        )
    parser.add_argument("--input", type=Path, default=None, help="输入 CSV 路径")
    parser.add_argument("--output", type=Path, default=None, help="输出 CSV 路径")
    parser.add_argument("--review", type=Path, default=None, help="复核 CSV 路径")
    parser.add_argument("--checkpoint", type=Path, default=None, help="续跑 checkpoint 路径")
    parser.add_argument("--base-url", required=True, help="OpenAI 兼容 API 根地址，例如 https://api.deepseek.com/v1")
    parser.add_argument("--model", required=True, help="模型名，例如 deepseek-chat")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="读取 API Key 的环境变量名")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="每批处理的 tag 数")
    parser.add_argument("--limit", type=int, default=None, help="仅处理前 N 条，便于小样本试跑")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="单批最大重试次数")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="单次请求超时秒数")
    parser.add_argument("--resume", dest="resume", action="store_true", help="启用 checkpoint 续跑")
    parser.add_argument("--no-resume", dest="resume", action="store_false", help="禁用 checkpoint 续跑")
    parser.set_defaults(resume=True)
    return parser


def parse_args(
    argv: Sequence[str] | None = None,
    *,
    default_config_key: str = "clothing",
    allow_config_override: bool = True,
) -> Tuple[argparse.Namespace, ClassificationConfig]:
    parser = build_parser(default_config_key=default_config_key, allow_config_override=allow_config_override)
    args = parser.parse_args(argv)

    if args.batch_size <= 0:
        parser.error("--batch-size 必须大于 0")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit 必须大于 0")
    if args.max_retries <= 0:
        parser.error("--max-retries 必须大于 0")
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")

    config_key = args.config if allow_config_override else default_config_key
    config = get_config(config_key)
    return apply_config_defaults(args, config), config


def main(
    argv: Sequence[str] | None = None,
    *,
    default_config_key: str = "clothing",
    allow_config_override: bool = True,
) -> int:
    args, config = parse_args(
        argv,
        default_config_key=default_config_key,
        allow_config_override=allow_config_override,
    )
    return classify_tags(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
