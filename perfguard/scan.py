#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from datetime import datetime
import re
from typing import List

MODEL = os.getenv("PERFGUARD_MODEL", "qwen2.5-coder:1.5b")

# Keep CI predictable. Raise as your model context length.
MAX_OUTPUT_CHARS = int(os.getenv("PERFGUARD_MAX_OUTPUT_CHARS", "50000"))
MAX_FILE_CHARS = int(os.getenv("PERFGUARD_MAX_FILE_CHARS", "80000"))  # per file content cap
MAX_FILE_ANALYSIS_CHARS = int(os.getenv("PERFGUARD_MAX_FILE_ANALYSIS_CHARS", "20000"))  # per-file model output cap

FILE_ANALYSIS_PROMPT = """You are PerfGuard, a senior Java performance and maintainability reviewer.

You are analyzing ONE changed file from a pull request.
Treat the file content as the post-merge (PR head) state.
Do not assume runtime behavior. Do not invent benchmarks.
Be conservative, factual, and evidence-based.

Constraints:
- Do NOT change or rewrite business logic
- Do NOT assume data size, traffic, or usage patterns
- Do NOT claim guaranteed performance improvements

---

### PR Metadata
- Title: {PR_TITLE}
- Description: {PR_DESCRIPTION}

### File Under Review
Path: {FILE_PATH}

### File Content (post-merge, may be truncated)
```java
{FILE_CONTENT}
```

---

### Output Requirements (STRICT)
Return EXACTLY two sections in this order:

1) `Executive Summary:` followed by 1-2 sentences.
2) A Markdown table with this exact header row and separator row:

| Finding | Evidence (snippet) | Impact | Suggested Fix | Confidence |
|---|---|---|---|---|

Rules:
- Provide 0 to 10 rows.
- Evidence MUST reference the file content shown above.
- Confidence MUST be exactly one of: High, Medium, Low.
- Do NOT include any other headings, bullet lists, or extra text.
- If there are no meaningful issues, output a single table row that says:
  - Finding: No significant performance or maintainability risks detected for this file.
  - Evidence/Impact/Suggested Fix: (leave as `-`)
  - Confidence: High

Proceed with the analysis.
"""


COMBINE_PROMPT = """You are PerfGuard, a senior Java performance and maintainability reviewer.

You will be given:
1) The list of analyzed files.
2) Per-file analyses (each contains an executive summary and a findings table).

Your job is to produce ONE final PR review.

Hard rules:
- Do NOT paste or restate the per-file analyses.
- Do NOT create new findings that are not supported by the provided per-file analyses.
- Remove duplicates and consolidate similar findings.
- Keep the final output concise and actionable.

---

### Files analyzed
{FILES_ANALYZED}

---

### Output Requirements (STRICT, Markdown)
Return EXACTLY three sections in this order:

1) `Files Analyzed:` followed by the same bullet list of file paths provided above.
2) `Executive Summary:` followed by 2-3 sentences.
3) A Markdown table with this exact header row and separator row:

| Finding | Evidence (file and snippet) | Impact | Suggested Fix | Autofix Eligible | Confidence |
|---|---|---|---|---|---|

Rules:
- Provide 0 to 10 rows.
- Evidence MUST cite a file path from the file list.
- Confidence MUST be exactly one of: High, Medium, Low.
- Autofix Eligible MUST be exactly one of: Yes, No.
- Do NOT include any other headings, bullet lists, or extra text.
- If there are no meaningful issues, output a single table row that says:
  - Finding: No significant performance or maintainability risks detected in this PR.
  - Evidence/Impact/Suggested Fix: (leave as `-`)
  - Autofix Eligible: No
  - Confidence: High

Proceed with the final PR review.
"""


ANSI_ESCAPE_RE = re.compile(r"(?:\x1B|\uFFFD)\[[0-?]*[ -/]*[@-~]")


def strip_ansi_and_controls(s: str) -> str:
    # Remove ANSI escape sequences (cursor moves, spinners, etc.)
    s = ANSI_ESCAPE_RE.sub("", s)
    # Normalize common control chars that can create spinner artifacts
    s = s.replace("\r", "")
    # Drop the Unicode replacement character if it remains
    s = s.replace("\uFFFD", "")
    # Remove braille spinner glyphs (U+2800..U+28FF) which may appear in progress output
    s = re.sub(r"[\u2800-\u28FF]", "", s)
    # Remove other control chars except newline and tab
    s = "".join(ch for ch in s if ch in {"\n", "\t"} or ord(ch) >= 32)
    return s


def sh(cmd: list[str], check: bool = True) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout}")
    return p.stdout




def run_ollama(prompt: str) -> str:
    env = os.environ.copy()
    env["TERM"] = "dumb"

    p = subprocess.run(
        ["ollama", "run", MODEL],
        input=prompt.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    out = p.stdout.decode("utf-8", errors="ignore")
    if p.returncode != 0:
        raise RuntimeError(f"Ollama failed ({p.returncode}):\n{out}")
    return strip_ansi_and_controls(out).strip() + "\n"


def truncate(s: str, limit: int) -> tuple[str, bool]:
    if len(s) <= limit:
        return s, False
    return s[:limit] + "\n\n[TRUNCATED]\n", True


def get_changed_files(base: str, head: str) -> str:
    out = sh(
        [
            "git",
            "diff",
            "--name-only",
            f"{base}..{head}",
            "--",
            "src/main/java",
            "src/test/java",
        ],
        check=False,
    ).strip()
    return out if out else "(none)"


def get_file_content_at_sha(sha: str, path: str) -> str:
    # Reads file content from a specific commit SHA.
    # Returns empty string if the file does not exist at that SHA (deleted/renamed).
    out = sh(["git", "show", f"{sha}:{path}"], check=False)
    if out.startswith("fatal:"):
        return ""
    return out


def truncate_labeled(s: str, limit: int, label: str) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n\n[TRUNCATED {label}]\n"




def main() -> None:
    base = os.getenv("PERFGUARD_BASE_SHA")
    head = os.getenv("PERFGUARD_HEAD_SHA")
    pr_number = os.getenv("PERFGUARD_PR_NUMBER", "")
    pr_title = os.getenv("PERFGUARD_PR_TITLE", "")
    pr_desc = os.getenv("PERFGUARD_PR_DESCRIPTION", "")

    if not base or not head:
        raise SystemExit("Missing PERFGUARD_BASE_SHA or PERFGUARD_HEAD_SHA")

    changed_files = get_changed_files(base, head)
    if changed_files.strip() == "(none)":
        report = f"""## PerfGuard – PR Performance Review

**PR:** {pr_number}  
**Range:** `{base[:7]}..{head[:7]}`  
**Generated:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

No relevant Java file changes detected under `src/main/java` or `src/test/java`.
"""
        with open("perfguard_report.md", "w", encoding="utf-8") as f:
            f.write(report)
        return


    # Analysis behavior:
    # 1) Determine all changed files.
    # 2) For each changed file, send full file content at PR head to the model.
    # 3) Run a final combine pass to produce a single PR-level report.

    file_analyses: List[str] = []
    changed_file_list = [f.strip() for f in changed_files.splitlines() if f.strip() and f.strip() != "(none)"]

    for path in changed_file_list:
        # Only analyze Java source and tests.
        if not (path.startswith("src/main/java/") or path.startswith("src/test/java/")):
            continue
        if not path.endswith(".java"):
            continue

        file_content_raw = get_file_content_at_sha(head, path)
        file_content = truncate_labeled(file_content_raw, MAX_FILE_CHARS, "FILE_CONTENT")

        per_file_prompt = FILE_ANALYSIS_PROMPT.format(
            PR_TITLE=pr_title,
            PR_DESCRIPTION=pr_desc,
            FILE_PATH=path,
            FILE_CONTENT=file_content if file_content else "(file content unavailable at head)\n",
        )

        per_file_out = run_ollama(per_file_prompt)
        per_file_out = truncate_labeled(per_file_out, MAX_FILE_ANALYSIS_CHARS, "MODEL_OUTPUT")

        file_analyses.append(f"FILE_PATH: {path}\n" + per_file_out.strip() + "\n")

    if not file_analyses:
        analysis_out = "No relevant Java changes detected for analysis."
    else:
        analyzed_paths = [
            p for p in changed_file_list
            if (p.startswith("src/main/java/") or p.startswith("src/test/java/")) and p.endswith(".java")
        ]
        files_analyzed_block = "\n".join([f"- {p}" for p in analyzed_paths])

        combine_input = "\n\n".join(file_analyses)
        combine_prompt = (
            COMBINE_PROMPT.format(FILES_ANALYZED=files_analyzed_block)
            + "\n\n---\n\n"
            + "Per-file analyses (do not repeat verbatim):\n\n"
            + combine_input
        )
        analysis_out = run_ollama(combine_prompt).strip()

        if not analysis_out:
            analysis_out = "No significant performance or maintainability risks detected in this PR."

    llm_out = (analysis_out or "").strip() + "\n"

    llm_out, out_truncated = truncate(llm_out, MAX_OUTPUT_CHARS)

    header = [
        "## PerfGuard – PR Performance Review",
        "",
        f"**PR:** {pr_number}  ",
        f"**Range:** `{base[:7]}..{head[:7]}`  ",
        f"**Model:** `{MODEL}`  ",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    if out_truncated:
        header.append("> Note: Model output was truncated for safety.\n")

    report = "\n".join(header) + "\n" + llm_out.strip() + "\n"

    with open("perfguard_report.md", "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    main()