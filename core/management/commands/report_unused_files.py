import ast
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


TEMPLATE_INCLUDE_RE = re.compile(r"{%\s*(?:extends|include)\s+[\"']([^\"']+)[\"']\s*%}")
TEMPLATE_STATIC_RE = re.compile(r"{%\s*static\s+[\"']([^\"']+)[\"']\s*%}")
PY_TEMPLATE_RE = re.compile(r"[\"']([^\"']+\.html)[\"']")
INCLUDE_MODULE_RE = re.compile(r"include\([\"']([\w\.]+)[\"']\)")


def _template_key(path: Path) -> str:
    parts = path.parts
    if "templates" not in parts:
        return path.name
    idx = parts.index("templates")
    return "/".join(parts[idx + 1 :])


def _module_name_from_path(base_dir: Path, path: Path) -> str:
    rel = path.relative_to(base_dir).with_suffix("")
    return ".".join(rel.parts)


def _resolve_relative_import(module: str | None, level: int, current_package: str) -> str:
    if level == 0:
        return module or ""
    parts = current_package.split(".") if current_package else []
    if level > len(parts):
        base_parts = []
    else:
        base_parts = parts[: len(parts) - level + 1]
    if module:
        base_parts.append(module)
    return ".".join([part for part in base_parts if part])


class Command(BaseCommand):
    help = "Gera um relatório de arquivos potencialmente não utilizados."

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        report_dir = base_dir / "reports"
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / "unused_files_report.md"

        template_files = []
        for templates_dir in base_dir.rglob("templates"):
            template_files.extend(templates_dir.rglob("*.html"))

        referenced_templates = set()
        referenced_static = set()
        for template_path in template_files:
            content = template_path.read_text(encoding="utf-8", errors="ignore")
            referenced_templates.update(TEMPLATE_INCLUDE_RE.findall(content))
            referenced_static.update(TEMPLATE_STATIC_RE.findall(content))
            referenced_templates.update(PY_TEMPLATE_RE.findall(content))

        python_files = [
            path
            for path in base_dir.rglob("*.py")
            if "migrations" not in path.parts
            and "node_modules" not in path.parts
            and "__pycache__" not in path.parts
            and "tests" not in path.parts
        ]

        referenced_templates.update(
            match
            for file_path in python_files
            for match in PY_TEMPLATE_RE.findall(
                file_path.read_text(encoding="utf-8", errors="ignore")
            )
        )

        template_keys = {_template_key(path): path for path in template_files}
        unused_templates = [
            template_keys[key]
            for key in sorted(template_keys.keys())
            if key not in referenced_templates
        ]

        static_files = []
        for static_dir in base_dir.rglob("static"):
            static_files.extend(
                path
                for path in static_dir.rglob("*")
                if path.is_file()
                and "node_modules" not in path.parts
                and "__pycache__" not in path.parts
                and path.suffix != ".py"
            )

        static_keys = {}
        for path in static_files:
            parts = path.parts
            if "static" in parts:
                idx = parts.index("static")
                static_keys["/".join(parts[idx + 1 :])] = path
        unused_static = [
            static_keys[key]
            for key in sorted(static_keys.keys())
            if key not in referenced_static
        ]

        used_modules = set(settings.INSTALLED_APPS)
        if getattr(settings, "ROOT_URLCONF", None):
            used_modules.add(settings.ROOT_URLCONF)
        if getattr(settings, "WSGI_APPLICATION", None):
            used_modules.add(settings.WSGI_APPLICATION)
        if getattr(settings, "ASGI_APPLICATION", None):
            used_modules.add(settings.ASGI_APPLICATION)
        for file_path in python_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content)
            except SyntaxError:
                continue
            used_modules.update(INCLUDE_MODULE_RE.findall(content))
            module_name = _module_name_from_path(base_dir, file_path)
            current_package = module_name.rsplit(".", 1)[0] if "." in module_name else ""
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        used_modules.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    resolved = _resolve_relative_import(node.module, node.level, current_package)
                    if resolved:
                        used_modules.add(resolved)
                        for alias in node.names:
                            used_modules.add(f"{resolved}.{alias.name}")
                    elif node.level:
                        for alias in node.names:
                            used_modules.add(f"{current_package}.{alias.name}".strip("."))

        python_candidates = [
            path
            for path in python_files
            if path.name not in {"manage.py", "__init__.py"}
            and "management" not in path.parts
            and "settings.py" not in path.name
            and "wsgi.py" not in path.name
            and "asgi.py" not in path.name
        ]
        unused_modules = []
        for path in python_candidates:
            module_name = _module_name_from_path(base_dir, path)
            if module_name not in used_modules:
                unused_modules.append(path)

        report_lines = [
            "# Relatório de arquivos potencialmente não utilizados",
            "",
            "_Este relatório é heurístico e pode conter falsos positivos._",
            "",
            "## Templates",
        ]
        if unused_templates:
            report_lines.extend(
                [
                    f"- `{path.relative_to(base_dir)}`: não encontrado em includes/extends/render."
                    for path in unused_templates
                ]
            )
        else:
            report_lines.append("- Nenhum template suspeito encontrado.")

        report_lines.append("")
        report_lines.append("## Arquivos estáticos")
        if unused_static:
            report_lines.extend(
                [
                    f"- `{path.relative_to(base_dir)}`: não encontrado em referências de {{% static %}}."
                    for path in unused_static
                ]
            )
        else:
            report_lines.append("- Nenhum arquivo estático suspeito encontrado.")

        report_lines.append("")
        report_lines.append("## Módulos Python")
        if unused_modules:
            report_lines.extend(
                [
                    f"- `{path.relative_to(base_dir)}`: não importado por outros módulos."
                    for path in unused_modules
                ]
            )
        else:
            report_lines.append("- Nenhum módulo Python suspeito encontrado.")

        report_path.write_text("\n".join(report_lines), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Relatório salvo em {report_path}"))
