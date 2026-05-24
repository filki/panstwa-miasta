#!/usr/bin/env python3
"""Merge legacy body.landing-page .class rules INTO @utility definitions."""

import re

CSS_PATH = "static/css/theme.css"

with open(CSS_PATH) as f:
    src = f.read()

# ── helpers ───────────────────────────────────────────────────────


def find_brace_pair(s, start):
    """Return pos AFTER matching }. start is just after {."""
    depth = 1
    pos = start
    while pos < len(s) and depth > 0:
        c = s[pos]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        pos += 1
    return pos


def parse_props_and_nested(body):
    """Parse CSS body → (props_dict, nested_rules_list)."""
    props = {}
    nested = []
    lines = body.split("\n")
    current_key = None
    current_val_lines = []
    brace_depth = 0
    in_nested = False
    nested_lines = []
    for line in lines:
        stripped = line.strip()
        bare_before = brace_depth
        if "{" in stripped:
            brace_depth += stripped.count("{")
        if "}" in stripped:
            brace_depth -= stripped.count("}")

        if bare_before == 0 and (stripped.startswith("&") or stripped.startswith("@media")):
            in_nested = True
            nested_lines = [line]
            continue
        if in_nested:
            nested_lines.append(line)
            if brace_depth <= 0:
                nested.append("\n".join(nested_lines))
                nested_lines = []
                in_nested = False
            continue
        if brace_depth > 0:
            continue
        if stripped == "}":
            continue
        if ":" in stripped and not stripped.endswith(","):
            if current_key and current_val_lines:
                val = " ".join(current_val_lines).strip().rstrip(";")
                props[current_key] = val
            key, _, val = stripped.partition(":")
            key = key.strip()
            if key and not key.startswith("//"):
                current_val_lines = [val.strip()]
                current_key = key
            else:
                current_key = None
        elif stripped and not stripped.startswith("//"):
            current_val_lines.append(stripped.rstrip(";"))
    if current_key and current_val_lines:
        val = " ".join(current_val_lines).strip().rstrip(";")
        props[current_key] = val
    return props, nested


def format_props(props, indent="    "):
    """Format props to CSS body lines."""
    return "\n".join(f"{indent}{k}: {v};" for k, v in props.items())


# ── Step 0: join multi-line selectors ─────────────────────────────
src = re.sub(r"(body\.landing-page)\s*\n\s*", r"\1 ", src)
src = re.sub(r"(body\.room-page)\s*\n\s*", r"\1 ", src)

# ── Step 1: collect all @utility definitions ──────────────────────
pat_utility = re.compile(r"^@utility\s+([\w-]+)\s*\{", re.MULTILINE)
utilities = {}  # name → (start, end_after_}, body, match)

for m in pat_utility.finditer(src):
    name = m.group(1)
    body_end = find_brace_pair(src, m.end())
    body = src[m.end() : body_end - 1]
    utilities[name] = (m.start(), body_end, body, m)

# ── Step 2: find body.landing-page .CLASS { } selectors ──────────
pat_legacy = re.compile(r"body\.landing-page\s+\.([\w-]+)\s*\{", re.MULTILINE)
merges = {}  # utility_name → [legacy_body_texts]

for m in pat_legacy.finditer(src):
    name = m.group(1)
    if name not in utilities:
        continue
    leg_end = find_brace_pair(src, m.end())
    leg_body = src[m.end() : leg_end - 1]
    merges.setdefault(name, []).append(leg_body)

# ── Step 3: update @utility bodies (process REVERSE for offset safety) ──
sorted_names = sorted(merges, key=lambda n: -utilities[n][0])
for name in sorted_names:
    util_start, util_end, util_body, m = utilities[name]
    util_props, util_nested = parse_props_and_nested(util_body)
    for leg_body in merges[name]:
        leg_props, _ = parse_props_and_nested(leg_body)
        util_props.update(leg_props)  # legacy wins conflicts

    new_lines = [format_props(util_props)]
    for n in util_nested:
        new_lines.append("")
        new_lines.append(n)
    new_body = "\n".join(new_lines).rstrip()

    # Replace body between { and }
    body_start = m.end()
    body_end = util_end - 1  # pos of }
    src = src[:body_start] + "\n" + new_body + "\n" + src[body_end:]

# ── Step 4: delete merged legacy blocks (re-collect + reverse delete) ──
pat2 = re.compile(r"body\.landing-page\s+\.([\w-]+)\s*\{", re.MULTILINE)
to_delete = []
for m in pat2.finditer(src):
    name = m.group(1)
    if name not in utilities:
        continue
    leg_end = find_brace_pair(src, m.end())
    to_delete.append((m.start(), leg_end))

for start, end in sorted(to_delete, reverse=True):
    while start > 0 and src[start - 1] in " \n\t":
        start -= 1
    src = src[:start] + src[end:]

# ── Step 5: clean up remaining body.landing-page ──────────────────
src = re.sub(r"\bbody\.landing-page\.", ".", src)
src = re.sub(r"\bbody\.landing-page\s+(?!\{)", "", src)
src = re.sub(r"\bbody\.landing-page\b", ".landing-page", src)

# ── Step 6: body.room-page → .room-page ──────────────────────────
src = re.sub(r"\bbody\.room-page\b", ".room-page", src)

# ── Step 7: clean empty lines ─────────────────────────────────────
src = re.sub(r"\n{3,}", "\n\n", src)

with open(CSS_PATH, "w") as f:
    f.write(src)

print(f"Merged {len(merges)} utilities into @utility blocks. Run: npm run css:build")
