from __future__ import annotations
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Request
from fastapi.responses import FileResponse,JSONResponse
from typing import Dict
from openai import AsyncOpenAI
from dotenv import load_dotenv
from pathlib import Path
import os, json
import shutil
import tempfile
import base64
import zipfile, tempfile, shutil, re, json
from typing import List, Any,Set,Optional
from services.flutter_generator import generate_flutter_app
from fastapi import Body, Query
from fastapi.encoders import jsonable_encoder
import textwrap
import logging
router = APIRouter()

# Cargar variables de entorno
load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def cleanup_temp_dir(temp_dir: str):
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

@router.post("/generate-flutter")
async def generate_flutter_code(json_data: Dict, background_tasks: BackgroundTasks):
    temp_dir = None
    try:
        prompt = f"""
        Based on this JSON specification, generate a complete main.dart file for a Flutter application:
        {json_data}
        

Requirements:
1. The code must be valid and executable without any modifications.
2. It must compile and run successfully without any errors or warnings.
3. Only return the code — no explanations, no comments, no markdown formatting, and no ``` markers.
4. Use only proper Flutter widgets, icons, and Flutter best practices.
5. Structure the app with main(), MaterialApp, and Scaffold.
6. Organize the code as needed to make it clean, readable, and maintainable.
7. Ensure the layout exactly reflects the JSON structure.
8. Optimize for responsiveness and performance.
9. Do not include anything else except the pure Dart code content of main.dart.
10. MAKE IT RESPONSIVE: The UI should adapt to different screen sizes and orientations.
11. I need that every widget that is in the JSON is present in the code.
Generate and return ONLY the content of a complete and correct main.dart file.
        """

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a Flutter expert code generator."},
                {"role": "user", "content": prompt}
            ]
        )

        generated_code = response.choices[0].message.content

        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        json_data["generated_code"] = generated_code

        flutter_app_path = temp_path / "flutter_app"
        generate_flutter_app(json_data, flutter_app_path)

        zip_path = temp_path / "flutter_project.zip"
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', flutter_app_path)

        background_tasks.add_task(cleanup_temp_dir, temp_dir)

        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename="flutter_project.zip",
            background=background_tasks
        )

    except Exception as e:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-flutter-from-image")
async def generate_flutter_from_image(
    image: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    temp_dir = None
    try:
        # Leer y codificar imagen
        image_bytes = await image.read()
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{image.content_type};base64,{base64_image}"

        # Preparar entrada multimodal para GPT-4o
        messages = [
            {
                "role": "system",
                "content": "You are a Flutter UI expert that converts design images into working Flutter code."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """
You will receive an image. Your task is to analyze the visual content of the image and replicate it using proper Flutter widgets and styling.

You must return only the Flutter code required to replicate the image layout and design as accurately as possible.

Strict rules:
- Do NOT include any explanations, descriptions, or markdown formatting.
- Do NOT wrap the code in ```dart or any code blocks.This is a direct code generation task.
- Return only the complete Dart code for main.dart.
- Do NOT include comments.
- Only return valid Flutter code starting from a full main.dart file, including main(), MaterialApp, and Scaffold.
- Use appropriate layout widgets (e.g., Column, Row, Stack, Container, etc.) and apply correct styling (colors, fonts, spacing).
- Use placeholder assets where needed (e.g., network images, icons).
- Do not user Padding or Margin widgets 
Return only the final code of main.dart.
""".strip()
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url
                        }
                    }
                ]
            }
        ]

        # Generar código con GPT-4o
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        generated_code = response.choices[0].message.content

        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        json_data = {
            "appName": "ImageApp",
            "pages": [],
            "generated_code": generated_code
        }

        flutter_app_path = temp_path / "flutter_app"
        generate_flutter_app(json_data, flutter_app_path)

        zip_path = temp_path / "flutter_project_from_image.zip"
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', flutter_app_path)

        if background_tasks:
            background_tasks.add_task(cleanup_temp_dir, temp_dir)

        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename="flutter_project_from_image.zip",
            background=background_tasks
        )

    except Exception as e:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-flutter-from-prompt")
async def generate_flutter_from_prompt(data: Dict, background_tasks: BackgroundTasks):
    temp_dir = None
    try:
        user_prompt = data.get("prompt", "").strip()
        if not user_prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

        messages = [
            {
                "role": "system",
                "content": "You are a Flutter code generation expert. You generate full Flutter main.dart files from design prompts."
            },
            {
                "role": "user",
                "content": f"""
{user_prompt}

Rules:
- Only return the complete Dart code for main.dart.
- Do NOT use markdown formatting or ```dart blocks.
- Do NOT include explanations or comments.
- Include necessary imports, main(), MaterialApp, and a full Scaffold.
- Use valid Flutter widgets and styling.
- It has to be responsive and adapt to different screen sizes.
- Completely functional and ready to run.
""".strip()
            }
        ]

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        generated_code = response.choices[0].message.content

        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        json_data = {
            "appName": "PromptGeneratedApp",
            "pages": [],
            "generated_code": generated_code
        }

        flutter_app_path = temp_path / "flutter_app"
        generate_flutter_app(json_data, flutter_app_path)

        zip_path = temp_path / "flutter_project_from_prompt.zip"
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', flutter_app_path)

        background_tasks.add_task(cleanup_temp_dir, temp_dir)

        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename="flutter_project_from_prompt.zip",
            background=background_tasks
        )

    except Exception as e:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))



# ─────────────── Helpers ───────────────

async def _cleanup(dir_path: str) -> None:
    if dir_path and os.path.exists(dir_path):
        shutil.rmtree(dir_path, ignore_errors=True)

def _zip_dir(src: Path, dest: Path) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in src.rglob("*"):
            zf.write(p, p.relative_to(src))

def _parse_size(val: Optional[str], dimension: str) -> Optional[str]:
    if not val:
        return None
    if val.endswith("%"):
        pct = float(val.rstrip("%")) / 100
        return f"constraints.max{dimension.capitalize()} * {pct}"
    if val.endswith("px"):
        return f"{float(val.rstrip('px'))}"
    return val

def _edge(pad: Optional[str]) -> str:
    if not pad:
        return "EdgeInsets.zero"
    parts = pad.replace("px", "").split()
    if len(parts) == 1:
        return f"EdgeInsets.all({parts[0]})"
    return f"EdgeInsets.symmetric(horizontal: {parts[0]}, vertical: {parts[1]})"

_color = lambda h: f"Color(0xFF{h.lstrip('#')})"

# ─────────── Writer ───────────

class DW:
    def __init__(self) -> None:
        self.lines: List[str] = []
    def w(self, txt: str = "", ind: int = 0) -> None:
        self.lines.append("  " * ind + txt)
    def __str__(self) -> str:
        return "\n".join(self.lines)

# ───── Align & FAB mappings ─────

_MAIN = {
    "flex-start": "MainAxisAlignment.start",
    "center":     "MainAxisAlignment.center",
    "flex-end":   "MainAxisAlignment.end",
    "space-between": "MainAxisAlignment.spaceBetween",
    "space-around":  "MainAxisAlignment.spaceAround",
}
_CROSS = {
    "flex-start": "CrossAxisAlignment.start",
    "center":     "CrossAxisAlignment.center",
    "flex-end":   "CrossAxisAlignment.end",
}
_ALIGN = {
    "center":     "Alignment.center",
    "flex-start": "Alignment.centerLeft",
    "flex-end":   "Alignment.centerRight",
}
_FAB_LOC = {
    "bottomRight":  "FloatingActionButtonLocation.endFloat",
    "bottomLeft":   "FloatingActionButtonLocation.startFloat",
    "bottomCenter": "FloatingActionButtonLocation.centerFloat",
    "centerDocked": "FloatingActionButtonLocation.centerDocked",
    "topRight":     "FloatingActionButtonLocation.endTop",
    "topLeft":      "FloatingActionButtonLocation.startTop",
}

# ─── Collect state variables recursively ───

def _collect_state_vars(widgets: List[Dict[str, Any]], state_vars: Dict[str, str]) -> None:
    for w in widgets:
        t = w["type"]
        if t == "switch":
            var = w["label"].lower().replace(" ", "_")
            init = str(w.get("value", False)).lower()
            state_vars[var] = f"bool {var} = {init};"
        elif t == "checkbox":
            var = w["label"].lower().replace(" ", "_")
            init = str(w.get("value", False)).lower()
            state_vars[var] = f"bool {var} = {init};"
        elif t == "slider":
            state_vars["sliderValue"] = f"double sliderValue = {w.get('value', 0)};"
        elif t == "radioGroup":
            var = w["label"].lower().replace(" ", "_")
            init = f"'{w.get('value','')}'"
            state_vars[var] = f"String {var} = {init};"
        elif t == "dropdown":
            var = w["label"].lower().replace(" ", "_")
            init = f"'{w.get('value','')}'"
            state_vars[var] = f"String {var} = {init};"
        elif t == "datePicker":
            state_vars["selectedDate"] = "DateTime? selectedDate;"
        if "children" in w and isinstance(w["children"], list):
            _collect_state_vars(w["children"], state_vars)

# ─── JSON → Dart widget converter ───

def _w2d(node: Dict[str, Any], ind: int, ctx_imp: Set[str]) -> List[str]:
    t = node["type"]
    out: List[str] = []

    if t in ("text","heading"):
        txt = node["text"]
        style_parts: List[str] = []
        if node.get("fontSize"):
            style_parts.append(f"fontSize: {node['fontSize']}")
        if node.get("bold"):
            style_parts.append("fontWeight: FontWeight.bold")
        if node.get("textColor"):
            style_parts.append(f"color: {_color(node['textColor'])}")
        style = f", style: TextStyle({', '.join(style_parts)})" if style_parts else ""
        widget = f"Text('{txt}'{style})"
        if align := node.get("align"):
            out.append(f"Align(alignment: {_ALIGN.get(align,'Alignment.center')}, child: {widget}),")
        else:
            out.append(f"{widget},")
        return [("  "*ind)+l for l in out]

    if t == "icon":
        out.append(f"Icon(Icons.{node['icon']}),")
    elif t == "image":
        w = _parse_size(node.get("width"), "width")
        h = _parse_size(node.get("height"), "height")
        args: List[str] = []
        if w: args.append(f"width: {w}")
        if h: args.append(f"height: {h}")
        arg_str = ", " + ", ".join(args) if args else ""
        out.append(f"Image.network('{node['src']}'{arg_str}),")
    elif t == "button":
        style = ""
        if node.get("backgroundColor"):
            style = f" style: ElevatedButton.styleFrom(backgroundColor: {_color(node['backgroundColor'])}),"
        out.extend([
            "ElevatedButton(",
            f"  onPressed: () {{ }},{style}",
            f"  child: Text('{node['label']}'),",
            "),",
        ])
    elif t == "textField":
        dec: List[str] = []
        if node.get("label"):
            dec.append(f"labelText: '{node['label']}'")
        if node.get("placeholder"):
            dec.append(f"hintText: '{node['placeholder']}'")
        out.append(f"TextField(decoration: InputDecoration({', '.join(dec)})),")
    elif t == "checkbox":
        var = node["label"].lower().replace(" ", "_")
        out.append(
            f"CheckboxListTile(title: Text('{node['label']}'), value: {var}, onChanged: (v) {{ setState(() => {var} = v!); }}),"
        )
    elif t == "switch":
        var = node["label"].lower().replace(" ", "_")
        out.append(
            f"SwitchListTile(title: Text('{node['label']}'), value: {var}, onChanged: (v) {{ setState(() => {var} = v!); }}),"
        )
    elif t == "slider":
        out.append("Slider(value: sliderValue, onChanged: (v) { setState(() => sliderValue = v); }, min: 0, max: 100),")
    elif t == "radioGroup":
        var = node["label"].lower().replace(" ", "_")
        out.append("Column(children: [")
        for opt in node["options"]:
            out.append(
                f"  RadioListTile<String>(value: '{opt}', groupValue: {var}, title: Text('{opt}'), onChanged: (v) {{ setState(() => {var} = v!); }},),"
            )
        out.append("]),")
    elif t == "dropdown":
        var = node["label"].lower().replace(" ", "_")
        items = ", ".join(f'DropdownMenuItem(value: "{i}", child: Text("{i}"))' for i in node["items"])
        out.append(
            f"DropdownButton<String>(value: {var}, items: [{items}], onChanged: (v) {{ setState(() => {var} = v!); }}),"
        )
    elif t == "datePicker":
        ctx_imp.add("intl")
        ph = node.get("placeholder", "Select date")
        out.extend([
            "OutlinedButton(",
            "  onPressed: () async {",
            "    final d = await showDatePicker(",
            "      context: context, firstDate: DateTime(2000), lastDate: DateTime(2100), initialDate: DateTime.now(),",
            "    ); if (d != null) setState(() => selectedDate = d);",
            "  },",
            f"  child: Text('{ph}'),",
            "),"
        ])
    elif t == "circleAvatar":
        out.append("CircleAvatar(radius: 24),")
    elif t == "chip":
        out.append(f"Chip(label: Text('{node['text']}')),")
    elif t == "listView":
        h = _parse_size(node.get("height"), "height")
        if h:
            out.append(f"SizedBox(height: {h}, child: ListView(children: [")
        else:
            out.append("ListView(shrinkWrap: true, children: [")
        for ch in node["children"]:
            out.extend(_w2d(ch, 1, ctx_imp))
        out.append("])),")
    elif t == "listTile":
        parts = ["ListTile("]
        if icon := node.get("icon"):
            parts.append(f"  leading: Icon(Icons.{icon['name']}, color: {_color(icon['color'])}),")
        parts.append(f"  title: Text('{node['title']}'),")
        parts.append(f"  subtitle: Text('{node['subtitle']}'),")
        if node.get("check"):
            parts.append("  trailing: Icon(Icons.check),")
        parts.append("),")
        out.extend(parts)
    elif t == "card":
        out.append("Card(")
        if bc := node.get("backgroundColor"):
            out.append(f"  color: {_color(bc)},")
        out.append("  child: Column(children: [")
        for ch in node["children"]:
            out.extend(_w2d(ch, 2, ctx_imp))
        out.append("  ]),")
        out.append("),")
    elif t == "stack":
        bg = node.get("backgroundColor")
        h = _parse_size(node.get("height"), "height")
        out.append("Container(")
        if bg: out.append(f"  color: {_color(bg)},")
        if h: out.append(f"  height: {h},")
        out.append("  child: Stack(children: [")
        for ch in node["children"]:
            out.extend(_w2d(ch, 2, ctx_imp))
        out.append("  ]),")
        out.append("),")
    elif t in ("row","column"):
        lay = "Row" if t=="row" else "Column"
        out.append(f"{lay}(")
        if ma := node.get("mainAxisAlignment"):
            out.append(f"  mainAxisAlignment: {_MAIN[ma]},")
        if ca := node.get("crossAxisAlignment"):
            out.append(f"  crossAxisAlignment: {_CROSS[ca]},")
        out.append("  children: [")
        for ch in node["children"]:
            out.extend(_w2d(ch,1,ctx_imp))
        out.append("  ],")
        out.append("),")
    elif t == "container":
        w = _parse_size(node.get("width"), "width") or "constraints.maxWidth"
        h = _parse_size(node.get("height"), "height")
        out.append("Container(")
        out.append(f"  width: {w},")
        if h: out.append(f"  height: {h},")
        if bc := node.get("backgroundColor"):
            out.append(f"  color: {_color(bc)},")
        if children := node.get("children"):
            out.append("  child: Column(")
            if ma := node.get("mainAxisAlignment"):
                out.append(f"    mainAxisAlignment: {_MAIN[ma]},")
            if ca := node.get("crossAxisAlignment"):
                out.append(f"    crossAxisAlignment: {_CROSS[ca]},")
            out.append("    children: [")
            for ch in children:
                out.extend(_w2d(ch,3,ctx_imp))
            out.append("    ],")
            out.append("  ),")
        out.append("),")
    elif t == "dataTable":
        cols = ", ".join(f'DataColumn(label: Text("{c}"))' for c in node["table"]["columns"])
        rows = []
        for r in node["table"]["rows"]:
            cells = ", ".join(f'DataCell(Text("{c}"))' for c in r)
            rows.append(f"DataRow(cells: [{cells}])")
        out.append(f"SingleChildScrollView(scrollDirection: Axis.horizontal, child: DataTable(columns: [{cols}], rows: [{','.join(rows)}])),")
    elif t == "alertDialog":
        dlg = node["dialog"]
        out.extend([
            "ElevatedButton(",
            "  onPressed: () {",
            "    showDialog(",
            "      context: context,",
            "      builder: (_) => AlertDialog(",
            f"        title: Text('{dlg['title']}'),",
            f"        content: Text('{dlg['content']}'),",
            "        actions: [",
            f"          TextButton(onPressed: ()=>Navigator.pop(context), child: Text('{dlg['buttons']['cancel']['text']}')),",
            f"          TextButton(onPressed: ()=>Navigator.pop(context), child: Text('{dlg['buttons']['confirm']['text']}')),",
            "        ],",
            "      ),",
            "    );",
            "  },",
            f"  child: Text('{dlg['buttons']['confirm']['text']}'),",
            "),"
        ])
    elif t == "progressIndicator":
        if node.get("value") is not None:
            out.append(f"LinearProgressIndicator(value: {node['value']}/100),")
        else:
            out.append("CircularProgressIndicator(),")
    else:
        out.append("Container(),")

    return [("  " * ind) + l for l in out]

# ─── Build main.dart ───

def build_main_dart(ui: Dict[str, Any]) -> str:
    raw = ui["name"].replace(" ", "")
    app_name = raw if raw.lower().endswith("app") else f"{raw}App"
    routes = ui["routes"]
    pages = ui["pages"]

    ctx_imp: Set[str] = set()
    if any(w["type"] == "datePicker" for p in pages for w in p["widgets"]):
        ctx_imp.add("intl")

    app = DW()
    app.w("import 'package:flutter/material.dart';")
    if "intl" in ctx_imp:
        app.w("import 'package:intl/intl.dart';")
    app.w()
    app.w(f"void main() => runApp(const {app_name}());")
    app.w()
    app.w(f"class {app_name} extends StatelessWidget {{")
    app.w("  const " + app_name + "({super.key});")
    app.w("  @override")
    app.w("  Widget build(BuildContext context) {")
    app.w("    return MaterialApp(",1)
    app.w(f"      title: '{ui['name']}',",2)
    app.w("      theme: ThemeData(",2)
    app.w(f"        primaryColor: const {_color(ui['theme']['primary'])},",3)
    app.w(f"        colorScheme: ColorScheme.fromSeed(seedColor: const {_color(ui['theme']['primary'])}),",3)
    app.w("      ),",2)
    app.w(f"      initialRoute: '{routes[0]}',",2)
    app.w("      routes: {",2)
    for rt in routes:
        cls = rt.lstrip("/").capitalize() + "Page"
        app.w(f"        '{rt}': (_) => const {cls}(),",3)
    app.w("      },",2)
    app.w("    );")
    app.w("  }")
    app.w("}")
    app.w()

    for pg in pages:
        cls = pg["name"].capitalize() + "Page"
        fab = pg.get("fab", {})
        state_vars: Dict[str,str] = {}
        _collect_state_vars(pg["widgets"], state_vars)
        is_stateful = bool(state_vars)

        if is_stateful:
            app.w(f"class {cls} extends StatefulWidget {{")
            app.w("  const " + cls + "({super.key});")
            app.w("  @override")
            app.w(f"  _{cls}State createState() => _{cls}State();")
            app.w("}")
            app.w()
            app.w(f"class _{cls}State extends State<{cls}> {{")
            for decl in state_vars.values():
                app.w(f"  {decl}")
            app.w()
            app.w("  @override")
            app.w("  Widget build(BuildContext context) {")
        else:
            app.w(f"class {cls} extends StatelessWidget {{")
            app.w("  const " + cls + "({super.key});")
            app.w("  @override")
            app.w("  Widget build(BuildContext context) {")

        app.w("    return Scaffold(",2)
        if bg := pg.get("background"):
            app.w(f"      backgroundColor: const {_color(bg)},",3)

        # only if an appBar widget is present in JSON
        ab = next((w for w in pg["widgets"] if w["type"] == "appBar"), None)
        if ab:
            bgc = ab.get("backgroundColor")
            tc  = ab.get("textColor")
            ht  = None
            if ab.get("height", "").endswith("px"):
                ht = float(ab["height"].rstrip("px"))
            app.w("      appBar: AppBar(",3)
            if bgc:
                app.w(f"        backgroundColor: {_color(bgc)},",4)
            if ht is not None:
                app.w(f"        toolbarHeight: {ht},",4)
            if tc:
                app.w(f"        title: Text('{pg['title']}', style: TextStyle(color: {_color(tc)})),",4)
            else:
                app.w(f"        title: Text('{pg['title']}'),",4)
            app.w("      ),",3)

        # FAB
        if fab:
            icon = fab.get("icon","add")
            lbl  = fab.get("label","")
            act  = fab.get("action","").replace("'", "\\'")
            loc  = _FAB_LOC.get(fab.get("position","bottomRight"))
            if fab.get("showLabel", False):
                app.w("      floatingActionButton: FloatingActionButton.extended(",3)
                app.w(f"        onPressed: () => ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('{act}'))),",4)
                app.w(f"        icon: const Icon(Icons.{icon}),",4)
                app.w(f"        label: const Text('{lbl}'),",4)
                app.w("      ),",3)
            else:
                app.w("      floatingActionButton: FloatingActionButton(",3)
                app.w(f"        onPressed: () => ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('{act}'))),",4)
                app.w(f"        child: const Icon(Icons.{icon}),",4)
                app.w("      ),",3)
            app.w(f"      floatingActionButtonLocation: {loc},",3)

        # Body
        app.w("      body: LayoutBuilder(",3)
        app.w("        builder: (context, constraints) => SingleChildScrollView(",4)
        app.w("          padding: const EdgeInsets.all(16),",5)
        app.w("          child: Column(",5)
        app.w("            children: [",6)
        for w in pg["widgets"]:
            if w["type"] == "appBar":
                continue
            for line in _w2d(w,8,ctx_imp):
                app.w(line)
        app.w("            ],",6)
        app.w("          ),",5)
        app.w("        ),",4)
        app.w("      ),",3)

        # BottomNavigationBar
        bn = next((w for w in pg["widgets"] if w["type"] == "bottomNavigationBar"), None)
        if bn:
            idx = routes.index(f"/{pg['name']}")
            app.w("      bottomNavigationBar: BottomNavigationBar(",3)
            app.w(f"        currentIndex: {idx},",4)
            sel = _color(bn["selectedItemColor"])
            uns = _color(bn["textColor"])
            app.w(f"        selectedItemColor: const {sel},",4)
            app.w(f"        unselectedItemColor: const {uns},",4)
            app.w("        onTap: (i) {",4)
            for i, item in enumerate(bn["items"]):
                app.w(f"          if (i == {i}) Navigator.pushReplacementNamed(context, '{item['route']}');",5)
            app.w("        },",4)
            app.w("        items: const [",4)
            for item in bn["items"]:
                app.w(f"          BottomNavigationBarItem(icon: Icon(Icons.{item['icon']}), label: '{item['label']}'),",5)
            app.w("        ],",4)
            app.w("      ),",3)

        app.w("    );",2)
        app.w("  }")
        app.w("}")
        app.w()

    return str(app)
@router.post("/generate-main-dart-manual")
async def generate_main_dart_manual(
    ui_json: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    tmp = tempfile.mkdtemp()
    try:
        # 1. Generar el código Dart a partir del JSON
        code = build_main_dart(ui_json)
        ui_json["generated_code"] = code

        # 2. Usar la misma función que empaqueta el proyecto Flutter
        from services.flutter_generator import generate_flutter_app  # importa según tu estructura real
        flutter_app_path = Path(tmp) / "flutter_app"
        generate_flutter_app(ui_json, flutter_app_path)

        # 3. Comprimir el proyecto en un ZIP
        zip_path = Path(tmp) / "flutter_project.zip"
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', flutter_app_path)

        # 4. Programar limpieza de temporales
        background_tasks.add_task(_cleanup, tmp)

        # 5. Responder el archivo
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename="flutter_project.zip",
            background=background_tasks
        )

    except Exception as e:
        await _cleanup(tmp)
        raise HTTPException(status_code=500, detail=str(e))



# ────── Config opcional de esquema ──────
UI_SCHEMA: dict | None = None  # Carga tu JSON Schema si lo necesitas

# ────── Helper: extraer el bloque JSON ──────
def _extract_json(raw: str) -> str:
    """Devuelve la primera cadena JSON con llaves balanceadas."""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.I | re.M)
    depth = start = 0
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return raw[start : i + 1]
    raise ValueError("No se encontró un objeto JSON balanceado.")

UI_SCHEMA: dict | None = None  # pon tu schema si lo deseas

def _extract_json(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.I | re.M)
    depth = start = 0
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return raw[start : i + 1]
    raise ValueError("Bloque JSON no encontrado")

# ────────── Helper: extraer JSON balanceado ──────────
def _extract_json(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.I | re.M)
    count = start = 0
    for i, ch in enumerate(raw):
        if ch == "{":
            if count == 0:
                start = i
            count += 1
        elif ch == "}":
            count -= 1
            if count == 0 and start is not None:
                return raw[start : i + 1]
    raise ValueError("No se encontró bloque JSON.")

# ════════════════════════════════════════════════════
@router.post("/analyze-ui-image")
async def analyze_ui_image(
    image: UploadFile = File(...)
):
    try:
        # 1) codificar imagen → data URL
        img64 = base64.b64encode(await image.read()).decode()
        data_url = f"data:{image.content_type};base64,{img64}"

        # 2) guía detallada de widgets + ejemplos mínimos
        widget_guide = textwrap.dedent("""
        Estructura general:
        {
          "name": "App Name",
          "theme": { "primary": "#hex" },
          "routes": ["/page1", "/page2"],
          "pages": [{ ... }]
        }
        Aqui tenes un ejemplo de una app completa:
        {
  "name": "Complete Free Positioning App",
  "theme": {
    "primary": "#ef4444"
  },
  "routes": ["/dashboard", "/design"],
  "pages": [
    {
      "name": "dashboard",
      "title": "Dashboard - Free Position",
      "layout": "fixed",
      "mode": "absolute",
      "background": "#0f172a",
      "fab": {
        "label": "Create",
        "icon": "plus",
        "action": "New element created!",
        "showLabel": false
      },
      "widgets": [
        {
          "type": "appBar",
          "title": "Free Position Dashboard",
          "backgroundColor": "#1e293b",
          "textColor": "#f1f5f9",
          "x": 0,
          "y": 0,
          "width": "100%",
          "height": "60px"
        },
        {
          "type": "card",
          "backgroundColor": "#1e293b",
          "elevation": 3,
          "x": 20,
          "y": 80,
          "width": "300px",
          "height": "200px",
          "children": [
            {
              "type": "heading",
              "text": "Analytics Overview",
              "fontSize": 20,
              "textColor": "#f1f5f9",
              "bold": true,
              "x": 10,
              "y": 10
            },
            {
              "type": "text",
              "text": "Real-time metrics and insights",
              "fontSize": 14,
              "textColor": "#94a3b8",
              "x": 10,
              "y": 40
            },
            {
              "type": "progressIndicator",
              "value": 85,
              "x": 10,
              "y": 70,
              "width": "280px"
            },
            {
              "type": "row",
              "x": 10,
              "y": 110,
              "width": "280px",
              "gap": 8,
              "children": [
                {
                  "type": "chip",
                  "text": "Active",
                  "variant": "default"
                },
                {
                  "type": "badge",
                  "text": "Live",
                  "variant": "default"
                }
              ]
            }
          ]
        },
        {
          "type": "container",
          "backgroundColor": "#374151",
          "x": 340,
          "y": 80,
          "width": "250px",
          "height": "350px",
          "children": [
            {
              "type": "heading",
              "text": "Quick Actions",
              "fontSize": 18,
              "textColor": "#f9fafb",
              "x": 15,
              "y": 15
            },
            {
              "type": "button",
              "label": "New Project",
              "variant": "default",
              "x": 15,
              "y": 50,
              "width": "220px"
            },
            {
              "type": "button",
              "label": "Import Data",
              "variant": "secondary",
              "x": 15,
              "y": 90,
              "width": "220px"
            },
            {
              "type": "textField",
              "label": "Search",
              "placeholder": "Type to search...",
              "x": 15,
              "y": 130,
              "width": "220px"
            },
            {
              "type": "dropdown",
              "label": "Category",
              "items": ["All", "Projects", "Tasks", "Reports"],
              "value": "All",
              "x": 15,
              "y": 180,
              "width": "220px"
            },
            {
              "type": "switch",
              "label": "Dark Mode",
              "value": true,
              "x": 15,
              "y": 230
            },
            {
              "type": "slider",
              "value": 7,
              "min": 0,
              "max": 10,
              "x": 15,
              "y": 270,
              "width": "220px"
            }
          ]
        },
        {
          "type": "image",
          "src": "/placeholder.svg?height=150&width=200",
          "alt": "Performance Chart",
          "x": 610,
          "y": 80,
          "width": "200px",
          "height": "150px"
        },
        {
          "type": "listView",
          "x": 20,
          "y": 300,
          "width": "300px",
          "height": "200px",
          "gap": 4,
          "children": [
            {
              "type": "listTile",
              "title": "System Status",
              "subtitle": "All systems operational",
              "icon": {
                "name": "check_circle",
                "color": "#10b981"
              },
              "check": true
            },
            {
              "type": "listTile",
              "title": "Database",
              "subtitle": "Connection stable",
              "icon": {
                "name": "storage",
                "color": "#3b82f6"
              },
              "check": true
            },
            {
              "type": "listTile",
              "title": "API Gateway",
              "subtitle": "Response time: 45ms",
              "icon": {
                "name": "api",
                "color": "#f59e0b"
              },
              "check": false
            }
          ]
        },
        {
          "type": "dataTable",
          "x": 610,
          "y": 250,
          "width": "350px",
          "height": "200px",
          "columns": ["User", "Status", "Last Active"],
          "rows": [
            ["Alice Johnson", "Online", "2 min ago"],
            ["Bob Smith", "Away", "15 min ago"],
            ["Carol Davis", "Offline", "2 hours ago"]
          ]
        },
        {
          "type": "row",
          "x": 20,
          "y": 520,
          "width": "400px",
          "gap": 12,
          "children": [
            {
              "type": "circleAvatar",
              "avatarSrc": "/placeholder.svg?height=60&width=60",
              "avatarFallback": "AD",
              "size": 60
            },
            {
              "type": "column",
              "gap": 8,
              "children": [
                {
                  "type": "text",
                  "text": "Administrator",
                  "fontSize": 16,
                  "textColor": "#f1f5f9",
                  "bold": true
                },
                {
                  "type": "text",
                  "text": "admin@company.com",
                  "fontSize": 14,
                  "textColor": "#94a3b8"
                }
              ]
            }
          ]
        },
        {
          "type": "icon",
          "icon": "settings",
          "iconSize": 48,
          "iconColor": "#64748b",
          "x": 900,
          "y": 100
        },
        {
          "type": "alertDialog",
          "dialogTitle": "System Maintenance",
          "dialogContent": "Scheduled maintenance will begin in 30 minutes.",
          "confirmButtonText": "Acknowledge",
          "cancelButtonText": "Remind Later",
          "dialogType": "warning",
          "x": 450,
          "y": 520
        },
        {
          "type": "bottomNavigationBar",
          "items": [
            {"label": "Dashboard", "icon": "dashboard"},
            {"label": "Analytics", "icon": "analytics"},
            {"label": "Settings", "icon": "settings"},
            {"label": "Help", "icon": "help"}
          ],
          "backgroundColor": "#1e293b",
          "textColor": "#94a3b8",
          "selectedItemColor": "#ef4444",
          "selectedIndex": 0,
          "x": 0,
          "y": "calc(100vh - 60px)",
          "width": "100%",
          "height": "60px"
        }
      ]
    },
    {
      "name": "design",
      "title": "Design Studio - Free",
      "layout": "fixed",
      "mode": "absolute",
      "background": "#fef3c7",
      "fab": {
        "label": "Add Layer",
        "icon": "layers",
        "action": "New layer added!",
        "showLabel": true,
        "variant": "default"
      },
      "widgets": [
        {
          "type": "appBar",
          "title": "Design Studio",
          "backgroundColor": "#d97706",
          "textColor": "#ffffff",
          "x": 0,
          "y": 0,
          "width": "100%"
        },
        {
          "type": "stack",
          "backgroundColor": "#fed7aa",
          "x": 50,
          "y": 100,
          "width": "400px",
          "height": "300px",
          "children": [
            {
              "type": "heading",
              "text": "Creative Canvas",
              "fontSize": 32,
              "textColor": "#92400e",
              "bold": true,
              "x": 20,
              "y": 20
            },
            {
              "type": "text",
              "text": "Design with precision using absolute positioning",
              "fontSize": 16,
              "textColor": "#a16207",
              "x": 20,
              "y": 70
            },
            {
              "type": "image",
              "src": "/placeholder.svg?height=100&width=150",
              "alt": "Design Tools",
              "x": 20,
              "y": 110,
              "width": "150px",
              "height": "100px"
            },
            {
              "type": "button",
              "label": "Start Creating",
              "variant": "default",
              "x": 200,
              "y": 150
            }
          ]
        },
        {
          "type": "card",
          "backgroundColor": "#ffffff",
          "elevation": 4,
          "x": 500,
          "y": 100,
          "width": "300px",
          "height": "400px",
          "children": [
            {
              "type": "heading",
              "text": "Tools Panel",
              "fontSize": 20,
              "x": 20,
              "y": 20
            },
            {
              "type": "checkbox",
              "label": "Grid Snap",
              "value": true,
              "x": 20,
              "y": 60
            },
            {
              "type": "checkbox",
              "label": "Show Rulers",
              "value": false,
              "x": 20,
              "y": 90
            },
            {
              "type": "radioGroup",
              "label": "Tool",
              "options": "Select,Move,Resize,Rotate",
              "value": "Select",
              "x": 20,
              "y": 120
            },
            {
              "type": "divider",
              "x": 20,
              "y": 200,
              "width": "260px"
            },
            {
              "type": "text",
              "text": "Properties",
              "fontSize": 16,
              "bold": true,
              "x": 20,
              "y": 220
            },
            {
              "type": "textField",
              "label": "Width",
              "placeholder": "200px",
              "x": 20,
              "y": 250,
              "width": "120px"
            },
            {
              "type": "textField",
              "label": "Height",
              "placeholder": "100px",
              "x": 160,
              "y": 250,
              "width": "120px"
            },
            {
              "type": "datePicker",
              "placeholder": "Created date",
              "x": 20,
              "y": 300,
              "width": "260px"
            }
          ]
        },
        {
          "type": "container",
          "backgroundColor": "#f3f4f6",
          "x": 50,
          "y": 420,
          "width": "750px",
          "height": "150px",
          "children": [
            {
              "type": "text",
              "text": "Recent Projects",
              "fontSize": 18,
              "bold": true,
              "x": 20,
              "y": 20
            },
            {
              "type": "row",
              "x": 20,
              "y": 50,
              "gap": 15,
              "children": [
                {
                  "type": "card",
                  "backgroundColor": "#ddd6fe",
                  "width": "100px",
                  "height": "80px",
                  "children": [
                    {
                      "type": "text",
                      "text": "Project A",
                      "fontSize": 12,
                      "x": 10,
                      "y": 10
                    }
                  ]
                },
                {
                  "type": "card",
                  "backgroundColor": "#fecaca",
                  "width": "100px",
                  "height": "80px",
                  "children": [
                    {
                      "type": "text",
                      "text": "Project B",
                      "fontSize": 12,
                      "x": 10,
                      "y": 10
                    }
                  ]
                },
                {
                  "type": "card",
                  "backgroundColor": "#bbf7d0",
                  "width": "100px",
                  "height": "80px",
                  "children": [
                    {
                      "type": "text",
                      "text": "Project C",
                      "fontSize": 12,
                      "x": 10,
                      "y": 10
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
                                       Mejor si no utilizas tantos containers , quiero algo mas a mano alzada que sea identico al diseño que te he proporcionado.
        IMPORTANTE: responde SOLO el JSON final, sin texto ni markdown.
        """)

        system = "Eres un analista experto en UI/UX."
        user   = [
            {"type": "text", "text": widget_guide},
            {"type": "image_url", "image_url": {"url": data_url}}
        ]

        # 3) llamada a GPT-4o
        resp = await client.chat.completions.create(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=4096,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}]
        )
        raw = resp.choices[0].message.content

        # 4) sanitizar y parsear
        try:
            clean = _extract_json(raw)
            ui_json = json.loads(clean)
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(400, "La IA no devolvió un JSON válido.")

        return JSONResponse(ui_json)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error en /analyze-ui-image")
        raise HTTPException(500, detail=str(e))
    


@router.post("/analyze-ui-prompt")
async def analyze_ui_prompt(
    payload: dict
):
    try:
        prompt_text = payload.get("prompt", "").strip()
        if not prompt_text:
            raise HTTPException(400, "El campo 'prompt' no puede estar vacío.")

        # 1) guía de widgets (idéntica a la del endpoint de imagen)
        widget_guide = textwrap.dedent("""
        Estructura general:
        {
          "name": "App Name",
          "theme": { "primary": "#hex" },
          "routes": ["/page1", "/page2"],
          "pages": [{ ... }]
        }
          Aqui tenes un ejemplo de una app completa:
        {
  "name": "Complete Free Positioning App",
  "theme": {
    "primary": "#ef4444"
  },
  "routes": ["/dashboard", "/design"],
  "pages": [
    {
      "name": "dashboard",
      "title": "Dashboard - Free Position",
      "layout": "fixed",
      "mode": "absolute",
      "background": "#0f172a",
      "fab": {
        "label": "Create",
        "icon": "plus",
        "action": "New element created!",
        "showLabel": false
      },
      "widgets": [
        {
          "type": "appBar",
          "title": "Free Position Dashboard",
          "backgroundColor": "#1e293b",
          "textColor": "#f1f5f9",
          "x": 0,
          "y": 0,
          "width": "100%",
          "height": "60px"
        },
        {
          "type": "card",
          "backgroundColor": "#1e293b",
          "elevation": 3,
          "x": 20,
          "y": 80,
          "width": "300px",
          "height": "200px",
          "children": [
            {
              "type": "heading",
              "text": "Analytics Overview",
              "fontSize": 20,
              "textColor": "#f1f5f9",
              "bold": true,
              "x": 10,
              "y": 10
            },
            {
              "type": "text",
              "text": "Real-time metrics and insights",
              "fontSize": 14,
              "textColor": "#94a3b8",
              "x": 10,
              "y": 40
            },
            {
              "type": "progressIndicator",
              "value": 85,
              "x": 10,
              "y": 70,
              "width": "280px"
            },
            {
              "type": "row",
              "x": 10,
              "y": 110,
              "width": "280px",
              "gap": 8,
              "children": [
                {
                  "type": "chip",
                  "text": "Active",
                  "variant": "default"
                },
                {
                  "type": "badge",
                  "text": "Live",
                  "variant": "default"
                }
              ]
            }
          ]
        },
        {
          "type": "container",
          "backgroundColor": "#374151",
          "x": 340,
          "y": 80,
          "width": "250px",
          "height": "350px",
          "children": [
            {
              "type": "heading",
              "text": "Quick Actions",
              "fontSize": 18,
              "textColor": "#f9fafb",
              "x": 15,
              "y": 15
            },
            {
              "type": "button",
              "label": "New Project",
              "variant": "default",
              "x": 15,
              "y": 50,
              "width": "220px"
            },
            {
              "type": "button",
              "label": "Import Data",
              "variant": "secondary",
              "x": 15,
              "y": 90,
              "width": "220px"
            },
            {
              "type": "textField",
              "label": "Search",
              "placeholder": "Type to search...",
              "x": 15,
              "y": 130,
              "width": "220px"
            },
            {
              "type": "dropdown",
              "label": "Category",
              "items": ["All", "Projects", "Tasks", "Reports"],
              "value": "All",
              "x": 15,
              "y": 180,
              "width": "220px"
            },
            {
              "type": "switch",
              "label": "Dark Mode",
              "value": true,
              "x": 15,
              "y": 230
            },
            {
              "type": "slider",
              "value": 7,
              "min": 0,
              "max": 10,
              "x": 15,
              "y": 270,
              "width": "220px"
            }
          ]
        },
        {
          "type": "image",
          "src": "/placeholder.svg?height=150&width=200",
          "alt": "Performance Chart",
          "x": 610,
          "y": 80,
          "width": "200px",
          "height": "150px"
        },
        {
          "type": "listView",
          "x": 20,
          "y": 300,
          "width": "300px",
          "height": "200px",
          "gap": 4,
          "children": [
            {
              "type": "listTile",
              "title": "System Status",
              "subtitle": "All systems operational",
              "icon": {
                "name": "check_circle",
                "color": "#10b981"
              },
              "check": true
            },
            {
              "type": "listTile",
              "title": "Database",
              "subtitle": "Connection stable",
              "icon": {
                "name": "storage",
                "color": "#3b82f6"
              },
              "check": true
            },
            {
              "type": "listTile",
              "title": "API Gateway",
              "subtitle": "Response time: 45ms",
              "icon": {
                "name": "api",
                "color": "#f59e0b"
              },
              "check": false
            }
          ]
        },
        {
          "type": "dataTable",
          "x": 610,
          "y": 250,
          "width": "350px",
          "height": "200px",
          "columns": ["User", "Status", "Last Active"],
          "rows": [
            ["Alice Johnson", "Online", "2 min ago"],
            ["Bob Smith", "Away", "15 min ago"],
            ["Carol Davis", "Offline", "2 hours ago"]
          ]
        },
        {
          "type": "row",
          "x": 20,
          "y": 520,
          "width": "400px",
          "gap": 12,
          "children": [
            {
              "type": "circleAvatar",
              "avatarSrc": "/placeholder.svg?height=60&width=60",
              "avatarFallback": "AD",
              "size": 60
            },
            {
              "type": "column",
              "gap": 8,
              "children": [
                {
                  "type": "text",
                  "text": "Administrator",
                  "fontSize": 16,
                  "textColor": "#f1f5f9",
                  "bold": true
                },
                {
                  "type": "text",
                  "text": "admin@company.com",
                  "fontSize": 14,
                  "textColor": "#94a3b8"
                }
              ]
            }
          ]
        },
        {
          "type": "icon",
          "icon": "settings",
          "iconSize": 48,
          "iconColor": "#64748b",
          "x": 900,
          "y": 100
        },
        {
          "type": "alertDialog",
          "dialogTitle": "System Maintenance",
          "dialogContent": "Scheduled maintenance will begin in 30 minutes.",
          "confirmButtonText": "Acknowledge",
          "cancelButtonText": "Remind Later",
          "dialogType": "warning",
          "x": 450,
          "y": 520
        },
        {
          "type": "bottomNavigationBar",
          "items": [
            {"label": "Dashboard", "icon": "dashboard"},
            {"label": "Analytics", "icon": "analytics"},
            {"label": "Settings", "icon": "settings"},
            {"label": "Help", "icon": "help"}
          ],
          "backgroundColor": "#1e293b",
          "textColor": "#94a3b8",
          "selectedItemColor": "#ef4444",
          "selectedIndex": 0,
          "x": 0,
          "y": "calc(100vh - 60px)",
          "width": "100%",
          "height": "60px"
        }
      ]
    },
    {
      "name": "design",
      "title": "Design Studio - Free",
      "layout": "fixed",
      "mode": "absolute",
      "background": "#fef3c7",
      "fab": {
        "label": "Add Layer",
        "icon": "layers",
        "action": "New layer added!",
        "showLabel": true,
        "variant": "default"
      },
      "widgets": [
        {
          "type": "appBar",
          "title": "Design Studio",
          "backgroundColor": "#d97706",
          "textColor": "#ffffff",
          "x": 0,
          "y": 0,
          "width": "100%"
        },
        {
          "type": "stack",
          "backgroundColor": "#fed7aa",
          "x": 50,
          "y": 100,
          "width": "400px",
          "height": "300px",
          "children": [
            {
              "type": "heading",
              "text": "Creative Canvas",
              "fontSize": 32,
              "textColor": "#92400e",
              "bold": true,
              "x": 20,
              "y": 20
            },
            {
              "type": "text",
              "text": "Design with precision using absolute positioning",
              "fontSize": 16,
              "textColor": "#a16207",
              "x": 20,
              "y": 70
            },
            {
              "type": "image",
              "src": "/placeholder.svg?height=100&width=150",
              "alt": "Design Tools",
              "x": 20,
              "y": 110,
              "width": "150px",
              "height": "100px"
            },
            {
              "type": "button",
              "label": "Start Creating",
              "variant": "default",
              "x": 200,
              "y": 150
            }
          ]
        },
        {
          "type": "card",
          "backgroundColor": "#ffffff",
          "elevation": 4,
          "x": 500,
          "y": 100,
          "width": "300px",
          "height": "400px",
          "children": [
            {
              "type": "heading",
              "text": "Tools Panel",
              "fontSize": 20,
              "x": 20,
              "y": 20
            },
            {
              "type": "checkbox",
              "label": "Grid Snap",
              "value": true,
              "x": 20,
              "y": 60
            },
            {
              "type": "checkbox",
              "label": "Show Rulers",
              "value": false,
              "x": 20,
              "y": 90
            },
            {
              "type": "radioGroup",
              "label": "Tool",
              "options": "Select,Move,Resize,Rotate",
              "value": "Select",
              "x": 20,
              "y": 120
            },
            {
              "type": "divider",
              "x": 20,
              "y": 200,
              "width": "260px"
            },
            {
              "type": "text",
              "text": "Properties",
              "fontSize": 16,
              "bold": true,
              "x": 20,
              "y": 220
            },
            {
              "type": "textField",
              "label": "Width",
              "placeholder": "200px",
              "x": 20,
              "y": 250,
              "width": "120px"
            },
            {
              "type": "textField",
              "label": "Height",
              "placeholder": "100px",
              "x": 160,
              "y": 250,
              "width": "120px"
            },
            {
              "type": "datePicker",
              "placeholder": "Created date",
              "x": 20,
              "y": 300,
              "width": "260px"
            }
          ]
        },
        {
          "type": "container",
          "backgroundColor": "#f3f4f6",
          "x": 50,
          "y": 420,
          "width": "750px",
          "height": "150px",
          "children": [
            {
              "type": "text",
              "text": "Recent Projects",
              "fontSize": 18,
              "bold": true,
              "x": 20,
              "y": 20
            },
            {
              "type": "row",
              "x": 20,
              "y": 50,
              "gap": 15,
              "children": [
                {
                  "type": "card",
                  "backgroundColor": "#ddd6fe",
                  "width": "100px",
                  "height": "80px",
                  "children": [
                    {
                      "type": "text",
                      "text": "Project A",
                      "fontSize": 12,
                      "x": 10,
                      "y": 10
                    }
                  ]
                },
                {
                  "type": "card",
                  "backgroundColor": "#fecaca",
                  "width": "100px",
                  "height": "80px",
                  "children": [
                    {
                      "type": "text",
                      "text": "Project B",
                      "fontSize": 12,
                      "x": 10,
                      "y": 10
                    }
                  ]
                },
                {
                  "type": "card",
                  "backgroundColor": "#bbf7d0",
                  "width": "100px",
                  "height": "80px",
                  "children": [
                    {
                      "type": "text",
                      "text": "Project C",
                      "fontSize": 12,
                      "x": 10,
                      "y": 10
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
        IMPORTANTE: devuelve SOLO el JSON final, sin explicaciones ni markdown.
        """)

        system_msg = "Eres un analista experto en UI/UX. Convierte el prompt en un JSON válido."
        user_msg = [
            {"type": "text", "text": f"{widget_guide}\nDescripción de la UI:\n{prompt_text}"}
        ]

        # 2) Llamada a GPT-4o multimodal (aunque aquí sólo es texto)
        resp = await client.chat.completions.create(
            model="gpt-4o",
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ]
        )
        raw = resp.choices[0].message.content

        # 3) sanitizar y extraer bloque JSON balanceado
        try:
            clean = _extract_json(raw)
            ui_json = json.loads(clean)
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(400, "La IA no devolvió un JSON válido.")

        return JSONResponse(ui_json)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error en /analyze-ui-prompt")
        raise HTTPException(500, detail=str(e))
