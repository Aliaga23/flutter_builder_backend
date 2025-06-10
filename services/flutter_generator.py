"""
flutter_generator.py
Copia un proyecto Flutter base y reemplaza lib/main.dart + lib/pages/*.dart
"""
import shutil, datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# rutas
BASE = Path(__file__).parent.parent
TEMPLATE_JINJA   = BASE / "utils" / "flutter_template"
TEMPLATE_PROJECT = BASE / "utils" / "flutter_template_project"

env = Environment(
    loader=FileSystemLoader([
        str(TEMPLATE_JINJA),
        str(TEMPLATE_JINJA / "lib"),
        str(TEMPLATE_JINJA / "lib" / "pages")
    ]),
    trim_blocks=True, lstrip_blocks=True, autoescape=False
)

def camel(s: str) -> str:
    return "".join(w.capitalize() for w in s.split("_"))

def generate_flutter_app(data: dict, output_dir: Path):
    # 1. copiar skeleton completo
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(TEMPLATE_PROJECT, output_dir, dirs_exist_ok=True)

    pages_dir = output_dir / "lib" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # 2. Generate main.dart directly
    main_file = output_dir / "lib" / "main.dart"
    main_file.write_text(data.get("generated_code", ""), encoding="utf-8")

    # 3. Update pubspec.yaml
    pubspec_tpl = env.get_template("pubspec.yaml.jinja")
    (output_dir / "pubspec.yaml").write_text(
        pubspec_tpl.render(app=data.get("appName","FlutterApp")),
        encoding="utf-8"
    )

    print("✅ Flutter app generated in:", output_dir)
