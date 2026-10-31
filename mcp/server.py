#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kaoyan-politics-mcp — 考研政治知识点/习题检索 MCP server（仅标准库，stdio）。

协议：MCP stdio 传输 = 换行分隔的 JSON-RPC 2.0 消息。
用法：python server.py
  - 数据文件默认取 server.py 同目录的 data.json，可用环境变量 KYZZ_DATA 覆盖。
  - 只读服务，无认证、无网络、无第三方依赖。
  - 关键词优先：用户/模型无需知道 ID，直接传关键词或书籍名即可。
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROTOCOL = "2024-11-05"
DATA = None

# 书籍名（板块）别名 -> 规范全名
CATEGORY_ALIASES = [
    ("马克思主义基本原理", "马克思主义基本原理"),
    ("马原", "马克思主义基本原理"),
    ("马克思主义", "马克思主义基本原理"),
    ("毛泽东思想和中国特色社会主义理论体系概论", "毛泽东思想和中国特色社会主义理论体系概论"),
    ("毛中特", "毛泽东思想和中国特色社会主义理论体系概论"),
    ("毛泽东思想", "毛泽东思想和中国特色社会主义理论体系概论"),
    ("习近平新时代中国特色社会主义思想概论", "习近平新时代中国特色社会主义思想概论"),
    ("习思想", "习近平新时代中国特色社会主义思想概论"),
    ("习概", "习近平新时代中国特色社会主义思想概论"),
    ("习近平新时代中国特色社会主义思想", "习近平新时代中国特色社会主义思想概论"),
    ("中国近现代史纲要", "中国近现代史纲要"),
    ("史纲", "中国近现代史纲要"),
    ("近代史", "中国近现代史纲要"),
    ("近现代史", "中国近现代史纲要"),
    ("思想道德与法治", "思想道德与法治"),
    ("思法", "思想道德与法治"),
    ("思想道德", "思想道德与法治"),
    ("思修", "思想道德与法治"),
]


def load_data():
    path = os.environ.get("KYZZ_DATA") or os.path.join(HERE, "data.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize_category(name):
    """把书籍名别名（马原/毛中特/史纲/习思想/思法…）归一化为规范板块名。"""
    if not name:
        return name
    n = name.strip()
    for alias, full in CATEGORY_ALIASES:
        if n == alias or (len(alias) <= 4 and alias in n):
            return full
    return n


# ---------------- 检索逻辑（只读） ----------------

def _rank_kp_ids(keyword=None, category=None, chapter=None, unit=None, fuzzy=True):
    """返回按相关度排序的 (score, kid) 列表。score: 0名称精确 1名称包含 2关键词 3正文模糊。"""
    kps = DATA["knowledge_points"]
    kw_idx = DATA["keyword_index"]
    cat = normalize_category(category)
    ranked = []
    seen = set()

    def add(kid, score):
        if kid in seen:
            return
        seen.add(kid)
        ranked.append((score, kid))

    if keyword:
        kw = keyword.strip().lower()
        for kid, kp in kps.items():              # 名称精确
            if kp["name"].lower() == kw:
                add(kid, 0)
        for kid, kp in kps.items():              # 名称包含
            if kid not in seen and kw in kp["name"].lower():
                add(kid, 1)
        for k, arr in kw_idx.items():            # 关键词索引
            if kw in k.lower():
                for kid in arr:
                    if kid not in seen:
                        add(kid, 2)
        for kid, kp in kps.items():              # 知识点关键词列表
            if kid not in seen and any(kw in x.lower() for x in kp.get("keywords", [])):
                add(kid, 2)
        if fuzzy:
            for kid, kp in kps.items():          # 正文包含（模糊）
                if kid not in seen and kw in kp.get("content", "").lower():
                    add(kid, 3)
    else:
        for kid in kps:
            add(kid, 0)

    out = []
    for score, kid in ranked:
        kp = kps[kid]
        if cat and cat not in kp["category"]:
            continue
        if chapter and chapter not in kp["chapter"]:
            continue
        if unit and unit not in kp["unit"]:
            continue
        out.append((score, kid))
    return out


def resolve_kp_ids(keyword=None, category=None, chapter=None, unit=None):
    """搜索用：全部相关知识点（含正文模糊命中）。"""
    return [kid for score, kid in _rank_kp_ids(keyword, category, chapter, unit)]


def topic_kp_ids(keyword, category=None, chapter=None):
    """出题/取题用：优先名称命中，其次关键词命中，最后正文模糊命中。"""
    if not keyword:
        return [kid for score, kid in _rank_kp_ids(None, category, chapter, None)]
    name_ids = [kid for score, kid in _rank_kp_ids(keyword, category, chapter, None, fuzzy=False)
                if score <= 1]
    if name_ids:
        return name_ids
    kw_ids = [kid for score, kid in _rank_kp_ids(keyword, category, chapter, None, fuzzy=False)
              if score <= 2]
    if kw_ids:
        return kw_ids
    return resolve_kp_ids(keyword, category, chapter)


def kp_summary(kp):
    return {
        "id": kp["id"],
        "name": kp["name"],
        "category": kp["category"],
        "chapter": kp["chapter"],
        "unit": kp["unit"],
        "keywords": kp.get("keywords", []),
    }


def q_summary(q):
    return {
        "id": q["id"],
        "question_type": q["question_type"],
        "source_unit": q["source_unit"],
        "category": q.get("category", ""),
        "knowledge_points": q["knowledge_points"],
    }


def q_full(q, include_answer=True):
    item = {
        "id": q["id"],
        "question_type": q["question_type"],
        "source_unit": q["source_unit"],
        "category": q.get("category", ""),
        "knowledge_points": q["knowledge_points"],
        "stem": q["stem"],
        "options": q["options"],
    }
    if include_answer:
        item["answer"] = q["answer"]
        item["explanation"] = q["explanation"]
    return item


def search_kp(keyword=None, category=None, chapter=None, unit=None, limit=20):
    ids = resolve_kp_ids(keyword, category, chapter, unit)
    out = []
    for kid in ids:
        kp = DATA["knowledge_points"][kid]
        out.append(kp_summary(kp))
    return out[: limit or 20]


def kp_by_ref(ref):
    """按 ID 或关键词定位单个知识点，返回 kp 对象。"""
    kid = (ref or "").strip()
    if kid in DATA["knowledge_points"]:
        return DATA["knowledge_points"][kid]
    ids = resolve_kp_ids(ref)
    if ids:
        return DATA["knowledge_points"][ids[0]]
    raise ValueError("未找到知识点（ID 或关键词）: %r" % ref)


def q_by_ref(ref):
    """按 ID 或题干关键词定位单个习题，返回 q 对象。"""
    qid = (ref or "").strip()
    if qid in DATA["questions"]:
        return DATA["questions"][qid]
    kw = ref.strip().lower()
    best = None
    for cur_id, q in DATA["questions"].items():
        if kw in q["stem"].lower():
            if best is None or len(q["stem"]) < len(DATA["questions"][best]["stem"]):
                best = cur_id
    if best is not None:
        return DATA["questions"][best]
    raise ValueError("未找到习题（ID 或题干关键词）: %r" % ref)


def list_questions(keyword=None, knowledge_point_id=None, category=None,
                   chapter=None, question_type=None, limit=50):
    questions = DATA["questions"]
    kq = DATA["knowledge_question_index"]
    cat = normalize_category(category)

    if knowledge_point_id:
        ids = kq.get(knowledge_point_id, [])
    elif keyword or cat or chapter or question_type:
        kp_ids = topic_kp_ids(keyword, category, chapter)
        ids = []
        for k in kp_ids:
            ids.extend(kq.get(k, []))
        ids = list(dict.fromkeys(ids))
    else:
        ids = list(questions.keys())

    out = []
    for qid in ids:
        q = questions.get(qid)
        if not q:
            continue
        if question_type and q["question_type"] != question_type:
            continue
        if cat and cat not in q.get("category", ""):
            continue
        if chapter:
            ok = any(DATA["knowledge_points"].get(k, {}).get("chapter", "") == chapter
                     for k in q["knowledge_points"])
            if not ok:
                continue
        out.append(q_summary(q))
    return out[: limit or 50]


def compose_paper(keyword=None, knowledge_point_ids=None, category=None,
                  question_type=None, count=10, exclude_ids=None,
                  include_answers=False, seed=None):
    questions = DATA["questions"]
    kq = DATA["knowledge_question_index"]
    cat = normalize_category(category)

    if knowledge_point_ids:
        ids = []
        for k in knowledge_point_ids:
            ids.extend(kq.get(k, []))
        ids = list(dict.fromkeys(ids))
    elif keyword or cat or question_type:
        kp_ids = topic_kp_ids(keyword, category, None)
        ids = []
        for k in kp_ids:
            ids.extend(kq.get(k, []))
        ids = list(dict.fromkeys(ids))
    else:
        ids = list(questions.keys())

    exclude = set(exclude_ids or [])
    cand = []
    for qid in ids:
        if qid in exclude:
            continue
        q = questions[qid]
        if question_type and q["question_type"] != question_type:
            continue
        if cat and cat not in q.get("category", ""):
            continue
        cand.append(qid)

    rng = random.Random(seed) if seed is not None else random.Random()
    if count and len(cand) > count:
        chosen = rng.sample(cand, count)
    else:
        chosen = cand
    return [q_full(questions[qid], include_answer=include_answers) for qid in chosen]


def call_tool(name, args):
    if name == "search_knowledge_point":
        return search_kp(args.get("keyword"), args.get("category"), args.get("chapter"),
                         args.get("unit"), args.get("limit"))
    if name == "get_knowledge_point":
        ref = args.get("id") or args.get("keyword")
        if not ref:
            raise ValueError("缺少参数：id 或 keyword")
        return kp_by_ref(ref)
    if name == "get_kp_relations":
        ref = args.get("id") or args.get("keyword")
        if not ref:
            raise ValueError("缺少参数：id 或 keyword")
        kp = kp_by_ref(ref)
        names = {k: DATA["knowledge_points"][k]["name"]
                 for k in set(kp["related"]) | set(kp["compare"]) | set(kp["prerequisite"])
                 if k in DATA["knowledge_points"]}
        return {
            "id": kp["id"],
            "name": kp["name"],
            "related": [{"id": k, "name": names.get(k, k)} for k in kp["related"]],
            "compare": [{"id": k, "name": names.get(k, k)} for k in kp["compare"]],
            "prerequisite": [{"id": k, "name": names.get(k, k)} for k in kp["prerequisite"]],
        }
    if name == "list_questions":
        return list_questions(args.get("keyword"), args.get("knowledge_point_id"),
                              args.get("category"), args.get("chapter"),
                              args.get("question_type"), args.get("limit"))
    if name == "get_question":
        ref = args.get("id") or args.get("keyword")
        if not ref:
            raise ValueError("缺少参数：id 或 keyword")
        return q_full(q_by_ref(ref), include_answer=args.get("include_answer", True))
    if name == "compose_paper":
        return compose_paper(args.get("keyword"), args.get("knowledge_point_ids"),
                             args.get("category"), args.get("question_type"),
                             args.get("count"), args.get("exclude_ids"),
                             args.get("include_answers", False), args.get("seed"))
    raise ValueError("未知工具: %r" % name)


# ---------------- MCP 协议 ----------------

TOOLS = [
    {
        "name": "search_knowledge_point",
        "description": "按关键词/书籍名/章节/单元检索考研政治知识点，返回知识点摘要列表。"
                       "用户通常用自然语言提问（如「剩余价值」「哲学基本问题」），直接传 keyword 即可，"
                       "无需知道知识点 ID；书籍名支持别名（马原/毛中特/史纲/习思想/思法）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "检索关键词，匹配知识点名称/正文/关键词索引"},
                "category": {"type": "string", "description": "书籍名或别名，如：马克思主义基本原理、马原"},
                "chapter": {"type": "string", "description": "章节，如：第一章 辩证唯物论"},
                "unit": {"type": "string", "description": "单元"},
                "limit": {"type": "integer", "description": "返回条数上限，默认 20"},
            },
        },
    },
    {
        "name": "get_knowledge_point",
        "description": "获取单个知识点的完整内容（名称、章节、关键词、关联关系、正文）。"
                       "传 id（形如 MARX-01-007）或直接传 keyword（如「剩余价值」）均可；"
                       "传 keyword 时自动定位最匹配的知识点。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "知识点 ID（可选）"},
                "keyword": {"type": "string", "description": "关键词（可选），与 id 二选一"},
            },
        },
    },
    {
        "name": "get_kp_relations",
        "description": "获取某个知识点的关联关系：related（相关）、compare（对比）、"
                       "prerequisite（前置）。传 id 或 keyword 均可，返回带名称的关联列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "知识点 ID（可选）"},
                "keyword": {"type": "string", "description": "关键词（可选），与 id 二选一"},
            },
        },
    },
    {
        "name": "list_questions",
        "description": "列出习题摘要（不含题干答案）。用户通常按主题/书籍名要题，"
                       "传 keyword（按知识点解析）或 category（书籍名）即可，无需知道习题 ID。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "主题关键词，解析为相关知识点后取其习题"},
                "knowledge_point_id": {"type": "string", "description": "知识点 ID（可选）"},
                "category": {"type": "string", "description": "书籍名或别名"},
                "chapter": {"type": "string", "description": "章节"},
                "question_type": {"type": "string", "description": "单选题 或 多选题"},
                "limit": {"type": "integer", "description": "返回条数上限，默认 50"},
            },
        },
    },
    {
        "name": "get_question",
        "description": "获取完整习题（题干、选项、答案、解析）。传 id（形如 Q-001001）或"
                       "题干关键词均可；出题场景请传 include_answer=false 隐藏答案。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "习题 ID（可选）"},
                "keyword": {"type": "string", "description": "题干关键词（可选），与 id 二选一"},
                "include_answer": {"type": "boolean", "description": "是否包含答案与解析，默认 true"},
            },
        },
    },
    {
        "name": "compose_paper",
        "description": "按主题/书籍名/知识点集合抽题组卷。用户要求如「出5道马原的题」"
                       "「出3道关于剩余价值的题」——传 category 或 keyword 即可，模型无需知道 ID。"
                       "默认随机抽取且不含答案（用于测验），可传 exclude_ids 避免重复，"
                       "include_answers=true 则带答案与解析。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "主题关键词，解析为相关知识点后从中抽题"},
                "knowledge_point_ids": {"type": "array", "items": {"type": "string"},
                                        "description": "知识点 ID 列表（可选，优先级高于 keyword）"},
                "category": {"type": "string", "description": "书籍名或别名，如：马原"},
                "question_type": {"type": "string", "description": "单选题 或 多选题"},
                "count": {"type": "integer", "description": "抽题数量，默认 10"},
                "exclude_ids": {"type": "array", "items": {"type": "string"},
                                "description": "要排除的习题 ID（避免重复）"},
                "include_answers": {"type": "boolean", "description": "是否包含答案与解析，默认 false"},
                "seed": {"type": "integer", "description": "随机种子（测试复现用）"},
            },
        },
    },
]


def dispatch(method, params):
    params = params or {}
    if method == "initialize":
        proto = params.get("protocolVersion") or DEFAULT_PROTOCOL
        return {
            "protocolVersion": proto,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "kaoyan-politics-mcp", "version": "1.0.0"},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = call_tool(name, args)
        except ValueError as e:
            return {"content": [{"type": "text", "text": "错误：%s" % e}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                "isError": False}
    if method == "ping":
        return {}
    raise ValueError("unknown method: %s" % method)


def main():
    global DATA
    DATA = load_data()
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if not isinstance(msg, dict) or "id" not in msg:
            continue  # notification（如 notifications/initialized）无需回复
        mid = msg["id"]
        method = msg.get("method", "")
        try:
            result = dispatch(method, msg.get("params"))
            resp = {"jsonrpc": "2.0", "id": mid, "result": result}
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32601 if "unknown method" in str(e) else -32603,
                              "message": str(e)}}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
