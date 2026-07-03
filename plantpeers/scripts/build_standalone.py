#!/usr/bin/env python3
"""Bundle the multi-file plantpeers app into a single self-contained HTML file.

Inlines model.js and data/*.json so the app runs with no server and no network
(the Artifact/preview sandbox blocks external + relative fetches). The app code
is left UNCHANGED: a small fetch-shim intercepts fetch('data/*.json') and returns
the inlined data, and <script src="model.js"> becomes an inline <script>.

Outputs (under plantpeers/dist/):
  plantpeers.standalone.html  — a full self-contained HTML document
  plantpeers.artifact.html    — body-only fragment (no <!doctype>/<html>/<head>/
                                <body>) for the Artifact publisher, which supplies
                                its own skeleton.

Run: python3 plantpeers/scripts/build_standalone.py
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DATA_KEYS = ["plants", "sellers", "offers", "reviews", "requests"]


def esc_close(s: str) -> str:
    # never let embedded data close the enclosing <script>
    return s.replace("</", "<\\/")


def build():
    html = (ROOT / "index.html").read_text()
    model = (ROOT / "model.js").read_text()
    data = {k: json.loads((ROOT / "data" / f"{k}.json").read_text()) for k in DATA_KEYS}

    # inlined data + fetch shim (defined before the app script runs)
    data_js = ",\n".join(f'  "{k}": {esc_close(json.dumps(data[k]))}' for k in DATA_KEYS)
    shim = (
        "<script>\n"
        "/* offline bundle: serve inlined data/*.json without network */\n"
        "(function(){var __D={\n" + data_js + "\n};\n"
        "var _f=window.fetch?window.fetch.bind(window):null;\n"
        "window.fetch=function(u,o){var s=String(u);for(var k in __D){"
        "if(s.indexOf('data/'+k+'.json')!==-1){var d=__D[k];return Promise.resolve("
        "{ok:true,status:200,json:function(){return Promise.resolve(d);},"
        "text:function(){return Promise.resolve(JSON.stringify(d));}});}}"
        "return _f?_f(u,o):Promise.reject(new Error('offline bundle: '+s));};})();\n"
        "</script>\n"
    )
    model_inline = "<script>\n" + esc_close(model) + "\n</script>\n"

    # replace <script src="model.js"></script> with inlined model + shim
    if '<script src="model.js"></script>' not in html:
        sys.exit("ERROR: expected <script src=\"model.js\"></script> in index.html")
    full = html.replace('<script src="model.js"></script>', model_inline + shim)

    DIST.mkdir(exist_ok=True)
    (DIST / "plantpeers.standalone.html").write_text(full)

    # body-only fragment for the Artifact publisher: keep <style> + body inner +
    # scripts; drop the document wrapper (doctype/html/head/title/meta/body tags).
    style = re.search(r"<style>.*?</style>", full, re.S).group(0)
    body_inner = re.search(r"<body>(.*?)</body>", full, re.S).group(1)
    fragment = style + "\n" + body_inner.strip() + "\n"
    (DIST / "plantpeers.artifact.html").write_text(fragment)

    sc = full.count("<script")
    print(f"OK  standalone {len(full):,}B, artifact fragment {len(fragment):,}B, "
          f"{sc} inline script blocks, data: "
          + ", ".join(f"{k}={len(data[k])}" for k in DATA_KEYS))


if __name__ == "__main__":
    build()
