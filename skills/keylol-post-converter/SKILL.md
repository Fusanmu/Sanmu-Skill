---
name: keylol-post-converter
description: Convert attached or local Markdown and plain-text review documents into native Keylol (其乐) forum BBCode with [postbg], [index], [K0]/[K1] headings, heading-based [page] pagination, body styling, output files, and a machine-readable warning report. Use when the user asks to 转其乐格式, 转成其乐论坛格式, 转 Keylol 发帖代码, 按其乐评测模板排版, generate Keylol BBCode, or invokes $keylol-post-converter for a .md, .markdown, or .txt source document.
---

# Keylol Post Converter

Convert the user's source document without rewriting its substance. Use the bundled script for deterministic conversion; do not manually reconstruct long BBCode.

## Workflow

1. Identify the single source `.md`, `.markdown`, or `.txt` file supplied or named by the user. If several candidates exist and intent is unclear, ask which one to convert.
2. Keep the source unchanged. Put deliverables in the current workspace's `outputs` directory unless the user chooses another writable location.
3. Resolve Python deterministically:
   - In Codex Desktop, call the workspace-dependencies helper first and use the Python executable it returns.
   - Otherwise try `py -3`, then `python`.
   - Do not scan drives or install packages; the converter has no third-party dependencies.
   - If none of these routes provides Python, stop and report that an interpreter is unavailable.
4. Run `scripts/convert.py` with explicit absolute input, output, and report paths.
5. Use these defaults unless the user specifies otherwise:
   - Add the Keylol post background `[postbg]bg4.png[/postbg]`.
   - Generate a native `[index]` from level-2 headings (`##`).
   - Keep the index and the first section together on page 1.
   - Render `##` as `[K0]` and `###` as `[K1]`.
   - Start each later `##` section with `[page]`.
   - Treat the first `#` heading as thread-title metadata: record it in the report and omit it from the post body.
   - Style normal body paragraphs as Microsoft YaHei size 4 and normalize each first-line indent to exactly two full-width spaces, without stacking existing source indentation. Style list items with the same font and size without the paragraph indent.
6. Read the generated JSON report. Check `warnings`, `page_count`, and the heading/page mapping before delivery.
7. Deliver the `.keylol.txt` file and briefly state page count and material warnings. Also deliver the `.report.json` file when warnings exist or the user requests diagnostics.

Run the converter as follows:

```powershell
python scripts/convert.py INPUT.md -o OUTPUT.keylol.txt --report OUTPUT.report.json
```

Use `--split-level 0` to disable content pagination, `--no-toc` to omit the native index, `--post-background FILE` to choose another Keylol background, or `--no-post-background` to omit it. `--toc-depth` remains accepted for command compatibility, but the native index contains page headings only. Use `--self-test` after modifying the converter.

## Guardrails

- Preserve wording, paragraph order, links, and code unless the user explicitly requests editing.
- Never overwrite the source file.
- Never invent public URLs for local images. Leave a visible placeholder and report the image for manual upload.
- Do not claim the result will render identically without checking Keylol's editor preview; forum-side BBCode support can change.
- If an attachment cannot be passed to the script directly, read it through an available document tool, save a temporary UTF-8 Markdown file in the workspace, and convert that file.
- For unsupported source formats such as `.docx` or `.pdf`, first extract the document to Markdown with the appropriate document skill, then run this converter.

Read [references/keylol-format-rules.md](references/keylol-format-rules.md) only when diagnosing output, changing conversion behavior, or explaining the mapping.
