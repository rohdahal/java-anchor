# Java Anchor

A minimal Spring Boot project that demonstrates how to run PerfGuard performance/maintainability reviews in GitHub pull requests. The repository includes a GitHub Actions workflow that analyzes changed Java files with a local LLM (Ollama) and posts a structured report as a PR comment.

## What this repo contains

- A barebones Spring Boot 4 application (Java 17, Maven).
- A PerfGuard scanner script that performs per-file reviews and a combined PR-level report.
- A GitHub Actions workflow that runs the scanner and posts or updates a PR comment.


## How PerfGuard works here

The scanner:

1. Collects changed files between `PERFGUARD_BASE_SHA` and `PERFGUARD_HEAD_SHA`.
2. Filters to `src/main/java` and `src/test/java`, only `*.java` files.
3. Sends each file (full content at PR head) to the model for analysis.
4. Runs a combine pass to create a single PR-level report.
5. Writes `perfguard_report.md`, which the GitHub workflow posts as a PR comment.

Notes:

- The analysis is conservative and limited to performance/maintainability risks.
- The report is truncated if it exceeds `PERFGUARD_MAX_OUTPUT_CHARS`.

## GitHub Actions workflow

The workflow in `.github/workflows/perfguard.yml` runs on PR events:

- Checks out the PR head.
- Installs Python 3.11 and Ollama.
- Pulls the `qwen2.5-coder:1.5b` model (default).
- Executes `perfguard/scan.py` with PR metadata.
- Posts or updates a PR comment with the report.

## Local development

### Prerequisites

- Java 17
- Maven
- Python 3.11 (only needed to run the scanner locally)
- Ollama (for local LLM runs)

### Run the Spring Boot app

```bash
./mvnw spring-boot:run
```

### Run tests

```bash
./mvnw test
```

### Run PerfGuard locally

You need two commit SHAs to compare (base and head). The scanner will generate `perfguard_report.md` in the repo root.

```bash
export PERFGUARD_BASE_SHA=<base_sha>
export PERFGUARD_HEAD_SHA=<head_sha>
export PERFGUARD_PR_NUMBER=local
export PERFGUARD_PR_TITLE="Local PerfGuard Run"
export PERFGUARD_PR_DESCRIPTION="Manual run"

python perfguard/scan.py
```

## Configuration

The scanner is configured via environment variables:

- `PERFGUARD_MODEL` (default: `qwen2.5-coder:1.5b`)
- `PERFGUARD_MAX_OUTPUT_CHARS` (default: `50000`)
- `PERFGUARD_MAX_FILE_CHARS` (default: `80000`)
- `PERFGUARD_MAX_FILE_ANALYSIS_CHARS` (default: `20000`)

The workflow supplies these per run:

- `PERFGUARD_BASE_SHA` / `PERFGUARD_HEAD_SHA`
- `PERFGUARD_PR_NUMBER`
- `PERFGUARD_PR_TITLE`
- `PERFGUARD_PR_DESCRIPTION`

## Limitations

- Only Java files in `src/main/java` and `src/test/java` are analyzed.
- Non-Java files are ignored.
- The LLM does not execute code or run benchmarks; it analyzes file content only.

## License

The Unlicense: This software is released into the public domain and may be used, modified, and distributed for any purpose, with or without attribution.
