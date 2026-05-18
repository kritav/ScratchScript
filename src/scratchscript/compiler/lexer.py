"""Indentation-aware tokenizer for ScratchScript."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator


class TokenType(Enum):
    # Structure
    INDENT = auto()
    DEDENT = auto()
    NEWLINE = auto()
    EOF = auto()

    # Keywords
    KEYWORD = auto()

    # Literals
    NUMBER = auto()
    STRING = auto()
    COLOR = auto()

    # Identifiers and operators
    IDENTIFIER = auto()
    OPERATOR = auto()

    # Punctuation
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    COLON = auto()


KEYWORDS = frozenset({
    "project", "sprite", "stage",
    "script", "when", "define",
    "if", "else", "end",
    "forever", "repeat", "until",
    "variable", "list", "global",
    "set", "change", "to", "by",
    "show", "hide",
    "add", "delete", "insert", "replace", "at", "of", "in", "all", "item",
    "and", "or", "not", "mod",
    "true", "false",
    "stop", "create", "clone", "myself",
    "costumes", "sounds", "backdrops",
    "position", "size", "direction", "visible", "rotation",
    "broadcast", "receive",
    "wait",
})

# Multi-character operators
OPERATORS = frozenset({"+", "-", "*", "/", ">", "<", "=", "%"})


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, line={self.line})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        self.line = line
        self.column = column
        super().__init__(f"Line {line}: {message}")


def tokenize(source: str) -> list[Token]:
    """Tokenize ScratchScript source code into a list of tokens."""
    tokens: list[Token] = []
    indent_stack: list[int] = [0]
    lines = source.split("\n")

    for line_num, line in enumerate(lines, start=1):
        # Skip empty lines and comment-only lines
        stripped = line.lstrip()
        if not stripped or stripped.startswith("//"):
            continue
        # Skip #-comments, but not #rrggbb color literals
        if stripped.startswith("#") and not re.match(r"#[0-9a-fA-F]{6}\b", stripped):
            continue

        # Calculate indentation (count spaces; 1 tab = 4 spaces)
        indent = 0
        for ch in line:
            if ch == " ":
                indent += 1
            elif ch == "\t":
                indent += 4
            else:
                break

        # Emit INDENT/DEDENT tokens
        if indent > indent_stack[-1]:
            indent_stack.append(indent)
            tokens.append(Token(TokenType.INDENT, "", line_num, 0))
        else:
            while indent < indent_stack[-1]:
                indent_stack.pop()
                tokens.append(Token(TokenType.DEDENT, "", line_num, 0))
            if indent != indent_stack[-1]:
                raise LexerError(
                    f"Inconsistent indentation (got {indent}, expected {indent_stack[-1]})",
                    line_num, indent,
                )

        # Tokenize the line content
        tokens.extend(_tokenize_line(stripped, line_num, indent))
        tokens.append(Token(TokenType.NEWLINE, "\\n", line_num, len(line)))

    # Emit remaining DEDENTs at EOF
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token(TokenType.DEDENT, "", len(lines), 0))

    tokens.append(Token(TokenType.EOF, "", len(lines), 0))
    return tokens


def _tokenize_line(line: str, line_num: int, base_col: int) -> Iterator[Token]:
    """Tokenize a single line of content (without leading whitespace)."""
    i = 0
    while i < len(line):
        ch = line[i]

        # Skip whitespace within a line
        if ch in " \t":
            i += 1
            continue

        # Comments (// or # but not #rrggbb color literals)
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break

        col = base_col + i

        # Color literal (#rrggbb) — must check before treating # as comment
        if ch == "#" and i + 1 < len(line):
            m = re.match(r"#[0-9a-fA-F]{6}\b", line[i:])
            if m:
                yield Token(TokenType.COLOR, m.group(), line_num, col)
                i += len(m.group())
                continue
            # Not a color — treat as comment
            break

        if ch == "#":
            break

        # String literal
        if ch == '"':
            end = line.find('"', i + 1)
            if end == -1:
                raise LexerError("Unterminated string literal", line_num, col)
            value = line[i + 1 : end]
            yield Token(TokenType.STRING, value, line_num, col)
            i = end + 1
            continue

        # Single-quoted string
        if ch == "'":
            end = line.find("'", i + 1)
            if end == -1:
                raise LexerError("Unterminated string literal", line_num, col)
            value = line[i + 1 : end]
            yield Token(TokenType.STRING, value, line_num, col)
            i = end + 1
            continue

        # Number literal (including negative handled as operator + number)
        if ch.isdigit() or (ch == "." and i + 1 < len(line) and line[i + 1].isdigit()):
            m = re.match(r"\d+\.?\d*", line[i:])
            if m:
                yield Token(TokenType.NUMBER, m.group(), line_num, col)
                i += len(m.group())
                continue

        # Operators
        if ch in OPERATORS:
            yield Token(TokenType.OPERATOR, ch, line_num, col)
            i += 1
            continue

        # Punctuation
        if ch == "(":
            yield Token(TokenType.LPAREN, "(", line_num, col)
            i += 1
            continue
        if ch == ")":
            yield Token(TokenType.RPAREN, ")", line_num, col)
            i += 1
            continue
        if ch == ",":
            yield Token(TokenType.COMMA, ",", line_num, col)
            i += 1
            continue
        if ch == ":":
            yield Token(TokenType.COLON, ":", line_num, col)
            i += 1
            continue

        # Identifiers / keywords
        if ch.isalpha() or ch == "_":
            m = re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", line[i:])
            if m:
                word = m.group()
                if word.lower() in KEYWORDS:
                    yield Token(TokenType.KEYWORD, word.lower(), line_num, col)
                elif word.lower() in ("true", "false"):
                    yield Token(TokenType.KEYWORD, word.lower(), line_num, col)
                else:
                    yield Token(TokenType.IDENTIFIER, word, line_num, col)
                i += len(word)
                continue

        raise LexerError(f"Unexpected character: {ch!r}", line_num, col)
