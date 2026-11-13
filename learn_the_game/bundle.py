"""Packt index.html, app.js und data.js in eine einzige Datei (Hockey-verstehen.html),
die man per Mail/Teams verschicken und per Doppelklick öffnen kann."""
from pathlib import Path

HERE = Path(__file__).parent
html = (HERE / "index.html").read_text(encoding="utf-8")
for name in ("data.js", "app.js"):
    js = (HERE / name).read_text(encoding="utf-8").replace("</script", "<\\/script")
    html = html.replace(f'<script src="{name}"></script>', f"<script>\n{js}\n</script>")
out = HERE / "Hockey-verstehen.html"
out.write_text(html, encoding="utf-8")
print(f"{out.name}: {out.stat().st_size / 1024:.0f} KB")
