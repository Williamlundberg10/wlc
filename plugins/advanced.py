# Advanced plugin example for dslc.py
# This plugin demonstrates registering plugin metadata and a dynamic definition

meta = {
    "name": "Advanced Component",
    "author": "Plugin Author",
    "version": "1.0",
    "description": "Provides an advanced component with default CSS and script"
}

# The plugin should expose a register(registry) function which the loader will call.
# It can register components by adding entries to the provided registry dict.

def register(registry):

    registry["Hej"] = {
        "tag": "div",
        # Demonstrate helpers: render an HTML list and JSON, then include children
        "content": "<div class='hej-data'>\n<h4>Data list</h4>\n{{data_list}}\n</div>\n<div class='hej-children'>{{children}}</div>\n<pre class='hej-json'>{{data_json}}</pre>",
        "selfclosing": False,
        "attrs": ["class"],
        "default_css": ".card{padding:10px;border:1px solid #ddd}",
    # Use the JSON placeholder directly; the compiler will substitute a JSON-quoted
    # value (e.g. "q1"), so we don't wrap it again.
    "default_script": 'alert({{data_json[0]}})',
        "allow_children": ["*"],
        "allow_attrs": ["*"],
        "deny_attrs": []
    }

# Optionally provide a metadata() helper
def metadata():
    return meta