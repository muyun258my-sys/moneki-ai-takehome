"""分词。"""

from __future__ import annotations

import re
import unicodedata

#: 分词规则变了，索引缓存必须失效。
TOKENIZER_VERSION = "tokenizer-3"

#: 中文里几乎不携带信息的字。只用在“查询覆盖率”上，索引照常保留全部词。
STOP_CHARS = frozenset("的了吗呢是在有和与及或就都也还把被给对从向于个些这那哪什么怎样如何多少几请帮我你他它可以能要想会一下少吧啊呀们么样过得着为所")
STOP_WORDS = frozenset("the a an of to in is are and or for on at it this that how what".split())

#: 中文连续字串，或英文字母/数字串。二者之外（标点、空白）不参与分词。
_TOKEN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+|[a-z0-9]+")


def normalise(text: str) -> str:
    """全角转半角、统一大小写，比较与分词都走这一层。"""
    return unicodedata.normalize("NFKC", text or "").lower()


def tokenize(text: str) -> list[str]:
    """中文切成重叠二元组（bigram），英文/数字按词切，直接喂给 BM25。"""
    tokens: list[str] = []
    for match in _TOKEN.finditer(normalise(text)):
        word = match.group(0)
        if word[0].isascii() or len(word) == 1:
            tokens.append(word)
        else:
            tokens.extend(word[index : index + 2] for index in range(len(word) - 1))
    return tokens


def content_tokens(text: str) -> list[str]:
    """去掉虚词之后的查询词，用来算“这个问题被文档覆盖了多少”。"""
    kept = []
    for token in tokenize(text):
        if token in STOP_WORDS:
            continue
        if all(char in STOP_CHARS for char in token):
            continue
        kept.append(token)
    return kept
