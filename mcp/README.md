# 考研政治知识库 MCP

通用只读 MCP 服务：让 AI 精确检索**考研政治知识点**、按知识点**出题**。仅用 Python 标准库，零第三方依赖，任何支持 MCP 的客户端（MiMo Desktop、Claude Code、Cursor 等）都能接。

## 环境要求

- Python 3.8+（Windows 命令 `python`，macOS/Linux `python3`）
- 无需 `pip install`、无需 Node、无需网络、无需认证

## 快速开始

```bash
cd kaoyan-politics-mcp
python server.py        # 前台启动，等待 MCP 客户端接入（stdio）
```

`server.py` 默认读取同目录的 `data.json`。可用环境变量 `KYZZ_DATA` 指定其他位置：

```bash
KYZZ_DATA=/path/to/data.json python server.py
```

## 接入客户端

### MiMo Desktop（mimocode.jsonc 的 `mcp` 段）

```jsonc
"mcp": {
  "kaoyan-politics": {
    "type": "local",
    "command": ["python", "C:\\path\\to\\kaoyan-politics-mcp\\server.py"],
    "environment": { "KYZZ_DATA": "C:\\path\\to\\kaoyan-politics-mcp\\data.json" },
    "enabled": true
  }
}
```

改完保存，重启 MiMo Desktop（或新开会话）生效。见同目录 `config.example.jsonc`。

### Claude Code（`.mcp.json`）

```json
{
  "mcpServers": {
    "kaoyan-politics": {
      "command": "python3",
      "args": ["/path/to/kaoyan-politics-mcp/server.py"],
      "env": { "KYZZ_DATA": "/path/to/kaoyan-politics-mcp/data.json" }
    }
  }
}
```

### Cursor

Settings → MCP → Add，类型选 `stdio`，command 填 Python、args 填 `server.py` 绝对路径。

## 工具一览（只读，关键词优先）

用户以自然语言提问（如「出5道马原的题」「查剩余价值的知识点」）。

| 工具 | 参数 | 返回 |
|---|---|---|
| `search_knowledge_point` | `keyword`, `category`, `chapter`, `unit`, `limit` | 知识点摘要列表（含模糊命中） |
| `get_knowledge_point` | `id` **或** `keyword` | 单个知识点全文（含正文） |
| `get_kp_relations` | `id` **或** `keyword` | related / compare / prerequisite |
| `list_questions` | `keyword`, `knowledge_point_id`, `category`, `chapter`, `question_type`, `limit` | 习题摘要列表 |
| `get_question` | `id` **或** `keyword`(题干), `include_answer`(默认 true) | 题干/选项/答案/解析 |
| `compose_paper` | `keyword`, `knowledge_point_ids`, `category`, `question_type`, `count`, `exclude_ids`, `include_answers`(默认 false), `seed` | 抽题结果 |

**书籍名别名**：`马原`/`毛中特`/`史纲`/`习思想`/`思法` 会自动归一化为板块全名。

## 数据规模

- 知识点：502 个（马原 97 / 毛中特 47 / 习思想 165 / 史纲 128 / 思法 65）
- 习题：1526 题（含多选），已关联知识点
- 数据文件：`data.json`（约 3.5 MB）

## 数据更新

知识库更新后，用构建脚本重新生成 `data.json`：

```bash
python build_data.py
# 或指定路径：
python build_data.py --kb ../考研政治知识库 --ex ../考研政治习题知识库 --out data.json
```

重新生成后重启 MCP 客户端即可加载最新数据。
