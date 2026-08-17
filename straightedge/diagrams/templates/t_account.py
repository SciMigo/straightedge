"""T-account (T 形账户 / 丁字账) — the iconic accounting teaching visual.

Every accounting course draws borrowed-vs-credit entries on a "T": the account
name sits on top, a horizontal rule under it, and a vertical rule splits the
**借方 (debit, left)** from the **贷方 (credit, right)**. Teachers use it
constantly to explain 借贷记账法, so the courseware generator can now emit a real
one instead of a bullet list.

image_hint usage::

    {"type": "t_account", "params": {
        "title": "借贷记账示例",
        "accounts": [
            {"name": "银行存款",
             "debit":  [{"text": "收到投资", "amount": "100000"}],
             "credit": [{"text": "购买设备", "amount": "60000"}]},
            {"name": "固定资产",
             "debit":  [{"text": "购入设备", "amount": "60000"}],
             "credit": []}]}}

A single account may also be given at the top level via ``name`` / ``debit`` /
``credit`` (no ``accounts`` list). Each entry is a bare string or a mapping with
``text`` (aliases ``label`` / ``name``) and optional ``amount`` (aliases
``value`` / ``money``). ``debit`` accepts alias ``left`` / ``借``; ``credit``
accepts ``right`` / ``贷``.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..registry import register
from ..renderer import group, line, rect, style, svg_document, text

MARGIN = 24
TITLE_H = 34
NAME_H = 34            # account-name band height
HEAD_H = 26           # 借/贷 header row height
ROW_H = 26            # entry row height
ACC_W = 300           # width of one account block
ACC_GAP = 40          # gap between accounts
MIN_ROWS = 2          # keep the T visibly tall even when nearly empty
DEFAULT_ACCENT = "#2f7d72"


def _entries(raw: Any) -> List[Dict[str, str]]:
    if isinstance(raw, (str, dict)):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            text_, amount = item.strip(), ""
        elif isinstance(item, dict):
            text_ = str(item.get("text") or item.get("label")
                        or item.get("name") or "").strip()
            amount = str(item.get("amount") or item.get("value")
                         or item.get("money") or "").strip()
        else:
            continue
        if text_ or amount:
            out.append({"text": text_, "amount": amount})
    return out


def _normalize_accounts(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    accounts = params.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        # allow a single account described at the top level
        if params.get("name") or params.get("debit") or params.get("credit"):
            accounts = [params]
        else:
            return []
    out: List[Dict[str, Any]] = []
    for a in accounts:
        if not isinstance(a, dict):
            continue
        name = str(a.get("name") or a.get("account") or a.get("title") or "").strip()
        debit = _entries(a.get("debit") or a.get("left") or a.get("借"))
        credit = _entries(a.get("credit") or a.get("right") or a.get("贷"))
        if name or debit or credit:
            out.append({"name": name or "账户", "debit": debit, "credit": credit})
    return out


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


@register("t_account")
class TAccountTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        accounts = _normalize_accounts(params)
        if not accounts:
            return svg_document("", width=200, height=80,
                                class_name="diagram t-account")

        accent = str(params.get("accent") or params.get("color")
                     or DEFAULT_ACCENT).strip() or DEFAULT_ACCENT
        title = str(params.get("title") or "").strip()

        rows = max(MIN_ROWS, max(max(len(a["debit"]), len(a["credit"]))
                                 for a in accounts))
        top0 = MARGIN + (TITLE_H if title else 0)
        acc_h = NAME_H + HEAD_H + rows * ROW_H
        n = len(accounts)
        width = MARGIN * 2 + n * ACC_W + (n - 1) * ACC_GAP
        height = top0 + acc_h + MARGIN

        parts: List[str] = [style(self._css(accent))]
        if title:
            parts.append(text(width / 2, MARGIN + 18, title,
                              **{"class": "ta-title", "text-anchor": "middle"}))

        for i, a in enumerate(accounts):
            x = MARGIN + i * (ACC_W + ACC_GAP)
            parts.append(self._account(a, x, top0, rows))
        return svg_document("\n".join(parts), width=width, height=height,
                            class_name="diagram t-account")

    def _account(self, a: Dict[str, Any], x: float, y: float, rows: int) -> str:
        cx = x + ACC_W / 2
        name_y = y + NAME_H
        head_y = name_y + HEAD_H
        bottom = head_y + rows * ROW_H
        inner: List[str] = [
            # account name band
            text(cx, y + 23, _clip(a["name"], 12),
                 **{"class": "ta-name", "text-anchor": "middle"}),
            # the "T": horizontal rule under the name + vertical divider
            line(x, name_y, x + ACC_W, name_y, **{"class": "ta-rule"}),
            line(cx, name_y, cx, bottom, **{"class": "ta-rule"}),
            # 借 / 贷 column headers
            text(x + ACC_W * 0.25, name_y + 19, "借方",
                 **{"class": "ta-head", "text-anchor": "middle"}),
            text(x + ACC_W * 0.75, name_y + 19, "贷方",
                 **{"class": "ta-head", "text-anchor": "middle"}),
        ]
        inner.append(self._side(a["debit"], x + 12, x + ACC_W / 2 - 12, head_y))
        inner.append(self._side(a["credit"], cx + 12, x + ACC_W - 12, head_y))
        return group("\n".join(inner))

    def _side(self, entries: List[Dict[str, str]], left: float, right: float,
              y0: float) -> str:
        out: List[str] = []
        ty = y0 + 18
        for e in entries:
            out.append(text(left, ty, _clip(e["text"], 6),
                            **{"class": "ta-entry"}))
            if e["amount"]:
                out.append(text(right, ty, e["amount"],
                                **{"class": "ta-amount", "text-anchor": "end"}))
            ty += ROW_H
        return "".join(out)

    def _css(self, accent: str) -> str:
        return f"""
.ta-title{{font:600 19px 'Noto Sans SC',sans-serif;fill:#0f172a}}
.ta-name{{font:600 17px 'Noto Sans SC',sans-serif;fill:{accent}}}
.ta-rule{{stroke:#334155;stroke-width:2}}
.ta-head{{font:600 14px 'Noto Sans SC',sans-serif;fill:#64748b}}
.ta-entry{{font:15px 'Noto Sans SC',sans-serif;fill:#1f2937}}
.ta-amount{{font:13px 'Noto Sans SC',sans-serif;fill:#334155}}
"""
