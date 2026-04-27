# ComfyUI Danbooru Tag Filter

一个用于 ComfyUI 的 Danbooru tag 分类筛选节点。它可以把 tagger 输出的标签按类别过滤，例如只保留人物特征、表情、服饰，或排除环境、构图、物品等标签，方便在工作流里清理和重组提示词。

内置分类数据基于 Danbooru2024 general tags 分类数据，覆盖约 3.5 万个 tag，并为「服饰」和「人物本身的特征」提供二级分类筛选。

## 功能

- 按 Danbooru tag 大类筛选标签
- 支持 `min_score`，可过滤低置信度 tagger 结果
- 支持保留或移除未分类标签
- 支持服饰、人物特征二级分类筛选
- 输出逗号分隔文本和结构化 JSON，便于继续接入其他节点
- 无额外 Python 依赖，安装后重启 ComfyUI 即可使用

## 安装

### 方式一：ComfyUI Manager 通过 Git URL 安装

可以。项目公开后，可以在 ComfyUI Manager 里使用 GitHub 地址远程安装。

1. 打开 ComfyUI Manager
2. 选择通过 Git URL 安装自定义节点的入口
3. 粘贴仓库地址：

```text
https://github.com/KoaZhang/comfyui_danbooru_tag_filter.git
```

4. 安装完成后重启 ComfyUI

如果 Manager 没有立刻识别新节点，请刷新浏览器页面，或确认仓库被安装到了 `ComfyUI/custom_nodes/` 目录下。

### 方式二：手动安装

进入 ComfyUI 的 `custom_nodes` 目录：

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/KoaZhang/comfyui_danbooru_tag_filter.git
```

然后重启 ComfyUI。

## 使用方法

在 ComfyUI 中添加节点：

```text
Danbooru Tag Category Filter
```

节点分类位于：

```text
utils
```

### 输入

`tags_input` 支持以下格式：

逗号分隔文本：

```text
1girl, blue_hair, smile, school_uniform, outdoors
```

JSON 字符串数组：

```json
["1girl", "blue_hair", "smile"]
```

带分数的 JSON 对象数组：

```json
[
  {"tag": "blue_hair", "score": 0.98},
  {"tag": "smile", "score": 0.93},
  {"tag": "outdoors", "score": 0.72}
]
```

### 参数

- `min_score`：只对带 `score` 的输入生效，低于该值的 tag 会被过滤
- `keep_unclassified`：是否保留未在分类数据中匹配到的 tag
- 分类按钮：点击切换大类是否保留
- `All` / `None`：快速全选或清空大类
- 带蓝色标记的分类：表示有二级分类
- 双击带二级分类的按钮：打开二级分类面板

### 输出

`filtered_tags_text`：逗号分隔的 tag 文本，可直接接入提示词节点。

```text
blue_hair, smile, school_uniform
```

`filtered_tags_json`：结构化结果，包含分类和二级分类信息。

```json
[
  {
    "tag": "blue_hair",
    "score": 0.98,
    "category": "人物本身的特征",
    "subcategory": "头发/发型"
  }
]
```

## 分类数据

当前包含以下大类文件：

- 人物本身的特征
- 表情
- 服饰
- 动作
- 环境_背景
- 物品
- 构图
- 其他

其中「服饰」和「人物本身的特征」包含二级分类数据。

分类数据位于 [`tags_classified/`](tags_classified/)，数据说明见 [`tags_classified/README.md`](tags_classified/README.md)。

## 开发与测试

运行单元测试：

```bash
python -m unittest discover -s tests
```

项目主要结构：

```text
.
├── __init__.py
├── nodes/
│   └── tag_category_filter.py
├── web/
│   └── tag_category_filter.js
├── tags_classified/
└── tests/
```

## 数据来源

分类数据来源：

```text
https://huggingface.co/datasets/Wenaka/danbooru2024_general_tags_classified
```

请遵守相关数据源许可与使用要求。本项目仅用于学习、研究和个人工作流辅助，请勿用于非法用途或侵犯他人权益。

## License

Apache-2.0
