import os
import re
import glob
import shutil
import subprocess
import PyPDF2
from dataclasses import dataclass


def compress_pdf_ghostscript(
    input_pdf: str, output_pdf: str, quality: str = "/ebook"
) -> None:
    """Compress PDF size."""
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={quality}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output_pdf}",
        input_pdf,
    ]
    subprocess.run(cmd, check=True)
    print(f"Compressed PDF saved to {output_pdf}")


def find_main_tex_file_to_combine(folder: str) -> str:
    """
    Find the main text file in a latex source folder,
    return that main file.
    """
    tex_files = glob.glob(os.path.join(folder, "**/*.tex"), recursive=True)
    for tex_file in tex_files:
        with open(tex_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "author" in content and "\\documentclass" in content:
                return tex_file
    # fallback: return largest
    if tex_files:
        return max(tex_files, key=os.path.getsize)
    else:
        raise Exception("folder doesn't contain tex files")


def find_file(filename: str, base_path: str, max_up: int = 1) -> str | None:
    """
    Find file in a folder,
    return found candidate files or None.
    """
    for i in range(max_up + 1):
        candidate = os.path.join(base_path, *([".."] * i), filename)
        candidate = os.path.realpath(candidate)
        if os.path.exists(candidate):
            return candidate
    return None


def resolve_inputs(content: str, base_path: str, visited: set | None = None) -> str:
    """
    Replace every input{} and include{} in the latex file to combine everything into 1 file,
    return the combined source.
    """
    if visited is None:
        visited = set()

    # regex for finding \input{} and \include{}
    pattern = re.compile(r"(?m)^[^%\n]*\\(input|include){([^}]+)}")

    # function to iteratively replace all \input and \include
    def replacer(match):
        cmd, filename = match.groups()
        filepath = os.path.join(base_path, filename)
        if not filepath.endswith(".tex"):
            filepath += ".tex"

        # Avoid circular includes
        realpath = find_file(
            filename if filename.endswith(".tex") else filename + ".tex", base_path
        )
        if not realpath or realpath in visited or not os.path.exists(realpath):
            return f"% Skipped {cmd}{{{filename}}} (already included or not found)"

        visited.add(realpath)
        try:
            with open(realpath, "r", encoding="utf-8", errors="ignore") as f:
                nested_content = f.read()
            return resolve_inputs(nested_content, os.path.dirname(realpath), visited)
        except Exception as e:
            return f"% Failed to include {cmd}{{{filename}}}: {e}"

    return pattern.sub(replacer, content)


def combine_latex_sources(paper_dir: str, output_file: str = "combined.tex") -> str:
    """
    Combine and save the combined latex source as a latex tex file,
    return the filename.
    """
    main_tex = find_main_tex_file_to_combine(paper_dir)

    with open(main_tex, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # remove any comments
    processed_lines = []
    for line in content.splitlines():
        # skip lines starting with % (comments)
        if line.lstrip().startswith("%"):
            continue
        processed_lines.append(line)

    no_comments = "\n".join(processed_lines)
    # combine into one main file if there are inputs
    combined_content = resolve_inputs(no_comments, os.path.dirname(main_tex))

    combined_path = os.path.join(paper_dir, output_file)
    with open(combined_path, "w", encoding="utf-8") as f:
        f.write(combined_content)
    return combined_path


def copy_dir_contents(src: str, dst: str, new_name: str | None = None) -> None:
    """
    Copy all files and subdirectories from src to dst,
    return None.
    """
    if not os.path.exists(src):
        print("ERROR: Source directory does not exist.")
        return

    file_count = 0
    skipped_count = 0
    for root, _, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        dest_dir = os.path.join(dst, rel_path)
        os.makedirs(dest_dir, exist_ok=True)

        for file in files:
            src_file = os.path.join(root, file)

            # Only rename files exactly named 'main.tex'
            filename_no_ext, ext = os.path.splitext(file)
            if new_name and filename_no_ext == "main" and ext == "tex":
                dest_file_name = new_name + ext
            else:
                dest_file_name = file

            dst_file = os.path.join(dest_dir, dest_file_name)
            if os.path.exists(dst_file):
                skipped_count += 1
            else:
                shutil.copy2(src_file, dst_file)
                file_count += 1
    print(f"Copied {file_count} files, skipped {skipped_count} files.")


def _tex_bin(name: str) -> str:
    """Locate a TeX binary (PATH first, then the MacTeX default location)."""
    return shutil.which(name) or f"/Library/TeX/texbin/{name}"


def _run_logged(cmd: list[str], cwd: str, log, timeout: int = 180) -> int:
    """Run one compile step, appending its output to `log`; never raises.
    Returns the exit code (-1 on timeout)."""
    log.write(f"\n$ {' '.join(cmd)}\n")
    log.flush()
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        ).returncode
    except subprocess.TimeoutExpired:
        log.write(f"\n[timeout after {timeout}s]\n")
        return -1


@dataclass(frozen=True)
class BibliographyPlan:
    """What the bibliography step should do for one document."""

    engine: str | None  # "bibtex", "biber", or None (reuse the shipped .bbl / no bibliography)


def plan_bibliography(tex_source: str, build_dir: str) -> BibliographyPlan:
    """Decide the bibliography engine from the source; only run one when its .bib files exist."""
    body = re.sub(r"(?m)(?<!\\)%.*$", "", tex_source)
    names = []
    for m in re.finditer(r"\\bibliography\{([^}]*)\}", body):
        names += [n.strip() for n in m.group(1).split(",") if n.strip()]
    for m in re.finditer(r"\\addbibresource(?:\[[^\]]*\])?\{([^}]*)\}", body):
        names.append(m.group(1).strip())
    all_present = bool(names) and all(
        os.path.exists(os.path.join(build_dir, n if n.endswith(".bib") else n + ".bib"))
        for n in names
    )
    if not all_present:
        return BibliographyPlan(None)
    return BibliographyPlan("biber" if "\\addbibresource" in body else "bibtex")


def ensure_bbl_fallback(src_dir: str, build_dir: str, base_name: str) -> None:
    """Reuse a shipped .bbl as `<base_name>.bbl` when the bibliography can't be rebuilt."""
    target = os.path.join(build_dir, base_name + ".bbl")
    if os.path.exists(target):
        return
    shipped = sorted(glob.glob(os.path.join(src_dir, "**/*.bbl"), recursive=True))
    if shipped:
        shutil.copy2(shipped[0], target)


def build_steps(plan: BibliographyPlan, latex_cmd: list[str], base_name: str) -> list[tuple[list[str], str]]:
    """The ordered (command, where) steps of one build: latex [-> bib] -> latex -> latex."""
    steps = [(latex_cmd, "source")]
    if plan.engine:
        steps.append(([_tex_bin(plan.engine), base_name], "build"))
    steps += [(latex_cmd, "source"), (latex_cmd, "source")]
    return steps


def compile_latex(paper: str, des: str, main_tex: str) -> str:
    """
    Compile a LaTeX project into a PDF,
    return output pdf path (the file may not exist if compilation failed).

    Differences from upstream, all aimed at not dying on real arXiv sources:
    - one log per paper (`latex_compilation_log.txt` next to the pdf) instead
      of a shared log that every run overwrites;
    - LaTeX errors no longer abort the build (nonstopmode still emits a PDF for
      most recoverable errors); success is judged by the PDF existing;
    - bibtex/biber only run when their .bib inputs exist, otherwise the
      shipped .bbl is reused, so a missing .bib no longer breaks references;
    - no --shell-escape (arXiv sources are untrusted code);
    - subprocess timeouts are handled instead of crashing the pipeline.
    """
    dst = des.lstrip("/\\")
    build_dir = os.path.join(os.getcwd(), dst)
    main_tex_filename = os.path.basename(main_tex)
    base_name = os.path.splitext(main_tex_filename)[0]
    src_dir = f"data/papers/{paper}"
    output_pdf_path = os.path.join(build_dir, main_tex_filename.replace(".tex", ".pdf"))

    copy_dir_contents(src_dir, dst, base_name)
    if os.path.exists(output_pdf_path):
        os.remove(output_pdf_path)  # never mistake a stale pdf for a fresh build

    with open(main_tex, "r", encoding="utf-8", errors="ignore") as f:
        plan = plan_bibliography(f.read(), build_dir)
    if plan.engine is None:
        ensure_bbl_fallback(src_dir, build_dir, base_name)

    latex_cmd = [_tex_bin("pdflatex"), "-interaction=nonstopmode", "-output-directory", build_dir, main_tex_filename]
    cwd_for = {"source": os.path.dirname(main_tex) or ".", "build": build_dir}
    log_path = os.path.join(build_dir, "latex_compilation_log.txt")
    with open(log_path, "w") as log:
        for cmd, where in build_steps(plan, latex_cmd, base_name):
            _run_logged(cmd, cwd_for[where], log)

    if os.path.exists(output_pdf_path):
        print(f"Compilation SUCCESSFUL: {output_pdf_path}")
    else:
        print(f"Compilation FAILED! See {log_path}")
    return output_pdf_path


def replace_bibliography(filepath: str) -> None:
    """
    Replace bibliography{*.bib} with input{*.bbl} since there could be no bib files,
    so that the references can compile.
    """
    try:
        # Read the entire content of the file
        with open(filepath, "r", encoding="utf-8") as file:
            content = file.read()

        pattern = r"\\bibliography\{.*?\}"
        replacement = r"\\input{main.bbl}"
        new_content = re.sub(
            pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL
        )

        with open(filepath, "w", encoding="utf-8") as file:
            file.write(new_content)
        print(
            f"Successfully replaced \\bibliography{{...}} with \\input{{main.bbl}} in {filepath}."
        )

    except FileNotFoundError:
        print(f"Error: The file {filepath} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def check_pdf_for_unresolved_references(pdf_file_path: str) -> bool:
    """
    Perform OCR to check if there are unresolved references,
    return whether we should use the pdf or not (should not if
    there are unresolved references).
    """
    try:
        with open(pdf_file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text = page.extract_text()
                # assume there will be a reference on the first 5 pages
                if ("???" in text or "[?]" in text) and (page_num + 1 < 5):
                    print(f"Unresolved referesnces found on page {page_num + 1}.")
                    return False
            return True
    except FileNotFoundError:
        print(f"Error: {pdf_file_path} not found.")
        return False
    except Exception as e:
        print(f"Error reading {pdf_file_path}: {e}")
        return False
