"""Zero-cost diagnostics for LaTeX sources, each function doing one thing.

  missing_packages(tex, search_dir)  -> packages a document needs that TeX cannot find
  first_latex_error(log_path)        -> the first fatal-looking line of a compile log
"""
import os
import re
import subprocess
from typing import Callable

_USEPACKAGE = re.compile(r"\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")


def _strip_comments(tex: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", tex)


def _kpsewhich(filename: str) -> bool:
    out = subprocess.run(["/Library/TeX/texbin/kpsewhich", filename], capture_output=True, text=True)
    return bool(out.stdout.strip())


def required_packages(tex: str) -> list[str]:
    names = []
    for m in _USEPACKAGE.finditer(_strip_comments(tex)):
        names += [n.strip() for n in m.group(1).split(",") if n.strip()]
    return sorted(set(names))


def missing_packages(tex: str, search_dir: str, exists: Callable[[str], bool] = _kpsewhich) -> list[str]:
    """Packages that are neither shipped next to the paper nor installed in TeX."""
    missing = []
    for pkg in required_packages(tex):
        local = os.path.exists(os.path.join(search_dir, pkg + ".sty"))
        if not local and not exists(pkg + ".sty"):
            missing.append(pkg)
    return missing


def first_latex_error(log_path: str) -> str:
    """First '! ...' error line of a compile log ('' if none)."""
    try:
        for line in open(log_path, errors="ignore"):
            if line.startswith("!"):
                return line.strip()
    except FileNotFoundError:
        pass
    return ""
