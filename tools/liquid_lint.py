#!/usr/bin/env python3
"""
Structural validator for Shopify Liquid files.

Checks that every block tag is opened/closed in the right order and that
{% liquid %} tags have matching internal directives. Catches the class of
typos that makes Shopify reject a theme file with a Liquid error.

Usage: python3 tools/liquid_lint.py <file-or-dir> ...
"""
import re
import sys
import os

TAG_RE = re.compile(r"{%-?\s*(.*?)\s*-?%}", re.DOTALL)
OUTPUT_RE = re.compile(r"{{-?\s*(.*?)\s*-?}}", re.DOTALL)

BLOCK_OPEN = {
    "if": "endif",
    "unless": "endunless",
    "for": "endfor",
    "case": "endcase",
    "capture": "endcapture",
    "comment": "endcomment",
    "form": "endform",
    "tablerow": "endtablerow",
    "paginate": "endpaginate",
    "style": "endstyle",
    "javascript": "endjavascript",
    "schema": "endschema",
    "raw": "endraw",
}
CLOSE_TO_OPEN = {v: k for k, v in BLOCK_OPEN.items()}

# words that may appear mid-block without changing depth
MIDDLE = {"else", "elsif", "when"}

LIQUID_KEYWORDS = set(BLOCK_OPEN) | set(CLOSE_TO_OPEN) | MIDDLE


def first_word(text):
    return text.split(None, 1)[0] if text.strip() else ""


def strip_liquid_comments(body):
    """Remove `# ...` comments from a {% liquid %} body (not from normal tags)."""
    out = []
    for line in body.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # inline trailing comment – only when '#' is outside quotes
        out.append(drop_inline_comment(line))
    return "\n".join(out)


def drop_inline_comment(line):
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


def directives_from_liquid(body):
    """A {% liquid %} block holds one directive per line."""
    body = strip_liquid_comments(body)
    dirs = []
    for raw_line in body.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        word = first_word(line)
        if word in LIQUID_KEYWORDS:
            dirs.append(word)
    return dirs


def check_file(path):
    src = open(path, encoding="utf-8").read()

    # Schema JSON is not Liquid — remove it so braces there don't confuse us.
    src_no_schema = re.sub(
        r"{%-?\s*schema\s*-?%}.*?{%-?\s*endschema\s*-?%}", "", src, flags=re.DOTALL
    )

    errors = []
    stack = []  # (keyword, line_no)

    def lineno(pos):
        return src_no_schema.count("\n", 0, pos) + 1

    # ---- walk normal {% %} tags -------------------------------------------
    for m in TAG_RE.finditer(src_no_schema):
        body = m.group(1)
        word = first_word(body)

        if word == "liquid":
            for d in directives_from_liquid(body):
                push_pop(d, stack, errors, lineno(m.start()), inside_liquid=True)
            continue

        if word in BLOCK_OPEN:
            stack.append((word, lineno(m.start())))
        elif word in CLOSE_TO_OPEN:
            expected_open = CLOSE_TO_OPEN[word]
            if not stack:
                errors.append(f"L{lineno(m.start())}: stray {{% {word} %}}")
            elif stack[-1][0] != expected_open:
                errors.append(
                    f"L{lineno(m.start())}: {{% {word} %}} closes "
                    f"{{% {stack[-1][0]} %}} opened at L{stack[-1][1]}"
                )
                # try to recover
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i][0] == expected_open:
                        del stack[i:]
                        break
            else:
                stack.pop()

    for kw, ln in stack:
        errors.append(f"L{ln}: unclosed {{% {kw} %}}")

    # ---- raw {% ... %} that Shopify doesn't know ---------------------------
    for m in TAG_RE.finditer(src_no_schema):
        word = first_word(m.group(1))
        if word == "liquid":
            continue

    # ---- output tag sanity --------------------------------------------------
    for m in OUTPUT_RE.finditer(src_no_schema):
        expr = m.group(1)
        if expr.count("'") % 2 or expr.count('"') % 2:
            errors.append(f"L{lineno(m.start())}: unbalanced quote in {{{{ {expr[:60]} }}}}")

    return errors


def push_pop(word, stack, errors, line, inside_liquid=False):
    if word in BLOCK_OPEN:
        stack.append((word, line))
    elif word in CLOSE_TO_OPEN:
        expected = CLOSE_TO_OPEN[word]
        if not stack:
            errors.append(f"L{line}: stray '{word}' inside liquid tag")
        elif stack[-1][0] != expected:
            errors.append(
                f"L{line}: '{word}' inside liquid tag closes "
                f"'{stack[-1][0]}' opened at L{stack[-1][1]}"
            )
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == expected:
                    del stack[i:]
                    break
        else:
            stack.pop()


def main(argv):
    targets = argv[1:] or ["."]
    files = []
    for t in targets:
        if os.path.isdir(t):
            for root, _, names in os.walk(t):
                for n in names:
                    if n.endswith(".liquid"):
                        files.append(os.path.join(root, n))
        else:
            files.append(t)

    bad = 0
    for f in sorted(files):
        errs = check_file(f)
        if errs:
            bad += 1
            print(f"✗ {f}")
            for e in errs:
                print(f"    {e}")
    print(f"\n{len(files)} file(s) checked, {bad} with problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
