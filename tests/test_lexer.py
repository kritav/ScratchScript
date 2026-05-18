"""Tests for the ScratchScript lexer."""

from scratchscript.compiler.lexer import Token, TokenType, tokenize, LexerError
import pytest


def token_types(source: str) -> list[TokenType]:
    """Helper: return just the token types for source."""
    return [t.type for t in tokenize(source)]


def token_values(source: str) -> list[tuple[TokenType, str]]:
    """Helper: return (type, value) pairs."""
    return [(t.type, t.value) for t in tokenize(source)]


class TestBasicTokens:
    def test_empty_source(self):
        tokens = tokenize("")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_single_keyword(self):
        tokens = tokenize("project")
        assert tokens[0].type == TokenType.KEYWORD
        assert tokens[0].value == "project"

    def test_identifier(self):
        tokens = tokenize("mySprite")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "mySprite"

    def test_number_integer(self):
        tokens = tokenize("42")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "42"

    def test_number_float(self):
        tokens = tokenize("3.14")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "3.14"

    def test_string_double_quotes(self):
        tokens = tokenize('"hello world"')
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"

    def test_string_single_quotes(self):
        tokens = tokenize("'hello'")
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello"

    def test_color_literal(self):
        tokens = tokenize("#ff0000")
        assert tokens[0].type == TokenType.COLOR
        assert tokens[0].value == "#ff0000"

    def test_operators(self):
        tokens = tokenize("+ - * / > < =")
        ops = [t for t in tokens if t.type == TokenType.OPERATOR]
        assert [o.value for o in ops] == ["+", "-", "*", "/", ">", "<", "="]

    def test_punctuation(self):
        tokens = tokenize("( ) , :")
        types = [t.type for t in tokens if t.type not in (TokenType.NEWLINE, TokenType.EOF)]
        assert types == [TokenType.LPAREN, TokenType.RPAREN, TokenType.COMMA, TokenType.COLON]


class TestIndentation:
    def test_single_indent(self):
        source = "project\n  sprite"
        types = token_types(source)
        assert TokenType.INDENT in types
        # One DEDENT at EOF
        assert types.count(TokenType.DEDENT) == 1

    def test_indent_dedent(self):
        source = "project\n  sprite\nend"
        types = token_types(source)
        assert types.count(TokenType.INDENT) == 1
        assert types.count(TokenType.DEDENT) == 1

    def test_nested_indent(self):
        source = "a\n  b\n    c\nd"
        types = token_types(source)
        assert types.count(TokenType.INDENT) == 2
        assert types.count(TokenType.DEDENT) == 2

    def test_multiple_dedent(self):
        source = "a\n  b\n    c\nd"
        types = token_types(source)
        # After "c" we should get two dedents before "d"
        dedent_count = 0
        found_c = False
        for t in tokenize(source):
            if t.type == TokenType.IDENTIFIER and t.value == "c":
                found_c = True
            if found_c and t.type == TokenType.DEDENT:
                dedent_count += 1
            if t.type == TokenType.IDENTIFIER and t.value == "d":
                break
        assert dedent_count == 2


class TestComments:
    def test_line_comment_double_slash(self):
        source = "move 10 // this is a comment"
        tokens = [t for t in tokenize(source) if t.type not in (TokenType.NEWLINE, TokenType.EOF)]
        # Should not include comment text
        values = [t.value for t in tokens]
        assert "this" not in values
        assert "comment" not in values

    def test_blank_lines_skipped(self):
        source = "a\n\n\nb"
        tokens = [t for t in tokenize(source) if t.type not in (TokenType.NEWLINE, TokenType.EOF)]
        assert len(tokens) == 2
        assert tokens[0].value == "a"
        assert tokens[1].value == "b"


class TestLineNumbers:
    def test_line_numbers(self):
        source = "project\n  sprite Cat"
        tokens = tokenize(source)
        proj = next(t for t in tokens if t.value == "project")
        assert proj.line == 1
        cat = next(t for t in tokens if t.value == "Cat")
        assert cat.line == 2


class TestKeywords:
    def test_all_keywords_recognized(self):
        for kw in ["project", "sprite", "when", "if", "else", "end",
                    "forever", "repeat", "until", "variable", "list",
                    "set", "change", "to", "by", "show", "hide",
                    "and", "or", "not", "stop", "define", "broadcast"]:
            tokens = tokenize(kw)
            assert tokens[0].type == TokenType.KEYWORD, f"{kw} not recognized as keyword"

    def test_case_insensitive_keywords(self):
        tokens = tokenize("Project")
        assert tokens[0].type == TokenType.KEYWORD
        assert tokens[0].value == "project"


class TestErrors:
    def test_unterminated_string(self):
        with pytest.raises(LexerError, match="Unterminated string"):
            tokenize('"hello')

    def test_unexpected_character(self):
        with pytest.raises(LexerError):
            tokenize("@")


class TestComplexInput:
    def test_full_script(self):
        source = '''project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        move 10
        say "Hello" 2
        if touching "edge"
          turn right 180
        end
'''
        tokens = tokenize(source)
        # Should not raise
        assert tokens[-1].type == TokenType.EOF
        # Check we get some reasonable tokens
        kws = [t.value for t in tokens if t.type == TokenType.KEYWORD]
        assert "project" in kws
        assert "sprite" in kws
        assert "when" in kws
        assert "if" in kws
