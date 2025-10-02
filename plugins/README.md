# Plugin authoring guide for dslc

This document explains how to write plugins for the DSL compiler in this repository.

There are two plugin formats supported:

- `.box` plugin files (declarative blocks parsed by `load_plugin_file`).
- Python plugins (`.py`) that export a `register(registry)` function.

Both kinds of plugins ultimately register entries in the global `plugin_registry`.

-----

## Plugin definition fields

Each plugin definition declares the behavior for a DSL tag. The following fields are supported:

- `tag` (string)
  - The HTML tag to emit for this component (e.g. `div`, `a`, `h2`). Defaults to the plugin name lowercased.

- `content` (string template)
  - Template used to render the inner content of the component. Use placeholder tokens (see below).
  - Examples: `"{{children}}"`, `"<div>{{data_list}}</div>{{children}}"`.

- `selfclosing` (bool)
  - If true, the component is rendered as a self-closing element (`<tag />`).

- `attrs` (list of strings)
  - Declares attribute names that the component recognizes (used as a fallback when `allow_attrs` is not specified).

- `default_css` (string)
  - Optional CSS injected into the compiled HTML inside a single `<style>` tag if the plugin is used.

- `default_script` (string)
  - Optional JavaScript injected into the compiled HTML (all used plugin scripts are appended before `</body>`).
  - See the `Script and JSON placeholders` section for safe ways to access plugin `data` from JS.

- `allow_children` (list of strings)
  - Whitelist of child tag names allowed inside this component. `"*"` means allow any child.

- `allow_attrs` (list of strings)
  - Whitelist of allowed attribute names. `"*"` means allow any attribute.

- `deny_attrs` (list of strings)
  - Deny specific attribute names (takes precedence over allow rules).

-----

## Placeholders available in `content` templates

The compiler supports a small templating substitution for plugin `content`. These are replaced at compile time:

- `{{children}}` — compiled children HTML (if any).
- `{{text}}` — the special `text(...)` property value (not emitted as attribute).
- `{{*}}` — shorthand for `text` then `children` (text followed by compiled children).
- `{{data}}` — the plugin's inline data list joined by commas (e.g. `q1,q2`).
- `{{data_list}}` — renders an HTML unordered list (`<ul><li>...</li></ul>`) of the inline data values.
- `{{data_json}}` — JSON array string of the inline data (e.g. `["q1","q2"]`). Useful for embedding raw JSON.

Indexed access is supported too:

- `{{data[n]}}` — the raw nth item (string) from the inline data list (0-based). Example: `{{data[0]}}` → `q1`.
- `{{data_json[n]}}` — the nth item JSON-encoded (includes quotes). Example: `{{data_json[0]}}` → `"q1"`.

Notes:
- Indexed placeholders are substituted before the general `{{key}}` replacement so they are available inside `content` or `default_script`.
- Use `{{data_list}}` when you want an HTML list. Use `{{data_json}}` / `{{data_json[n]}}` for JS-safe embedding.

-----

## Script and JSON placeholders

`default_script` templates are processed per-element instance so script placeholders may include element-specific data. The compiler provides multiple ways to safely embed JSON data into JS code:

- Use `alert({{data_json[0]}})` in your `default_script` if you want the compiler to insert a JSON-quoted value like `"q1"`. Do not wrap the placeholder in extra quotes — the compiler will insert properly quoted JSON.
- Use `console.log({{data_json}})` to receive a raw JSON array in JS.
- If you must place data inside a quoted JS string, use `{{data_json_esc}}` or let the compiler recognize quoted occurrences and produce an escaped string literal automatically.

Examples:

Python plugin script value:

```
# alerts the first data item
"default_script": 'alert({{data_json[0]}})'
```

Or to log the full JSON array:

```
"default_script": 'console.log({{data_json}})'
```

-----

## Attribute / children rules

- `deny_attrs` has precedence — any attribute listed there will be dropped even if also allowed by `allow_attrs`.
- If `allow_attrs` is provided and does not contain `"*"`, it's treated as a whitelist; attributes not listed are dropped.
- `allow_children` controls which child tags are kept inside the compiled output. If omitted or contains `"*"` any children are allowed.

-----

## .box plugin format (declarative)

A `.box` plugin is processed by `load_plugin_file`. It looks for `define Name(...)` blocks and extracts fields like `tag("div")`, `content("...")`, `attr("class")`, `default_css("...")`, etc.

Example (illustrative):

```
define Card(
  tag("div")
  content("<div class='card'>{{children}}</div>")
  attr("class")
  default_css(".card { padding:10px }")
  allow_children("*")
  allow_attrs("*")
)
```

Field parsing supports quoted strings spanning multiple lines for CSS/JS blocks.

-----

## Python plugin format

A Python plugin should expose a `register(registry)` function. The loader will import the module and call `register(registry)`; your function should add keys to the provided `registry` dict.

You may also provide `metadata()` or a `meta` dict to supply plugin metadata (name/author/version/description) which will be displayed when plugins are loaded.

Example Python plugin:

```python
meta = {
  "name": "Advanced Component",
  "author": "Plugin Author",
  "version": "1.0",
}

def register(registry):
  registry["Hej"] = {
    "tag": "div",
    "content": "<div>{{data_list}}</div>{{children}}",
    "selfclosing": False,
    "attrs": ["class"],
    "default_css": ".card{padding:10px}",
    "default_script": 'alert({{data_json[0]}})',
    "allow_children": ["*"],
    "allow_attrs": ["*"],
    "deny_attrs": []
  }

def metadata():
  return meta
```

Loader behavior notes:

- Python plugin modules are executed and `register(registry)` is called. The loader normalizes plugin keys to lowercase when adding them to the global registry so lookups from the DSL are case-insensitive.

-----

## Best practices

- Prefer `{{data_json}}` for raw JSON and `{{data_list}}` for HTML rendering.
- Avoid embedding raw user data directly into HTML or JS without proper escaping. Use `{{data_json[n]}}` for safe JSON quoting inside JS contexts.
- Keep `default_css` small and scoped by class names to avoid global style collisions.

-----

## Testing and debugging

- To test a plugin, create a `.box` file that uses the tag with inline data:

```
Hej{"q1","q2"}(
  h1(text("Hello"))
)
```

- Run the compiler:

```powershell
C:/Python313/python.exe dslc.py t.box
```

- Inspect the generated `t.html` and the injected `<style>` / `<script>` blocks.

-----

If something in this doc doesn't match the current behavior of the compiler, open an issue or ask for an update — I can expand the docs or add examples as needed.
