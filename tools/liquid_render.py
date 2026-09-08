#!/usr/bin/env python3
"""
Minimal Shopify-Liquid renderer — test harness only.
=====================================================
Implements the subset of Liquid that Dew's snippets use, with Shopify's real
semantics for the things that bite:

  * only `nil` and `false` are falsy (an empty string is TRUTHY)
  * `blank` / `empty` mean nil, false, "", [] or {}
  * `{% render %}` has an ISOLATED scope — only explicitly passed params exist
  * `forloop.index / index0 / first / last / length`
  * `{% liquid %}` blocks: one directive per line, `#` comments
  * whitespace control `{%-` / `-%}`
  * no auto-escaping (Shopify does not escape `{{ }}`)

It exists so tools/test-dews-spec-block.py can render the real snippet files and
assert on real output. It is deliberately NOT a full Liquid implementation.
"""
import json
import re
import html as _html

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

class Blank:
    """Sentinel for Liquid's `blank` / `empty`."""
    def __repr__(self):
        return "blank"


BLANK = Blank()


def is_blank(v):
    if v is None or v is False:
        return True
    if isinstance(v, Blank):
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, tuple, dict, set)):
        return len(v) == 0
    return False


def truthy(v):
    """Liquid: everything except nil and false is truthy."""
    return not (v is None or v is False)


def to_s(v):
    if v is None or v is False:
        return ""
    if v is True:
        return "true"
    if isinstance(v, Blank):
        return ""
    if isinstance(v, float):
        if v == int(v):
            return str(int(v))
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "".join(to_s(x) for x in v)
    if isinstance(v, dict):
        return "".join(to_s(x) for x in v.values())
    return str(v)


class Metafield:
    """Stand-in for Shopify's metafield drop."""

    def __init__(self, value, mf_type="single_line_text_field", key="", namespace="custom"):
        self.value = value
        self.type = mf_type
        self.key = key
        self.namespace = namespace

    def __bool__(self):
        return True

    def __repr__(self):
        return f"Metafield({self.value!r},{self.type!r})"


class Metafields:
    """namespace -> key -> Metafield. Missing lookups return None (never raise)."""

    def __init__(self, data=None):
        self._data = data or {}

    def get_ns(self, ns):
        return self._data.get(ns)

    def __repr__(self):
        return f"Metafields({list(self._data)})"


class Drop(dict):
    """dict that also exposes keys as attributes and returns None when missing."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self.get(name)


# --------------------------------------------------------------------------
# filters
# --------------------------------------------------------------------------

def _f_default(v, arg=None, *rest):
    if is_blank(v):
        return arg
    return v


def _f_split(v, sep):
    return to_s(v).split(to_s(sep))


def _f_join(v, sep=""):
    if not isinstance(v, (list, tuple)):
        return to_s(v)
    return to_s(sep).join(to_s(x) for x in v)


def _f_json(v):
    if v is None or isinstance(v, Blank):
        return "null"
    if isinstance(v, Metafield):
        # Shopify would emit an object here — exactly the bug we removed.
        return json.dumps({"type": v.type, "value": to_s(v.value)})
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (list, tuple)):
        return json.dumps([_jsonable(x) for x in v])
    if isinstance(v, dict):
        return json.dumps({to_s(k): _jsonable(x) for k, x in v.items()})
    if isinstance(v, (int, float)):
        return json.dumps(v)
    return json.dumps(to_s(v))


def _jsonable(v):
    if v is None or isinstance(v, Blank):
        return None
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {to_s(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    return to_s(v)


def _f_newline_to_br(v):
    return to_s(v).replace("\r\n", "\n").replace("\n", "<br />\n")


def _f_strip_html(v):
    return re.sub(r"<[^>]*>", "", to_s(v))


def _f_escape(v):
    return _html.escape(to_s(v), quote=True)


def _f_capitalize(v):
    s = to_s(v)
    return s[:1].upper() + s[1:]


def _f_remove_first(v, needle):
    s, n = to_s(v), to_s(needle)
    if not n:
        return s
    i = s.find(n)
    return s if i < 0 else s[:i] + s[i + len(n):]


def _f_replace_first(v, a, b=""):
    s = to_s(v)
    return s.replace(to_s(a), to_s(b), 1)


def _f_size(v):
    if isinstance(v, (list, tuple, dict, str)):
        return len(v)
    return 0


def _f_map(v, prop):
    if not isinstance(v, (list, tuple)):
        return []
    return [resolve_property(x, to_s(prop)) for x in v]


def _f_compact(v):
    return [x for x in v if x is not None] if isinstance(v, (list, tuple)) else v


def _f_date(v, fmt="%d %b %Y"):
    return to_s(v)


FILTERS = {
    "default": _f_default,
    "strip": lambda v: to_s(v).strip(),
    "lstrip": lambda v: to_s(v).lstrip(),
    "rstrip": lambda v: to_s(v).rstrip(),
    "downcase": lambda v: to_s(v).lower(),
    "upcase": lambda v: to_s(v).upper(),
    "capitalize": _f_capitalize,
    "split": _f_split,
    "join": _f_join,
    "append": lambda v, a="": to_s(v) + to_s(a),
    "prepend": lambda v, a="": to_s(a) + to_s(v),
    "remove": lambda v, a: to_s(v).replace(to_s(a), ""),
    "remove_first": _f_remove_first,
    "replace": lambda v, a, b="": to_s(v).replace(to_s(a), to_s(b)),
    "replace_first": _f_replace_first,
    "escape": _f_escape,
    "escape_once": _f_escape,
    "json": _f_json,
    "newline_to_br": _f_newline_to_br,
    "strip_newlines": lambda v: to_s(v).replace("\n", "").replace("\r", ""),
    "strip_html": _f_strip_html,
    "size": _f_size,
    "first": lambda v: (v[0] if isinstance(v, (list, tuple)) and v else None),
    "last": lambda v: (v[-1] if isinstance(v, (list, tuple)) and v else None),
    "map": _f_map,
    "compact": _f_compact,
    "reverse": lambda v: list(reversed(v)) if isinstance(v, (list, tuple)) else to_s(v)[::-1],
    "uniq": lambda v: list(dict.fromkeys(v)) if isinstance(v, (list, tuple)) else v,
    "sort": lambda v: sorted(v, key=to_s) if isinstance(v, (list, tuple)) else v,
    "date": _f_date,
    "times": lambda v, a: _num(v) * _num(a),
    "plus": lambda v, a: _num(v) + _num(a),
    "minus": lambda v, a: _num(v) - _num(a),
    "round": lambda v, a=0: round(_num(v), int(_num(a))),
    "abs": lambda v: abs(_num(v)),
    "truncate": lambda v, n=50, s="...": to_s(v)[: int(_num(n))] + (s if len(to_s(v)) > int(_num(n)) else ""),
    "money": lambda v: to_s(v),
    "money_with_currency": lambda v: to_s(v),
}


def _num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------
# tokenizer
# --------------------------------------------------------------------------

TOKEN_RE = re.compile(r"({%-?.*?-?%}|{{-?.*?-?}})", re.DOTALL)


class TextNode:
    def __init__(self, text):
        self.text = text


class OutputNode:
    def __init__(self, expr):
        self.expr = expr


class TagNode:
    def __init__(self, name, args, body=None, branches=None):
        self.name = name
        self.args = args
        self.body = body if body is not None else []
        self.branches = branches or []  # [(condition_src|None, nodes)]


def tokenize(src):
    """Turn a template into a flat list of nodes (no nesting yet)."""
    nodes = []
    pos = 0
    for m in TOKEN_RE.finditer(src):
        pre = src[pos:m.start()]
        if pre:
            nodes.append(("text", pre))
        tok = m.group(0)
        if tok.startswith("{{"):
            inner = tok[2:-2]
            strip_l = inner.startswith("-")
            strip_r = inner.endswith("-")
            inner = _trim_dash(inner)
            nodes.append(("output", inner, strip_l, strip_r))
        else:
            inner = tok[2:-2]
            strip_l = inner.startswith("-")
            strip_r = inner.endswith("-")
            inner = _trim_dash(inner)
            parts = inner.split(None, 1)
            name = parts[0] if parts else ""
            args = parts[1].strip() if len(parts) > 1 else ""
            nodes.append(("tag", name, args, strip_l, strip_r))
        pos = m.end()
    if pos < len(src):
        nodes.append(("text", src[pos:]))

    # apply whitespace control
    out = []
    for i, n in enumerate(nodes):
        if n[0] == "text":
            out.append(n)
            continue
        strip_l = n[-2]
        strip_r = n[-1]
        if strip_l and out and out[-1][0] == "text":
            out[-1] = ("text", out[-1][1].rstrip())
        if strip_r and i + 1 < len(nodes) and nodes[i + 1][0] == "text":
            nodes[i + 1] = ("text", nodes[i + 1][1].lstrip())
        out.append(n)
    return out


def _trim_dash(inner):
    """Remove the optional leading/trailing `-` whitespace-control markers."""
    inner = inner.strip()
    if inner.startswith("-"):
        inner = inner[1:]
    if inner.endswith("-"):
        inner = inner[:-1]
    return inner.strip()


BLOCK_TAGS = {"if", "unless", "for", "case", "capture", "comment", "form", "paginate", "raw"}
END_TAGS = {
    "endif": "if", "endunless": "unless", "endfor": "for", "endcase": "case",
    "endcapture": "capture", "endcomment": "comment", "endform": "form",
    "endpaginate": "paginate", "endraw": "raw",
}
MID_TAGS = {"else", "elsif", "when"}


def parse(flat):
    """flat list -> nested node tree."""
    root, _, _ = _parse_until(flat, 0, None)
    return root


def _parse_until(flat, i, terminators):
    nodes = []
    while i < len(flat):
        n = flat[i]
        if n[0] == "text":
            nodes.append(TextNode(n[1]))
            i += 1
            continue
        if n[0] == "output":
            nodes.append(OutputNode(n[1]))
            i += 1
            continue

        _, name, args = n[0], n[1], n[2]

        if terminators and name in terminators:
            return nodes, i, name

        if name in END_TAGS:
            raise SyntaxError(f"unexpected {{% {name} %}}")

        if name in BLOCK_TAGS:
            args_for_first = args
            i += 1
            if name == "raw":
                buf = []
                while i < len(flat) and not (flat[i][0] == "tag" and flat[i][1] == "endraw"):
                    buf.append(flat[i])
                    i += 1
                i += 1
                nodes.append(TextNode("".join(_flat_text(b) for b in buf)))
                continue

            sub, i, ended = _parse_until(flat, i, {"end" + name} | MID_TAGS)
            # branches[0] carries the opening condition (if/unless) or the
            # case subject; every later entry is an elsif/when/else branch.
            branches = [(args_for_first, sub)]
            while ended in MID_TAGS:
                mid_name = flat[i][1]
                mid_args = flat[i][2]
                i += 1
                sub2, i, ended = _parse_until(flat, i, {"end" + name} | MID_TAGS)
                branches.append((None if mid_name == "else" else mid_args, sub2))
            if ended != "end" + name:
                raise SyntaxError(f"unclosed {{% {name} %}} (got {ended})")
            i += 1
            nodes.append(TagNode(name, args, branches=branches))
            continue

        if name == "liquid":
            i += 1
            sub_flat = _liquid_block_to_flat(args)
            sub = parse(sub_flat)
            nodes.append(TagNode("liquidgroup", "", body=sub))
            continue

        nodes.append(TagNode(name, args))
        i += 1

    if terminators:
        return nodes, i, None
    return nodes, i, None


def _flat_text(n):
    if n[0] == "text":
        return n[1]
    if n[0] == "output":
        return "{{ " + n[1] + " }}"
    return "{% " + n[1] + " " + n[2] + " %}"


def _liquid_block_to_flat(body):
    """Expand a {% liquid %} body into the same flat node tuples."""
    out = []
    for raw_line in body.split("\n"):
        line = _drop_comment(raw_line).strip()
        if not line:
            continue
        parts = line.split(None, 1)
        name = parts[0]
        args = parts[1].strip() if len(parts) > 1 else ""
        out.append(("tag", name, args, False, False))
    return out


def _drop_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and not quote:
            return line[:i]
    return line


# --------------------------------------------------------------------------
# expressions
# --------------------------------------------------------------------------

STR_RE = re.compile(r"""^"((?:[^"\\]|\\.)*)$|^'((?:[^'\\]|\\.)*)'$""", re.DOTALL)


def split_top(s, sep=","):
    """Split on a separator that is not inside quotes or brackets."""
    parts, buf, quote, depth = [], "", None, 0
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            buf += ch
            continue
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p.strip() for p in parts]


def split_filters(expr):
    """'a | f: x | g' -> ('a', [('f',['x']), ('g',[])]) respecting quotes."""
    parts = split_top(expr, "|")
    base = parts[0]
    filters = []
    for p in parts[1:]:
        if not p:
            continue
        seg = split_top(p, ":")
        name = seg[0].strip()
        argstr = ":".join(seg[1:])          # a named arg may itself contain ':'
        args = [a.strip() for a in split_top(argstr, ",") if a.strip() != ""]
        filters.append((name, args))
    return base, filters


PATH_TOKEN_RE = re.compile(r"\.([A-Za-z_][\w\-?!]*)|\[\s*([^\]]+?)\s*\]")


def parse_path(base):
    """'a.b[c].d' -> ('a', ['b', ('expr','c'), 'd'])"""
    m = re.match(r"^\s*([A-Za-z_][\w\-?!]*)", base)
    if not m:
        return None, []
    root = m.group(1)
    steps = []
    for dm, expr in PATH_TOKEN_RE.findall(base[m.end():]):
        if dm:
            steps.append(dm)
        else:
            steps.append(("expr", expr.strip()))
    return root, steps


def resolve_property(obj, prop):
    if obj is None:
        return None
    if isinstance(obj, Metafield):
        return getattr(obj, prop, None)
    if isinstance(obj, Metafields):
        return obj.get_ns(prop)
    if isinstance(obj, dict):
        if prop in obj:
            return obj[prop]
        if prop == "size":
            return len(obj)
        if prop == "first":
            return next(iter(obj.values()), None)
        if prop == "last":
            return list(obj.values())[-1] if obj else None
        return None
    if isinstance(obj, (list, tuple)):
        if prop == "size":
            return len(obj)
        if prop == "first":
            return obj[0] if obj else None
        if prop == "last":
            return obj[-1] if obj else None
        try:
            return obj[int(prop)]
        except (ValueError, IndexError):
            return None
    if isinstance(obj, str):
        if prop == "size":
            return len(obj)
        return None
    return getattr(obj, prop, None)


def lookup(ctx, base):
    base = base.strip()
    if base in ("nil", "null"):
        return None
    if base == "true":
        return True
    if base == "false":
        return False
    if base in ("blank", "empty"):
        return BLANK
    m = STR_RE.match(base)
    if m:
        s = m.group(1) if m.group(1) is not None else m.group(2)
        return s.replace('\\"', '"').replace("\\'", "'")
    if re.match(r"^-?\d+$", base):
        return int(base)
    if re.match(r"^-?\d*\.\d+$", base):
        return float(base)

    root, steps = parse_path(base)
    if root is None:
        return None
    val = ctx.get(root)
    for st in steps:
        if isinstance(st, tuple):  # bracket access -> evaluate the inner expr
            key = lookup(ctx, st[1])
            val = resolve_property(val, to_s(key))
        else:
            val = resolve_property(val, st)
    return val


def eval_expr(ctx, expr):
    expr = expr.strip()
    base, filters = split_filters(expr)
    val = lookup(ctx, base)
    for name, raw_args in filters:
        args = [lookup(ctx, a) for a in raw_args]
        fn = FILTERS.get(name)
        if fn is None:
            raise NotImplementedError(f"filter not implemented: {name}")
        val = fn(val, *args)
    return val


CMP_RE = re.compile(r"\s*(==|!=|<>|<=|>=|<|>|contains)\s*")


def split_conditions(src):
    """Split on top-level `and` / `or`, keeping the operator."""
    tokens = re.split(r"\s+(and|or)\s+", src.strip())
    return tokens  # [cond, op, cond, op, cond...]


def eval_condition(ctx, src):
    src = src.strip()
    if not src:
        return True
    tokens = split_conditions(src)
    result = eval_one_condition(ctx, tokens[0])
    i = 1
    while i < len(tokens):
        op = tokens[i]
        nxt = eval_one_condition(ctx, tokens[i + 1])
        result = (result and nxt) if op == "and" else (result or nxt)
        i += 2
    return result


def eval_one_condition(ctx, src):
    src = src.strip()
    parts = CMP_RE.split(src)
    if len(parts) == 1:
        return truthy(eval_expr(ctx, parts[0]))
    left, op, right_src = parts[0], parts[1], parts[2]
    left_v = eval_expr(ctx, left)
    right_v = eval_expr(ctx, right_src)

    if isinstance(right_v, Blank) or isinstance(left_v, Blank):
        if op in ("==",):
            return is_blank(left_v) if isinstance(right_v, Blank) else is_blank(right_v)
        if op in ("!=", "<>"):
            return not (is_blank(left_v) if isinstance(right_v, Blank) else is_blank(right_v))

    if op == "contains":
        if isinstance(left_v, (list, tuple)):
            return right_v in left_v
        return to_s(right_v) in to_s(left_v)
    if op == "==":
        return _loose_eq(left_v, right_v)
    if op in ("!=", "<>"):
        return not _loose_eq(left_v, right_v)

    ln, rn = _num(left_v), _num(right_v)
    return {"<": ln < rn, ">": ln > rn, "<=": ln <= rn, ">=": ln >= rn}[op]


def _loose_eq(a, b):
    if isinstance(a, Metafield) or isinstance(b, Metafield):
        return False
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return to_s(a) == to_s(b)


# --------------------------------------------------------------------------
# renderer
# --------------------------------------------------------------------------

class LiquidError(Exception):
    pass


class Renderer:
    def __init__(self, snippet_dirs, strict=True):
        self.snippet_dirs = snippet_dirs
        self.strict = strict
        self.errors = []

    # -- entry ---------------------------------------------------------
    def render_file(self, name, ctx):
        path = None
        for d in self.snippet_dirs:
            cand = f"{d}/{name}.liquid"
            import os
            if os.path.exists(cand):
                path = cand
                break
        if path is None:
            raise LiquidError(f"snippet not found: {name}")
        src = open(path, encoding="utf-8").read()
        return self.render_string(src, ctx)

    def render_string(self, src, ctx):
        nodes = parse(tokenize(src))
        out, _ = self._render_nodes(nodes, dict(ctx), None)
        return "".join(out)

    # -- core ----------------------------------------------------------
    def _render_nodes(self, nodes, ctx, loop_ctx):
        out = []
        for n in nodes:
            if isinstance(n, TextNode):
                out.append(n.text)
            elif isinstance(n, OutputNode):
                val = eval_expr(ctx, n.expr)
                if isinstance(val, Metafield):
                    # Shopify prints a metafield object as its value
                    val = val.value
                out.append(to_s(val))
            elif isinstance(n, TagNode):
                out.append(self._render_tag(n, ctx))
        return out, ctx

    def _render_tag(self, node, ctx):
        name = node.name

        if name == "liquidgroup":
            text, _ = self._render_nodes(node.body, ctx, None)
            return "".join(text)

        if name == "assign":
            self._do_assign(node.args, ctx)
            return ""

        if name == "echo":
            val = eval_expr(ctx, node.args)
            return to_s(val.value if isinstance(val, Metafield) else val)

        if name == "increment" or name == "decrement":
            return "0"

        if name == "capture":
            varname = node.args.strip()
            inner, _ = self._render_nodes(node.branches[0][1], ctx, None)
            ctx[varname] = "".join(inner)
            return ""

        if name == "comment":
            return ""

        if name == "if" or name == "unless":
            return self._do_if(node, ctx)

        if name == "case":
            return self._do_case(node, ctx)

        if name == "for":
            return self._do_for(node, ctx)

        if name == "cycle":
            return ""

        if name == "render" or name == "include":
            return self._do_render(node, ctx)

        if name in ("break", "continue"):
            raise _LoopSignal(name)

        if self.strict:
            raise LiquidError(f"unsupported tag: {{% {name} {node.args} %}}")
        return ""

    # -- individual tags ------------------------------------------------
    ASSIGN_RE = re.compile(r"^([A-Za-z_][\w\-]*)\s*=\s*(.*)$", re.DOTALL)

    def _do_assign(self, args, ctx):
        m = self.ASSIGN_RE.match(args.strip())
        if not m:
            raise LiquidError(f"bad assign: {args!r}")
        ctx[m.group(1)] = eval_expr(ctx, m.group(2))
        return ""

    def _do_if(self, node, ctx):
        negated = node.name == "unless"
        for i, (cond, body) in enumerate(node.branches):
            if i == 0:
                take = eval_condition(ctx, cond)
                if negated:
                    take = not take
            elif cond is None:  # else
                take = True
            else:  # elsif — only legal for `if`
                take = eval_condition(ctx, cond)
            if take:
                text, _ = self._render_nodes(body, ctx, None)
                return "".join(text)
        return ""

    def _do_case(self, node, ctx):
        subject = eval_expr(ctx, node.args)
        # branches[0] is the (normally empty) body between `case` and the first
        # `when`; its slot holds the subject expression, so it is skipped here.
        for cond, body in node.branches[1:]:
            if cond is None:  # else
                text, _ = self._render_nodes(body, ctx, None)
                return "".join(text)
            for opt in split_top(cond):
                if opt and _loose_eq(subject, eval_expr(ctx, opt)):
                    text, _ = self._render_nodes(body, ctx, None)
                    return "".join(text)
        return ""

    FOR_RE = re.compile(r"^([A-Za-z_][\w\-]*)\s+in\s+(.+?)(?:\s+limit\s*:\s*(\S+))?$", re.DOTALL)

    def _do_for(self, node, ctx):
        m = self.FOR_RE.match(node.args.strip())
        if not m:
            raise LiquidError(f"bad for: {node.args!r}")
        varname, coll_src = m.group(1), m.group(2)
        coll = eval_expr(ctx, coll_src)
        if coll is None or isinstance(coll, Blank):
            coll = []
        if isinstance(coll, str):
            coll = list(coll)
        if isinstance(coll, dict):
            coll = list(coll.items())
        if not isinstance(coll, (list, tuple)):
            coll = []

        body = node.branches[0][1]
        else_body = None
        for cond, b in node.branches[1:]:
            if cond is None:
                else_body = b

        if not coll:
            if else_body:
                text, _ = self._render_nodes(else_body, ctx, None)
                return "".join(text)
            return ""

        out = []
        n = len(coll)
        for idx, item in enumerate(coll):
            ctx[varname] = item
            ctx["forloop"] = Drop({
                "index": idx + 1, "index0": idx, "length": n,
                "first": idx == 0, "last": idx == n - 1,
                "rindex": n - idx, "rindex0": n - idx - 1,
            })
            try:
                text, _ = self._render_nodes(body, ctx, None)
                out.append("".join(text))
            except _LoopSignal as sig:
                if sig.name == "break":
                    break
                continue
        ctx.pop("forloop", None)
        return "".join(out)

    RENDER_RE = re.compile(r"""^['"]([\w\-\./]+)['"](.*)$""", re.DOTALL)

    def _do_render(self, node, ctx):
        m = self.RENDER_RE.match(node.args.strip())
        if not m:
            # {% render block %} — theme app extension, not needed here
            return ""
        snippet, rest = m.group(1), m.group(2).strip()
        sub_ctx = {}
        if rest.startswith(","):
            rest = rest[1:]
        if rest:
            for part in split_top(rest):
                if not part:
                    continue
                if ":" in part:
                    k, v = part.split(":", 1)
                    sub_ctx[k.strip()] = eval_expr(ctx, v.strip())
                else:
                    v = eval_expr(ctx, part)
                    sub_ctx[part.strip()] = v
        # `with` / `for` forms
        return self.render_file(snippet, sub_ctx)


class _LoopSignal(Exception):
    def __init__(self, name):
        self.name = name
