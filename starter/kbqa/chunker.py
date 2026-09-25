"""把文档切成检索用的小块。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .loader import Document

#: 切块参数变了，索引缓存必须失效，所以写进缓存键里。
CHUNKER_VERSION = "chunker-5"

CHUNK_SIZE = 300

_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    text: str
    source_text: str
    heading: str = ""
    kind: str = "text"
    table_header: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source_text": self.source_text,
            "heading": self.heading,
            "kind": self.kind,
            "table_header": self.table_header,
        }


def _cells(line: str) -> list[str]:
    match = _TABLE_ROW.match(line)
    return [cell.strip() for cell in match.group(1).split("|")] if match else []


def _split_blocks(text: str) -> list[tuple[str, str]]:
    """把正文切成 (kind, raw) 块：`table` 是 Markdown 表格，其余是 `text`。"""
    lines = text.splitlines()
    blocks: list[tuple[str, str]] = []
    buffer: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if (
            _TABLE_ROW.match(line)
            and index + 1 < len(lines)
            and _TABLE_SEP.match(lines[index + 1])
        ):
            if buffer:
                blocks.append(("text", "\n".join(buffer)))
                buffer = []
            table = [line, lines[index + 1]]
            index += 2
            while index < len(lines) and _TABLE_ROW.match(lines[index]):
                table.append(lines[index])
                index += 1
            blocks.append(("table", "\n".join(table)))
            continue
        buffer.append(line)
        index += 1
    if buffer:
        blocks.append(("text", "\n".join(buffer)))
    return blocks


def _text_chunks(text: str) -> list[str]:
    """按约 300 字打包，但只在句号/问号/换行处断，不把一句话拦腰截断。"""
    text = text.strip("\n")
    if not text:
        return []
    boundaries = [match.end() for match in re.finditer(r"[。！？!?\n]", text)]
    starts = [0] + boundaries
    ends = starts[1:] + [len(text)]
    sentences: list[str] = []
    for start, end in zip(starts, ends):
        piece = text[start:end]
        if piece.strip():
            sentences.append(piece)
        elif sentences:
            # “。”后面紧跟的换行会单独切成一段：它是分行的依据，接回上一句，不能丢。
            # 丢了的话列表的各条、小标题都会粘成一行，引用时就把相邻几条连着引出来。
            sentences[-1] += piece
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > CHUNK_SIZE:
            chunks.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def chunk_document(document: Document) -> list[Chunk]:
    """一篇文档切成 text 块和 table 块；text 块 300 字一块、末段保留。"""
    chunks: list[Chunk] = []
    number = 0
    for kind, raw in _split_blocks(document.text):
        if kind == "table":
            header = _cells(raw.splitlines()[0])
            rows = [_cells(line) for line in raw.splitlines()[2:] if _TABLE_ROW.match(line)]
            flat = " ".join(header + [" ".join(row) for row in rows]).strip()
            number += 1
            chunks.append(
                Chunk(
                    doc_id=document.doc_id,
                    chunk_id="%s#%d" % (document.doc_id, number),
                    text=flat,
                    source_text=raw,
                    heading=document.title,
                    kind="table",
                    table_header=header,
                )
            )
        else:
            for piece in _text_chunks(raw):
                number += 1
                chunks.append(
                    Chunk(
                        doc_id=document.doc_id,
                        chunk_id="%s#%d" % (document.doc_id, number),
                        text=piece,
                        source_text=piece,
                        heading=document.title,
                    )
                )
    if not chunks:
        chunks.append(
            Chunk(
                doc_id=document.doc_id,
                chunk_id="%s#1" % document.doc_id,
                text=document.title,
                source_text=document.title,
                heading=document.title,
            )
        )
    return chunks


def chunk_documents(documents: list[Document]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(chunk_document(document))
    return chunks
