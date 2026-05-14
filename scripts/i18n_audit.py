"""i18n 审计：检查 locale 键完整性 + 代码里未翻译的中文字面量。

用法:
    python scripts/i18n_audit.py                 # 只检查，不改
    python scripts/i18n_audit.py --fix           # 调 Claude 翻译并回写 locale 文件
    python scripts/i18n_audit.py --fix --dry-run # 只打印 AI 译文，不写盘
    python scripts/i18n_audit.py --no-code       # 跳过代码扫描（只查 locale 差异）
    python scripts/i18n_audit.py --model X       # 指定模型（默认 claude-haiku-4-5-20251001）

退出码:
    0  全部对齐
    1  发现问题且未修复（或 --fix 后仍有遗留：例如代码硬编码）
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，遇到 emoji / 部分 CJK 会崩；强制 UTF-8 输出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "seeed_jetson_develop" / "locales"
CODE_ROOT = ROOT / "seeed_jetson_develop"

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
CJK_RE = re.compile(r"[一-鿿]")

# 跳过这些路径：locale 源文件本身、AI 提示词目录、wiki/skills 数据 JSON 已由各自模块解析
SKIP_DIR_NAMES = {"locales", "__pycache__", "data"}

# 跳过这些文件名（按 basename 全词匹配）
SKIP_FILES = {
    "runtime_i18n.py",  # 这就是 zh→en 翻译表本身
    "i18n.py",          # 翻译加载器
    # Legacy GUI（项目入口是 run_v2.py → main_window_v2.py，下面这些是死代码）
    "main_window.py",
    "main_window_modern.py",
    "main_window_sdk.py",
    # CLI 子命令（rich markup 输出，不走 GUI i18n 渠道）
    "recovery.py",
    # 演示 / 抽象基类里 raise NotImplementedError 的中文消息——给开发者看的，不翻译
    "example_list_page.py",
    "list_page_base.py",
}

# 含 CSS / QSS 片段的字面量跳过：有花括号或 `属性:值;` 模式
QSS_HINT_RE = re.compile(r"\{\s|\}\s|^\s*[a-zA-Z-]+\s*:\s*[^;\n]+;", re.MULTILINE)

# 内联 ignore：已知的 false positive，路径精确到 (basename, lineno) 或 (basename, text)
# - onboarding_guide.py 的语言切换器："中文"是 zh 标签自身，不翻译
# - devices/page.py 的双语 fallback 文案：已包含中英两段，不需要重复翻译
IGNORE_LITERALS: set[tuple[str, str]] = {
    ("onboarding_guide.py", ';">中文</span>'),
}


def _is_bilingual_fallback(text: str) -> bool:
    """如果字符串里同时含 CJK 和一段 >=20 字的 ASCII 句子，认为是开发者写好的双语 fallback。"""
    if not CJK_RE.search(text):
        return False
    ascii_run = re.search(r"[A-Za-z][A-Za-z0-9 ,.;:'\"!?()\-\n]{19,}", text)
    return ascii_run is not None

# 这些调用里的字符串当作"日志/非 UI"忽略。后缀也算（如 logger.info）。
SKIP_CALL_NAMES = {
    "t",                # 已经走 i18n
    "print",
    "log_emit",
    "_log",
    "_emit_log",
    "warn",
    "warnings.warn",
    "traceback.format_exc",
}
SKIP_CALL_PREFIX = ("logger.", "logging.", "_logger.", "log.")


def load_locale_dir(lang: str) -> tuple[dict[str, str], dict[str, Path]]:
    """返回 (merged_key→value, key→file_path)。重复键会报错。"""
    merged: dict[str, str] = {}
    origin: dict[str, Path] = {}
    locale_dir = LOCALES_DIR / lang
    for fp in sorted(locale_dir.glob("*.json")):
        payload = json.loads(fp.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"{fp} must be a JSON object")
        for k, v in payload.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError(f"{fp} has non-string entry: {k!r}")
            if k in merged:
                raise ValueError(f"Duplicate key {k!r} (also in {origin[k]})")
            merged[k] = v
            origin[k] = fp
    return merged, origin


def diff_locales(zh: dict[str, str], en: dict[str, str]) -> tuple[list[str], list[str]]:
    """返回 (zh 有 en 缺, en 有 zh 缺)。"""
    return sorted(set(zh) - set(en)), sorted(set(en) - set(zh))


# ── 代码扫描：找未翻译的中文字面量 ──────────────────────────────────────────
def _call_name(call: ast.Call) -> str:
    """从 ast.Call.func 提取可读名字：foo / mod.foo / a.b.foo。失败返回 ''."""
    func = call.func
    parts: list[str] = []
    node: ast.AST = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    else:
        return ""
    return ".".join(reversed(parts))


def _attach_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent  # type: ignore[attr-defined]


def _is_in_data_literal(node: ast.Constant) -> bool:
    """node 是否处于模块级 ALL_CAPS = {...} 这类数据表里（dict/set/list/tuple key 或 value）。"""
    p = getattr(node, "_parent", None)
    # 跳出可能的 FormattedValue/JoinedStr 等包装
    while isinstance(p, (ast.FormattedValue, ast.JoinedStr)):
        p = getattr(p, "_parent", None)
    if not isinstance(p, (ast.Dict, ast.Set, ast.List, ast.Tuple)):
        return False
    # 一路向上找 Assign，看左值是不是 ALL_CAPS_NAME
    cur = p
    while cur is not None and not isinstance(cur, ast.Assign):
        cur = getattr(cur, "_parent", None)
    if not isinstance(cur, ast.Assign):
        return False
    for target in cur.targets:
        if isinstance(target, ast.Name) and target.id.isupper() and "_" in target.id + "_":
            return True
    return False


def _is_in_skipped_call(node: ast.Constant) -> bool:
    """node 是否作为参数出现在 SKIP_CALL_NAMES / SKIP_CALL_PREFIX 调用里。"""
    parent = getattr(node, "_parent", None)
    # 允许包一层 JoinedStr/FormattedValue（少见但保险）
    while isinstance(parent, (ast.FormattedValue, ast.JoinedStr)):
        parent = getattr(parent, "_parent", None)
    if not isinstance(parent, ast.Call):
        return False
    name = _call_name(parent)
    if not name:
        return False
    if name in SKIP_CALL_NAMES:
        return True
    return any(name.startswith(p) or name.endswith("." + p.rstrip(".")) for p in SKIP_CALL_PREFIX)


class CJKLiteralFinder(ast.NodeVisitor):
    """收集所有含 CJK 的字符串字面量（不含 docstring，不含日志调用参数）。"""

    def __init__(self, file_basename: str) -> None:
        self.hits: list[tuple[int, str]] = []
        self._doc_nodes: set[int] = set()
        self._basename = file_basename

    def _mark_docstring(self, node: ast.AST) -> None:
        body = getattr(node, "body", None)
        if not body:
            return
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            self._doc_nodes.add(id(first.value))

    def visit_Module(self, node: ast.Module) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self._doc_nodes:
            return
        if not isinstance(node.value, str) or not CJK_RE.search(node.value):
            return
        if _is_in_skipped_call(node):
            return
        if _is_in_data_literal(node):
            return
        if QSS_HINT_RE.search(node.value):
            return
        if (self._basename, node.value) in IGNORE_LITERALS:
            return
        if _is_bilingual_fallback(node.value):
            return
        self.hits.append((node.lineno, node.value))


def load_translation_table() -> tuple[set[str], list[re.Pattern]]:
    """从 runtime_i18n 导入 ZH_EN_EXACT/ZH_EN_PATTERNS。"""
    sys.path.insert(0, str(ROOT))
    try:
        from seeed_jetson_develop.gui import runtime_i18n
    finally:
        sys.path.pop(0)
    exact = set(runtime_i18n.ZH_EN_EXACT.keys())
    patterns = [p for p, _ in runtime_i18n.ZH_EN_PATTERNS]
    return exact, patterns


def is_translated(text: str, exact: set[str], patterns: list[re.Pattern]) -> bool:
    if text in exact:
        return True
    for p in patterns:
        if p.match(text):
            return True
    return False


def scan_code_for_untranslated() -> list[tuple[Path, int, str]]:
    """返回 [(file, lineno, text), ...]，按文件名排序。"""
    exact, patterns = load_translation_table()
    locale_zh_values = set(load_locale_dir("zh-CN")[0].values())

    results: list[tuple[Path, int, str]] = []
    for py_file in CODE_ROOT.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in py_file.relative_to(ROOT).parts):
            continue
        if py_file.name in SKIP_FILES:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        _attach_parents(tree)
        finder = CJKLiteralFinder(py_file.name)
        finder.visit(tree)
        for lineno, text in finder.hits:
            if is_translated(text, exact, patterns):
                continue
            if text in locale_zh_values:
                continue  # 已经在 locale JSON 里有对应中文条目
            results.append((py_file, lineno, text))
    results.sort(key=lambda x: (str(x[0]), x[1]))
    return results


# ── AI 修复：补齐 locale 缺失键 ──────────────────────────────────────────────
def ai_translate(
    items: list[tuple[str, str]],
    direction: str,
    model: str,
) -> dict[str, str]:
    """items: [(key, source_text)], direction: 'zh->en' or 'en->zh'。

    自动分批以避开模型 max_tokens 限制。
    """
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic SDK not installed. `pip install anthropic`.", file=sys.stderr)
        sys.exit(2)

    sys.path.insert(0, str(ROOT))
    try:
        from seeed_jetson_develop.core.config import get_runtime_anthropic_settings
    finally:
        sys.path.pop(0)

    settings = get_runtime_anthropic_settings()
    api_key = settings["api_key"]
    if not api_key:
        print(
            "ERROR: no ANTHROPIC_API_KEY. Set env var or configure in the app's "
            "Remote page (Claude API Setup).",
            file=sys.stderr,
        )
        sys.exit(2)

    client = anthropic.Anthropic(api_key=api_key, base_url=settings["base_url"])
    src_lang, tgt_lang = ("Chinese", "English") if direction == "zh->en" else ("English", "Chinese")

    BATCH_SIZE = 15  # 每批最多 15 条，防止输出超 max_tokens
    out: dict[str, str] = {}
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        out.update(_ai_translate_batch(client, batch, src_lang, tgt_lang, model))
    return out


def _ai_translate_batch(
    client,
    batch: list[tuple[str, str]],
    src_lang: str,
    tgt_lang: str,
    model: str,
) -> dict[str, str]:
    payload = {k: v for k, v in batch}
    user_msg = (
        f"Translate the following UI strings from {src_lang} to {tgt_lang}. "
        "These are short labels/messages from a PyQt5 desktop app for Jetson development. "
        "Keep emoji/punctuation/leading symbols (✓ ● ▶ → 📓 etc.) intact. "
        "Keep technical terms (SSH, Jetson, L4T, JetPack, CUDA, USB, GPIO, etc.) unchanged. "
        "Preserve any leading/trailing whitespace, newlines, and partial-sentence fragments verbatim "
        "(some inputs are interpolation fragments like '\\n\\nCommand failed (rc=' — translate the "
        "Chinese portion but keep the structure). "
        "Match the tone of similar UI strings: terse, sentence-case for English. "
        "Return ONLY a JSON object mapping each key to its translated string. "
        "No prose, no markdown fences.\n\n"
        f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    resp = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": user_msg}],
    )
    if resp.stop_reason == "max_tokens":
        print(
            f"ERROR: model hit max_tokens with batch of {len(batch)}. "
            "Try lowering BATCH_SIZE in the script.",
            file=sys.stderr,
        )
        sys.exit(2)
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)
    try:
        translated = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: model returned non-JSON:\n{raw[:800]}", file=sys.stderr)
        raise SystemExit(2) from e
    if not isinstance(translated, dict):
        print(f"ERROR: model returned non-object: {type(translated).__name__}", file=sys.stderr)
        sys.exit(2)
    return {str(k): str(v) for k, v in translated.items()}


def write_back(
    missing_keys: list[str],
    translations: dict[str, str],
    source_origin: dict[str, Path],
    target_lang: str,
) -> dict[Path, int]:
    """把翻译写回目标语言对应的 JSON 文件，键文件归属沿用源语言。"""
    by_file: dict[Path, dict[str, str]] = {}
    for k in missing_keys:
        if k not in translations:
            continue
        src_file = source_origin[k]
        tgt_file = LOCALES_DIR / target_lang / src_file.name
        by_file.setdefault(tgt_file, {})[k] = translations[k]

    written: dict[Path, int] = {}
    for tgt_file, additions in by_file.items():
        existing: dict[str, str] = {}
        if tgt_file.exists():
            existing = json.loads(tgt_file.read_text(encoding="utf-8-sig"))
        existing.update(additions)
        tgt_file.parent.mkdir(parents=True, exist_ok=True)
        tgt_file.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written[tgt_file] = len(additions)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fix", action="store_true", help="调 Claude 翻译并回写缺失的 locale 键")
    ap.add_argument("--dry-run", action="store_true", help="--fix 时只打印译文，不写盘")
    ap.add_argument("--no-code", action="store_true", help="跳过代码硬编码扫描")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"AI 模型 (默认 {DEFAULT_MODEL})")
    args = ap.parse_args()

    zh, zh_origin = load_locale_dir("zh-CN")
    en, en_origin = load_locale_dir("en")
    zh_only, en_only = diff_locales(zh, en)

    print(f"== Locale keys: zh-CN={len(zh)}  en={len(en)} ==")
    if zh_only:
        print(f"\n[EN missing {len(zh_only)} keys]")
        for k in zh_only:
            print(f"  {k}  →  zh: {zh[k]!r}")
    if en_only:
        print(f"\n[ZH missing {len(en_only)} keys]")
        for k in en_only:
            print(f"  {k}  →  en: {en[k]!r}")
    if not zh_only and not en_only:
        print("All locale keys aligned.")

    code_hits: list[tuple[Path, int, str]] = []
    if not args.no_code:
        print("\n== Scanning code for hardcoded CJK strings ==")
        code_hits = scan_code_for_untranslated()
        if code_hits:
            print(f"Found {len(code_hits)} untranslated literal(s):")
            for fp, lineno, text in code_hits:
                rel = fp.relative_to(ROOT)
                snippet = text if len(text) <= 60 else text[:57] + "..."
                print(f"  {rel}:{lineno}  {snippet!r}")
            print(
                "\nTo translate: either move these into a locale JSON and use t(...), "
                "or add them to ZH_EN_EXACT in seeed_jetson_develop/gui/runtime_i18n.py.\n"
                "Suggested ZH_EN_EXACT entries (run with --fix to ask Claude for English):\n"
            )
        else:
            print("No untranslated CJK literals found in code.")

    if args.fix and (zh_only or en_only or code_hits):
        print("\n== AI fix ==")

        if zh_only:
            print(f"\nTranslating {len(zh_only)} keys zh → en (model={args.model})...")
            translated = ai_translate(
                [(k, zh[k]) for k in zh_only], "zh->en", args.model,
            )
            for k in zh_only:
                if k in translated:
                    print(f"  {k}: {zh[k]!r}  →  {translated[k]!r}")
            if not args.dry_run:
                written = write_back(zh_only, translated, zh_origin, "en")
                for fp, n in written.items():
                    print(f"  wrote {n} key(s) → {fp.relative_to(ROOT)}")

        if en_only:
            print(f"\nTranslating {len(en_only)} keys en → zh (model={args.model})...")
            translated = ai_translate(
                [(k, en[k]) for k in en_only], "en->zh", args.model,
            )
            for k in en_only:
                if k in translated:
                    print(f"  {k}: {en[k]!r}  →  {translated[k]!r}")
            if not args.dry_run:
                written = write_back(en_only, translated, en_origin, "zh-CN")
                for fp, n in written.items():
                    print(f"  wrote {n} key(s) → {fp.relative_to(ROOT)}")

        if code_hits:
            print(f"\nTranslating {len(code_hits)} hardcoded literal(s) for runtime_i18n.ZH_EN_EXACT...")
            uniq = sorted({text for _, _, text in code_hits})
            translated = ai_translate(
                [(s, s) for s in uniq], "zh->en", args.model,
            )
            print("\nPaste into runtime_i18n.ZH_EN_EXACT:")
            print("    # ── auto-generated by scripts/i18n_audit.py ─────────────────────")
            for s in uniq:
                if s in translated:
                    zh_repr = json.dumps(s, ensure_ascii=False)
                    en_repr = json.dumps(translated[s], ensure_ascii=False)
                    print(f"    {zh_repr}: {en_repr},")

    # 退出码：locale 不齐且未修复，或仍有代码硬编码
    leftover_locale = (zh_only or en_only) and not args.fix
    return 1 if (leftover_locale or code_hits) else 0


if __name__ == "__main__":
    sys.exit(main())
