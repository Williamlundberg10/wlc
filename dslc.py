import os, re, sys

# Simple DSL compiler for HTML-like pages.
# Language rules:
# - Syntax looks JavaScript-like: Name(prop("value"); ...)
# - Properties are key("value").
# - Tags must not contain other tags (no nested tags). If a child name followed by '(' is encountered inside an element, the parser raises a SyntaxError.


plugin_registry = {}
plugin_metadata = []

# ---------------------------
# Plugin Loader
# ---------------------------
def load_plugin_file(path):
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    # Metadata
    meta_matches = re.findall(r'(\w+)\(\"(.*?)\"\)', code)
    meta = {}
    for k, v in meta_matches:
        if k in ["name","author","version","description"]:
            meta[k] = v
    if meta:
        plugin_metadata.append(meta)

    # Define blocks: find 'define Name(' and extract the block by matching parentheses
    for m in re.finditer(r'define\s+(\w+)\s*\(', code):
        name = m.group(1)
        start = m.end()  # position after '('
        depth = 1
        i = start
        while i < len(code) and depth > 0:
            if code[i] == '(':
                depth += 1
            elif code[i] == ')':
                depth -= 1
            i += 1
        block = code[start:i-1]

        tag_match = re.search(r'tag\("(.*?)"\)', block)
        content_match = re.search(r'content\("(.*?)"\)', block, re.S)
        selfclosing_match = re.search(r'selfclosing\("(.*?)"\)', block)
        attrs = re.findall(r'attr\("(.*?)"\)', block)
        # allow/deny parsing: can contain multiple quoted values separated by commas
        def _parse_list(inner: str):
            if not inner:
                return []
            return [s.strip() for s in re.findall(r'"(.*?)"', inner)]
        allow_children_match = re.search(r'allow_children\((.*?)\)', block, re.S)
        allow_attrs_match = re.search(r'allow_attrs\((.*?)\)', block, re.S)
        deny_attrs_match = re.search(r'deny_attrs\((.*?)\)', block, re.S)
        default_css_match = re.search(r'default_css\("(.*?)"\)', block, re.S)
        default_script_match = re.search(r'default_script\("(.*?)"\)', block, re.S)

        # helper to unescape escaped sequences (e.g. \n -> newline)
        def _unescape(s: str) -> str:
            try:
                return bytes(s, "utf-8").decode("unicode_escape")
            except Exception:
                return s

        plugin_registry[name.lower()] = {
            "tag": tag_match.group(1) if tag_match else name.lower(),
            "content": content_match.group(1) if content_match else "{{text}}",
            "selfclosing": selfclosing_match.group(1) == "true" if selfclosing_match else False,
            "attrs": attrs,
            "default_css": _unescape(default_css_match.group(1)) if default_css_match else "",
            "default_script": _unescape(default_script_match.group(1)) if default_script_match else "",
            "allow_children": _parse_list(allow_children_match.group(1)) if allow_children_match else [],
            "allow_attrs": _parse_list(allow_attrs_match.group(1)) if allow_attrs_match else [],
            "deny_attrs": _parse_list(deny_attrs_match.group(1)) if deny_attrs_match else []
        }

def load_plugins(folder="plugins"):
    if not os.path.exists(folder):
        os.makedirs(folder)

    default_plugin = os.path.join(folder, "default.box")
    if os.path.exists(default_plugin):
        load_plugin_file(default_plugin)

    for filename in os.listdir(folder):
        if filename.endswith(".box") and filename != "default.box":
            load_plugin_file(os.path.join(folder, filename))

    print("Loaded plugins:")
    for p in plugin_metadata:
        print(f"- {p['name']} v{p['version']} by {p['author']}")

# ---------------------------
# Tokenizer
# ---------------------------
def tokenize(code):
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|\(|\)|\".*?\"|;|>', code)
    return tokens

# ---------------------------
# Recursive Parser
# ---------------------------
def parse(tokens):
    pos = 0

    def parse_element():
        nonlocal pos
        if pos >= len(tokens):
            return None

        name = tokens[pos]
        pos += 1

        props = []
        children = []

        if pos < len(tokens) and tokens[pos] == "(":
            pos += 1
            while pos < len(tokens) and tokens[pos] != ")":
                if re.match(r'[A-Za-z_][A-Za-z0-9_]*', tokens[pos]):
                    key = tokens[pos]
                    # If next token is '(' we need to decide whether this is a simple property
                    # like key("value") or a nested child element like Name(...).
                    if pos + 1 < len(tokens) and tokens[pos + 1] == "(":
                        # look ahead: if token after '(' is a quoted string, it's a property
                        if pos + 2 < len(tokens) and isinstance(tokens[pos + 2], str) and tokens[pos + 2].startswith('"'):
                            # property
                            pos += 2  # move to the value token
                            value = tokens[pos].strip('"')
                            pos += 1
                            # consume closing ')'
                            if pos < len(tokens) and tokens[pos] == ")":
                                pos += 1
                            props.append((key, value))
                            if pos < len(tokens) and tokens[pos] == ";":
                                pos += 1
                        else:
                            # Treat as a nested child element (allow nesting)
                            child = parse_element()
                            if child:
                                children.append(child)
                            if pos < len(tokens) and tokens[pos] == ";":
                                pos += 1
                    else:
                        # malformed or unexpected token sequence; try to parse as child
                        child = parse_element()
                        if child:
                            children.append(child)
                        if pos < len(tokens) and tokens[pos] == ";":
                            pos += 1
                elif tokens[pos] == ";":
                    pos += 1
                else:
                    pos += 1
            pos += 1  # skip ')'

        return {"name": name, "props": props, "children": children}

    elements = []
    while pos < len(tokens):
        elem = parse_element()
        if elem:
            elements.append(elem)
    return elements

# ---------------------------
# Compiler
# ---------------------------
def compile_element(element, indent=0):
    """Compile an element to pretty HTML with indentation."""
    pad = "  " * indent
    name = element["name"].lower()
    props_dict = dict(element["props"])

    # raw children from AST
    raw_children = element["children"]
    children_html_inner = ""

    if name in plugin_registry:
        info = plugin_registry[name]
        tag = info["tag"]
        content_template = info["content"]
        # If plugin provides default_css and declares 'class' as an allowed attr,
        # auto-assign a default class (plugin name lowercased) when no class is provided.
        if info.get("default_css") and "class" in info.get("attrs", []):
            props_dict = dict(element["props"])  # copy
            if "class" not in props_dict or not props_dict.get("class"):
                # assign default class based on plugin name
                props_dict["class"] = name.lower()
                # update props_dict used below
                # we'll use this updated props_dict for rendering attributes and placeholder substitution
        else:
            props_dict = dict(element["props"])
        had_children_placeholder = "{{children}}" in content_template
        selfclosing = info["selfclosing"]
        allowed_attrs = info["attrs"]
        # enforce attribute allow/deny rules
        allow_attrs = info.get("allow_attrs", [])
        deny_attrs = info.get("deny_attrs", [])

        final_props = {}
        for k, v in props_dict.items():
            # deny precedence
            if k in deny_attrs:
                print(f"Warning: attribute '{k}' on <{name}> denied by plugin rules; dropping")
                continue
            # if allow_attrs specified and not wildcard, enforce whitelist
            if allow_attrs and not ("*" in allow_attrs):
                if k not in [a.lower() for a in allow_attrs]:
                    print(f"Warning: attribute '{k}' not in allow_attrs for <{name}>; dropping")
                    continue
            # otherwise allowed
            final_props[k] = v

        # build attributes string using final_props and allowed_attrs declared in plugin (fallback)
        attr_allowed_set = set(a.lower() for a in (allowed_attrs or []))
        if allow_attrs and not ("*" in allow_attrs):
            # use allow_attrs as authoritative
            attr_allowed_set = set(a.lower() for a in allow_attrs)

        # If neither allow_attrs nor plugin attrs restrict, allow all final_props
        if attr_allowed_set:
            attr_str = " ".join(f'{k}="{v}"' for k,v in final_props.items() if k.lower() in attr_allowed_set).strip()
        else:
            attr_str = " ".join(f'{k}="{v}"' for k,v in final_props.items()).strip()

        # replace placeholders in content (use final_props)
        content = content_template
        for k,v in final_props.items():
            content = content.replace(f"{{{{{k}}}}}", v)

        # enforce allowed children rules
        allow_children = info.get("allow_children", [])
        filtered_children = []
        if allow_children and not ("*" in allow_children):
            allow_set = set(n.lower() for n in allow_children)
            for c in raw_children:
                if c["name"].lower() in allow_set:
                    filtered_children.append(c)
                else:
                    print(f"Warning: child '<{c['name']}>' not allowed inside '<{name}>' by plugin rules; dropping")
        else:
            filtered_children = raw_children

        # compile filtered children
        child_lines = [compile_element(c, indent + 1) for c in filtered_children]
        children_html_inner = "\n".join(child_lines)

        # insert children into content if template requested them
        if had_children_placeholder:
            # replace children placeholder in the already placeholder-substituted content
            content = content.replace("{{children}}", children_html_inner)
        else:
            # start from content_template with placeholders replaced above
            content = content

        # remove any unreplaced template placeholders like {{text}} or others
        content = re.sub(r"\{\{.*?\}\}", "", content)
        content = content.strip()

        # build tag
        if selfclosing:
            return f"{pad}<{tag}{' ' + attr_str if attr_str else ''} />"
        else:
            # multi-line tag if we have content or children
            if content or child_lines:
                parts = [f"{pad}<{tag}{' ' + attr_str if attr_str else ''}>"]
                if content:
                    for line in content.splitlines():
                        parts.append(f"{pad}  {line}")
                # Only append compiled children separately if content did not already include them
                if child_lines and not had_children_placeholder:
                    parts.append(children_html_inner)
                parts.append(f"{pad}</{tag}>")
                return "\n".join(parts)
            else:
                return f"{pad}<{tag}{' ' + attr_str if attr_str else ''}></{tag}>"
    else:
        text = props_dict.get("text", "").strip()
        if text or child_lines:
            parts = [f"{pad}<{name}>"]
            if text:
                for line in text.splitlines():
                    parts.append(f"{pad}  {line}")
            if child_lines:
                parts.append(children_html_inner)
            parts.append(f"{pad}</{name}>")
            return "\n".join(parts)
        else:
            return f"{pad}<{name}></{name}>"

def compile_to_html(ast):
    # Collect compiled body and also any default_css/default_script from used plugins
    compiled_parts = [compile_element(element, 0) for element in ast]

    used_css = []
    used_scripts = []

    def collect_defaults(element):
        name = element["name"].lower()
        if name in plugin_registry:
            info = plugin_registry[name]
            css = info.get("default_css","" ).strip()
            js = info.get("default_script","" ).strip()
            if css and css not in used_css:
                used_css.append(css)
            if js and js not in used_scripts:
                used_scripts.append(js)
        for c in element["children"]:
            collect_defaults(c)

    for e in ast:
        collect_defaults(e)

    # If there's a top-level Html element, try to insert <style> into its head and script into body
    full_html = "\n".join(compiled_parts) + "\n"

    # Simple injection: if '<head>' exists, insert styles after opening head; otherwise prepend styles
    style_block = ""
    if used_css:
        style_block = "<style>\n" + "\n".join(used_css) + "\n</style>\n"
        if "<head>" in full_html:
            full_html = full_html.replace("<head>", "<head>\n" + style_block, 1)
        else:
            full_html = style_block + full_html

    # Append scripts before closing body if present
    if used_scripts:
        script_block = "<script>\n" + "\n".join(used_scripts) + "\n</script>\n"
        if "</body>" in full_html:
            full_html = full_html.replace("</body>", script_block + "</body>", 1)
        else:
            full_html = full_html + script_block

    return full_html

# ---------------------------
# CLI
# ---------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dslc.py <file.box>")
        sys.exit(1)

    input_file = sys.argv[1]

    if not os.path.exists(input_file):
        print(f"File {input_file} not found!")
        sys.exit(1)

    load_plugins("plugins")

    with open(input_file, "r", encoding="utf-8") as f:
        code = f.read()

    try:
        tokens = tokenize(code)
        ast = parse(tokens)
        html = compile_to_html(ast)

        output_file = os.path.splitext(input_file)[0] + ".html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"Compiled {input_file} → {output_file}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)
