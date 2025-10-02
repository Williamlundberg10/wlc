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
    registry["card"] = {
        "tag": "div",
        "content": "<div class=\"card\">{{children}}</div>",
        "selfclosing": False,
        "attrs": ["class"],
        "default_css": ".card{padding:10px;border:1px solid #ddd}",
        "default_script": "",
        "allow_children": ["*"],
        "allow_attrs": ["*"],
        "deny_attrs": []
    }

# Optionally provide a metadata() helper
def metadata():
    return meta
