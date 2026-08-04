# Keylol conversion rules

The converter targets the Discuz-style BBCode used by Keylol posts. Treat the generated text as a publishing draft and check it in the forum editor preview before posting.

## Defaults

- The post begins with `[postbg]bg4.png[/postbg]`.
- The native `[index]` and first `##` section share page 1.
- The native index contains one `[#N]` entry for each `##` page heading.
- Each later `##` heading starts a new page with `[page]`.
- The first `#` heading is treated as the forum thread title: it is recorded as `document_title` in the report and omitted from the post body.
- Normal paragraphs use Microsoft YaHei at size 4. Existing leading spaces are normalized so each paragraph starts with exactly two full-width spaces.
- The source wording is preserved; this is formatting conversion, not editing.

## Markdown mapping

| Markdown | BBCode |
| --- | --- |
| First `#` heading | Thread-title metadata; omitted from body |
| `##` heading | `[K0]heading[/K0]` and a native index entry |
| `###` heading | `[K1]heading[/K1]` |
| `####` through `######` | Bold text with decreasing `[size]` |
| Normal paragraph | `[font=微软雅黑][size=4]　　text[/size][/font]` |
| `**bold**` | `[b]bold[/b]` |
| `*italic*` | `[i]italic[/i]` |
| `~~strike~~` | `[s]strike[/s]` |
| Inline code | `[font=Courier New]...[/font]` |
| Fenced or indented code | `[code]...[/code]` |
| Link | `[url=URL]label[/url]` |
| Remote image | `[img]URL[/img]` |
| Blockquote | `[quote]...[/quote]` |
| Horizontal rule | `[hr]` |
| List | `[list]` or `[list=1]` with styled `[*]` items |
| Table | `[table]`, `[tr]`, and `[td]` |
| Page boundary | `[page]` |

## Native page structure

```text
[postbg]bg4.png[/postbg]
[index]
[#1]前言
[#2]角色、伏笔与Meta
[/index]

[K0]前言[/K0]
[font=微软雅黑][size=4]　　正文[/size][/font]

[page]
[K0]角色、伏笔与Meta[/K0]
[K1]生动的角色群像[/K1]
```

## Warnings

- Local and relative images cannot be uploaded by conversion alone. They remain visible as `【待上传图片：path】` and are listed in the report.
- Raw HTML is preserved as text and reported because Keylol may not render it.
- Nested lists are flattened and reported.
- Unterminated code fences are closed at end of file and reported.
- Existing raw BBCode is preserved but reported because it may interact with generated tags.
