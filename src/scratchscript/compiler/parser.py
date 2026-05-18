"""Recursive descent parser for ScratchScript."""

from __future__ import annotations

from typing import Optional

from .ast_nodes import (
    BinaryOp,
    Block,
    ChangeVariable,
    CloneBlock,
    ColorLiteral,
    CustomBlockCall,
    CustomBlockDef,
    Expression,
    ForeverBlock,
    FunctionCall,
    HideVariable,
    IfBlock,
    ListDecl,
    ListOperation,
    ListRef,
    Literal,
    Project,
    RepeatBlock,
    RepeatUntilBlock,
    Script,
    SetVariable,
    ShowVariable,
    Sprite,
    Statement,
    StopBlock,
    UnaryOp,
    VarRef,
    VariableDecl,
)
from .lexer import Token, TokenType, tokenize


class ParseError(Exception):
    def __init__(self, message: str, line: int = 0):
        self.line = line
        super().__init__(f"Line {line}: {message}" if line else message)


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.errors: list[str] = []
        self._custom_blocks: set[str] = set()

    # --- Token navigation ---

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def _advance(self) -> Token:
        tok = self._current()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def _expect(self, ttype: TokenType, value: Optional[str] = None) -> Token:
        tok = self._current()
        if tok.type != ttype:
            raise ParseError(
                f"Expected {ttype.name} but got {tok.type.name} ({tok.value!r})",
                tok.line,
            )
        if value is not None and tok.value != value:
            raise ParseError(
                f"Expected {value!r} but got {tok.value!r}",
                tok.line,
            )
        return self._advance()

    def _match(self, ttype: TokenType, value: Optional[str] = None) -> Optional[Token]:
        tok = self._current()
        if tok.type == ttype and (value is None or tok.value == value):
            return self._advance()
        return None

    def _skip_newlines(self):
        while self._current().type == TokenType.NEWLINE:
            self._advance()

    def _at_end(self) -> bool:
        return self._current().type == TokenType.EOF

    def _at_block_end(self) -> bool:
        """Check if we're at a DEDENT or EOF (end of indented block)."""
        return self._current().type in (TokenType.DEDENT, TokenType.EOF)

    # --- Top-level parsing ---

    def parse(self) -> Project:
        """Parse tokens into a Project AST."""
        self._skip_newlines()
        project = self._parse_project()
        return project

    def _parse_project(self) -> Project:
        project = Project()
        line = self._current().line

        # Optional "project" declaration
        if self._match(TokenType.KEYWORD, "project"):
            if self._current().type == TokenType.IDENTIFIER:
                project.name = self._advance().value
            elif self._current().type == TokenType.STRING:
                project.name = self._advance().value
            self._skip_newlines()

            # Enter indented block
            if self._match(TokenType.INDENT):
                self._parse_project_body(project)
                self._match(TokenType.DEDENT)
        else:
            # No project wrapper — parse sprites and scripts at top level
            self._parse_project_body(project)

        project.line = line
        return project

    def _parse_project_body(self, project: Project):
        """Parse the body of a project (sprites, variables, scripts, etc.)."""
        while not self._at_end() and not self._at_block_end():
            self._skip_newlines()
            if self._at_end() or self._at_block_end():
                break

            tok = self._current()

            if tok.type == TokenType.KEYWORD and tok.value == "sprite":
                project.sprites.append(self._parse_sprite())
            elif tok.type == TokenType.KEYWORD and tok.value == "stage":
                self._parse_stage(project)
            elif tok.type == TokenType.KEYWORD and tok.value == "backdrops":
                self._advance()
                project.backdrops = self._parse_string_list()
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "variable":
                project.variables.append(self._parse_variable_decl(is_global=True))
            elif tok.type == TokenType.KEYWORD and tok.value == "list":
                project.lists.append(self._parse_list_decl(is_global=True))
            elif tok.type == TokenType.KEYWORD and tok.value == "script":
                project.stage_scripts.append(self._parse_script())
            elif tok.type == TokenType.KEYWORD and tok.value == "define":
                project.stage_custom_blocks.append(self._parse_custom_block_def())
            else:
                self._error(f"Unexpected token in project body: {tok.value!r}")
                self._advance()
                self._skip_newlines()

    def _parse_stage(self, project: Project):
        """Parse a stage block (like sprite but for the stage)."""
        self._expect(TokenType.KEYWORD, "stage")
        self._skip_newlines()

        if not self._match(TokenType.INDENT):
            return

        while not self._at_end() and not self._at_block_end():
            self._skip_newlines()
            if self._at_end() or self._at_block_end():
                break

            tok = self._current()
            if tok.type == TokenType.KEYWORD and tok.value == "backdrops":
                self._advance()
                project.backdrops = self._parse_string_list()
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "variable":
                project.variables.append(self._parse_variable_decl(is_global=True))
            elif tok.type == TokenType.KEYWORD and tok.value == "list":
                project.lists.append(self._parse_list_decl(is_global=True))
            elif tok.type == TokenType.KEYWORD and tok.value == "script":
                project.stage_scripts.append(self._parse_script())
            elif tok.type == TokenType.KEYWORD and tok.value == "define":
                project.stage_custom_blocks.append(self._parse_custom_block_def())
            elif tok.type == TokenType.KEYWORD and tok.value == "sounds":
                self._advance()
                self._parse_string_list()  # consume but stage sounds not stored
                self._skip_newlines()
            else:
                self._error(f"Unexpected token in stage body: {tok.value!r}")
                self._advance()
                self._skip_newlines()

        self._match(TokenType.DEDENT)

    def _parse_sprite(self) -> Sprite:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "sprite")

        name = "Sprite1"
        if self._current().type == TokenType.IDENTIFIER:
            name = self._advance().value
        elif self._current().type == TokenType.STRING:
            name = self._advance().value

        sprite = Sprite(name=name, line=line)
        self._skip_newlines()

        if not self._match(TokenType.INDENT):
            return sprite

        while not self._at_end() and not self._at_block_end():
            self._skip_newlines()
            if self._at_end() or self._at_block_end():
                break

            tok = self._current()

            if tok.type == TokenType.KEYWORD and tok.value == "costumes":
                self._advance()
                sprite.costumes = self._parse_string_list()
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "sounds":
                self._advance()
                sprite.sounds = self._parse_string_list()
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "position":
                self._advance()
                x = self._parse_number()
                self._match(TokenType.COMMA)
                y = self._parse_number()
                sprite.x = x
                sprite.y = y
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "size":
                self._advance()
                sprite.size = self._parse_number()
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "direction":
                self._advance()
                sprite.direction = self._parse_number()
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "visible":
                self._advance()
                val = self._current()
                if val.type == TokenType.KEYWORD and val.value == "false":
                    sprite.visible = False
                    self._advance()
                elif val.type == TokenType.KEYWORD and val.value == "true":
                    sprite.visible = True
                    self._advance()
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "rotation":
                self._advance()
                # "rotation left-right" or "rotation don't rotate" or "rotation all around"
                parts = []
                while self._current().type in (TokenType.IDENTIFIER, TokenType.KEYWORD) and self._current().type != TokenType.NEWLINE:
                    parts.append(self._advance().value)
                sprite.rotation_style = " ".join(parts) if parts else "all around"
                self._skip_newlines()
            elif tok.type == TokenType.KEYWORD and tok.value == "variable":
                sprite.variables.append(self._parse_variable_decl())
            elif tok.type == TokenType.KEYWORD and tok.value == "list":
                sprite.lists.append(self._parse_list_decl())
            elif tok.type == TokenType.KEYWORD and tok.value == "script":
                sprite.scripts.append(self._parse_script())
            elif tok.type == TokenType.KEYWORD and tok.value == "define":
                cb = self._parse_custom_block_def()
                sprite.custom_blocks.append(cb)
                self._custom_blocks.add(cb.name)
            elif tok.type == TokenType.KEYWORD and tok.value == "global":
                self._advance()
                if self._current().value == "variable":
                    sprite.variables.append(self._parse_variable_decl(is_global=True))
                elif self._current().value == "list":
                    sprite.lists.append(self._parse_list_decl(is_global=True))
                else:
                    self._error("Expected 'variable' or 'list' after 'global'")
                    self._advance()
            else:
                self._error(f"Unexpected token in sprite body: {tok.value!r}")
                self._advance()
                self._skip_newlines()

        self._match(TokenType.DEDENT)
        return sprite

    def _parse_script(self) -> Script:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "script")
        self._skip_newlines()

        if not self._match(TokenType.INDENT):
            return Script(event="when flag clicked", line=line)

        # Parse event trigger
        event, event_args = self._parse_event()
        self._skip_newlines()

        # The body might be indented further or at the same level
        body: list[Statement] = []
        if self._match(TokenType.INDENT):
            body = self._parse_block_list()
            self._match(TokenType.DEDENT)
        else:
            # Body at same indentation as event
            body = self._parse_block_list()

        self._match(TokenType.DEDENT)
        return Script(event=event, event_args=event_args, body=body, line=line)

    def _parse_event(self) -> tuple[str, list[str]]:
        """Parse an event trigger line. Returns (event_name, event_args)."""
        tok = self._current()

        if tok.type == TokenType.KEYWORD and tok.value == "when":
            self._advance()
            return self._parse_when_event()

        # Fallback: treat as "when flag clicked"
        return "when flag clicked", []

    def _parse_when_event(self) -> tuple[str, list[str]]:
        """Parse what comes after 'when'."""
        tok = self._current()

        # "when flag clicked"
        if tok.type == TokenType.IDENTIFIER and tok.value == "flag":
            self._advance()
            self._match_identifier("clicked")
            return "when flag clicked", []

        # "when key <key> pressed"
        if (tok.type == TokenType.KEYWORD and tok.value == "key") or \
           (tok.type == TokenType.IDENTIFIER and tok.value.lower() == "key"):
            self._advance()
            key = self._parse_key_name()
            self._match_identifier("pressed")
            return "when key pressed", [key]

        # "when this sprite clicked"  /  "when stage clicked"
        if tok.type == TokenType.KEYWORD and tok.value == "this":
            self._advance()
            self._match(TokenType.KEYWORD, "sprite")
            self._match_identifier("clicked")
            return "when this sprite clicked", []

        if tok.type == TokenType.KEYWORD and tok.value == "stage":
            self._advance()
            self._match_identifier("clicked")
            return "when stage clicked", []

        # "when I receive <message>" vs "when I start as a clone"
        if tok.type == TokenType.IDENTIFIER and tok.value == "I":
            next_tok = self._peek(1)
            if next_tok.type == TokenType.KEYWORD and next_tok.value == "receive":
                self._advance()  # consume "I"
                self._advance()  # consume "receive"
                msg = self._parse_string_or_id()
                return "when I receive", [msg]
            elif next_tok.type == TokenType.IDENTIFIER and next_tok.value.lower() == "start":
                self._advance()  # consume "I"
                self._advance()  # consume "start"
                # "as a clone" — consume remaining tokens
                self._match_identifier("as")
                self._match_identifier("a")
                self._match(TokenType.KEYWORD, "clone")
                return "when I start as a clone", []
            else:
                # Unknown "when I ..." — consume rest of line
                self._advance()
                return "when I receive", [self._parse_string_or_id()]

        # "when backdrop switches to <name>"
        if tok.type == TokenType.KEYWORD and tok.value == "backdrop":
            self._advance()
            # "switches to"
            self._match_identifier("switches")
            self._match(TokenType.KEYWORD, "to")
            name = self._parse_string_or_id()
            return "when backdrop switches to", [name]

        # "when loudness > <value>"
        if tok.type == TokenType.IDENTIFIER and tok.value in ("loudness", "timer"):
            sensor = self._advance().value
            self._expect(TokenType.OPERATOR, ">")
            val = self._parse_number_str()
            return "when loudness >", [sensor.upper(), val]

        # "when clone" shorthand for "when I start as a clone"
        if tok.type == TokenType.KEYWORD and tok.value == "clone":
            self._advance()
            return "when I start as a clone", []

        # Unknown event — try to consume the rest of the line
        parts = []
        while self._current().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.INDENT, TokenType.DEDENT):
            parts.append(self._advance().value)

        event_str = "when " + " ".join(parts)
        return event_str, []

    def _match_identifier(self, name: str) -> Optional[Token]:
        """Match an identifier by value (not necessarily a keyword)."""
        tok = self._current()
        if tok.type in (TokenType.IDENTIFIER, TokenType.KEYWORD) and tok.value.lower() == name.lower():
            return self._advance()
        return None

    def _parse_key_name(self) -> str:
        """Parse a key name like 'space', 'up arrow', 'a', etc."""
        tok = self._current()
        if tok.type == TokenType.STRING:
            return self._advance().value

        name = self._advance().value
        # Check for "up arrow", "down arrow", etc.
        if name in ("up", "down", "left", "right") and self._current().value == "arrow":
            self._advance()
            return f"{name} arrow"
        return name

    def _parse_string_or_id(self) -> str:
        tok = self._current()
        if tok.type == TokenType.STRING:
            return self._advance().value
        if tok.type in (TokenType.IDENTIFIER, TokenType.KEYWORD):
            return self._advance().value
        return self._advance().value

    # --- Block list parsing ---

    def _parse_block_list(self) -> list[Statement]:
        """Parse a sequence of statements at the current indentation level."""
        stmts: list[Statement] = []
        while not self._at_end() and not self._at_block_end():
            self._skip_newlines()
            if self._at_end() or self._at_block_end():
                break
            stmt = self._parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def _parse_statement(self) -> Optional[Statement]:
        """Parse a single statement."""
        tok = self._current()
        line = tok.line

        # Control flow
        if tok.type == TokenType.KEYWORD:
            if tok.value == "if":
                # Special case: "if on edge bounce" is a motion block, not control flow
                if self._peek(1).type == TokenType.IDENTIFIER and self._peek(1).value == "on":
                    return self._parse_named_block()
                return self._parse_if()
            if tok.value == "forever":
                return self._parse_forever()
            if tok.value == "repeat":
                return self._parse_repeat()
            if tok.value == "set":
                return self._parse_set()
            if tok.value == "change":
                return self._parse_change()
            if tok.value == "show":
                return self._parse_show()
            if tok.value == "hide":
                return self._parse_hide()
            if tok.value == "add":
                return self._parse_list_add()
            if tok.value == "delete":
                return self._parse_list_delete()
            if tok.value == "insert":
                return self._parse_list_insert()
            if tok.value == "replace":
                return self._parse_list_replace()
            if tok.value == "stop":
                return self._parse_stop()
            if tok.value == "create":
                return self._parse_create_clone()
            if tok.value == "wait":
                return self._parse_wait()
            if tok.value == "broadcast":
                return self._parse_broadcast()
            if tok.value == "end":
                # Stray 'end' — skip it
                self._advance()
                self._skip_newlines()
                return None

        # Named block (motion, looks, sound, sensing, pen, etc.)
        return self._parse_named_block()

    def _parse_if(self) -> IfBlock:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "if")
        condition = self._parse_expression()
        self._skip_newlines()

        body: list[Statement] = []
        else_body: list[Statement] = []

        if self._match(TokenType.INDENT):
            body = self._parse_block_list()
            self._match(TokenType.DEDENT)

        self._skip_newlines()

        if self._match(TokenType.KEYWORD, "else"):
            self._skip_newlines()
            if self._match(TokenType.INDENT):
                else_body = self._parse_block_list()
                self._match(TokenType.DEDENT)

        # Optional 'end'
        self._skip_newlines()
        self._match(TokenType.KEYWORD, "end")
        self._skip_newlines()

        return IfBlock(condition=condition, body=body, else_body=else_body, line=line)

    def _parse_forever(self) -> ForeverBlock:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "forever")
        self._skip_newlines()

        body: list[Statement] = []
        if self._match(TokenType.INDENT):
            body = self._parse_block_list()
            self._match(TokenType.DEDENT)

        self._skip_newlines()
        self._match(TokenType.KEYWORD, "end")
        self._skip_newlines()

        return ForeverBlock(body=body, line=line)

    def _parse_repeat(self) -> RepeatBlock | RepeatUntilBlock:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "repeat")

        # "repeat until <condition>"
        if self._match(TokenType.KEYWORD, "until"):
            condition = self._parse_expression()
            self._skip_newlines()
            body: list[Statement] = []
            if self._match(TokenType.INDENT):
                body = self._parse_block_list()
                self._match(TokenType.DEDENT)
            self._skip_newlines()
            self._match(TokenType.KEYWORD, "end")
            self._skip_newlines()
            return RepeatUntilBlock(condition=condition, body=body, line=line)

        # "repeat <n>"
        times = self._parse_expression()
        self._skip_newlines()
        body = []
        if self._match(TokenType.INDENT):
            body = self._parse_block_list()
            self._match(TokenType.DEDENT)
        self._skip_newlines()
        self._match(TokenType.KEYWORD, "end")
        self._skip_newlines()
        return RepeatBlock(times=times, body=body, line=line)

    def _parse_set(self) -> SetVariable:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "set")
        name = self._parse_string_or_id()
        self._match(TokenType.KEYWORD, "to")
        value = self._parse_expression()
        self._skip_newlines()
        return SetVariable(name=name, value=value, line=line)

    def _parse_change(self) -> ChangeVariable | Block:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "change")

        tok = self._current()
        # "change x by 10", "change y by 10" — motion blocks
        if tok.type == TokenType.IDENTIFIER and tok.value in ("x", "y") and self._peek(1).value == "by":
            axis = self._advance().value
            self._expect(TokenType.KEYWORD, "by")
            val = self._parse_expression()
            self._skip_newlines()
            block_name = f"change {axis} by"
            return Block(name=block_name, args=[val], line=line)

        # "change size by N" — looks block
        if tok.type == TokenType.KEYWORD and tok.value == "size":
            self._advance()
            self._expect(TokenType.KEYWORD, "by")
            val = self._parse_expression()
            self._skip_newlines()
            return Block(name="change size by", args=[val], line=line)

        # "change effect <name> by N"
        if tok.type == TokenType.IDENTIFIER and tok.value == "effect":
            self._advance()
            effect = self._parse_string_or_id()
            self._expect(TokenType.KEYWORD, "by")
            val = self._parse_expression()
            self._skip_newlines()
            return Block(name="change effect by", args=[Literal(effect.upper(), line), val], line=line)

        # "change volume by N"
        if tok.type == TokenType.IDENTIFIER and tok.value == "volume":
            self._advance()
            self._expect(TokenType.KEYWORD, "by")
            val = self._parse_expression()
            self._skip_newlines()
            return Block(name="change volume by", args=[val], line=line)

        # "change pen size by N"
        if tok.type == TokenType.IDENTIFIER and tok.value == "pen":
            self._advance()
            self._match(TokenType.KEYWORD, "size")  # might be "size" keyword
            if self._current().type == TokenType.KEYWORD and self._current().value == "size":
                self._advance()
            self._expect(TokenType.KEYWORD, "by")
            val = self._parse_expression()
            self._skip_newlines()
            return Block(name="change pen size by", args=[val], line=line)

        # Generic: "change <varname> by <expr>"
        name = self._parse_string_or_id()
        self._match(TokenType.KEYWORD, "by")
        value = self._parse_expression()
        self._skip_newlines()
        return ChangeVariable(name=name, value=value, line=line)

    def _parse_show(self) -> ShowVariable | Block:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "show")

        tok = self._current()
        # "show variable <name>"
        if tok.type == TokenType.KEYWORD and tok.value == "variable":
            self._advance()
            name = self._parse_string_or_id()
            self._skip_newlines()
            return ShowVariable(name=name, line=line)

        # "show list <name>"
        if tok.type == TokenType.KEYWORD and tok.value == "list":
            self._advance()
            name = self._parse_string_or_id()
            self._skip_newlines()
            return Block(name="show list", args=[Literal(name, line)], line=line)

        # Plain "show" (looks_show)
        self._skip_newlines()
        return Block(name="show", args=[], line=line)

    def _parse_hide(self) -> HideVariable | Block:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "hide")

        tok = self._current()
        if tok.type == TokenType.KEYWORD and tok.value == "variable":
            self._advance()
            name = self._parse_string_or_id()
            self._skip_newlines()
            return HideVariable(name=name, line=line)

        if tok.type == TokenType.KEYWORD and tok.value == "list":
            self._advance()
            name = self._parse_string_or_id()
            self._skip_newlines()
            return Block(name="hide list", args=[Literal(name, line)], line=line)

        self._skip_newlines()
        return Block(name="hide", args=[], line=line)

    def _parse_stop(self) -> StopBlock:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "stop")
        # Consume rest of line for mode
        parts = []
        while self._current().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.INDENT, TokenType.DEDENT):
            parts.append(self._advance().value)
        mode = " ".join(parts) if parts else "all"
        self._skip_newlines()
        return StopBlock(mode=mode, line=line)

    def _parse_create_clone(self) -> CloneBlock:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "create")
        self._match(TokenType.KEYWORD, "clone")
        self._match(TokenType.KEYWORD, "of")
        target = self._parse_string_or_id() if self._current().type not in (TokenType.NEWLINE, TokenType.EOF) else "myself"
        self._skip_newlines()
        return CloneBlock(action="create", target=target, line=line)

    def _parse_wait(self) -> Block:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "wait")

        # "wait until <condition>"
        if self._match(TokenType.KEYWORD, "until"):
            cond = self._parse_expression()
            self._skip_newlines()
            return Block(name="wait until", args=[cond], line=line)

        # "wait <n>" or "wait <n> seconds"
        val = self._parse_expression()
        # optional "seconds"
        if self._current().type == TokenType.IDENTIFIER and self._current().value == "seconds":
            self._advance()
        self._skip_newlines()
        return Block(name="wait", args=[val], line=line)

    def _parse_broadcast(self) -> Block:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "broadcast")

        # "broadcast and wait"
        if self._current().type == TokenType.KEYWORD and self._current().value == "and":
            self._advance()
            self._match(TokenType.KEYWORD, "wait")
            msg = self._parse_expression()
            self._skip_newlines()
            return Block(name="broadcast and wait", args=[msg], line=line)

        msg = self._parse_expression()
        self._skip_newlines()
        return Block(name="broadcast", args=[msg], line=line)

    def _parse_list_add(self) -> ListOperation:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "add")
        value = self._parse_expression()
        self._match(TokenType.KEYWORD, "to")
        list_name = self._parse_string_or_id()
        self._skip_newlines()
        return ListOperation("add", list_name, [value], line=line)

    def _parse_list_delete(self) -> ListOperation | Block:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "delete")

        # "delete this clone"
        if self._current().value == "this":
            self._advance()
            self._match(TokenType.KEYWORD, "clone")
            self._skip_newlines()
            return Block(name="delete this clone", args=[], line=line)

        # "delete all of <list>"
        if self._match(TokenType.KEYWORD, "all"):
            self._match(TokenType.KEYWORD, "of")
            list_name = self._parse_string_or_id()
            self._skip_newlines()
            return ListOperation("delete_all", list_name, [], line=line)

        # "delete <index> of <list>"
        index = self._parse_expression()
        self._match(TokenType.KEYWORD, "of")
        list_name = self._parse_string_or_id()
        self._skip_newlines()
        return ListOperation("delete", list_name, [index], line=line)

    def _parse_list_insert(self) -> ListOperation:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "insert")
        value = self._parse_expression()
        self._match(TokenType.KEYWORD, "at")
        index = self._parse_expression()
        self._match(TokenType.KEYWORD, "of")
        list_name = self._parse_string_or_id()
        self._skip_newlines()
        return ListOperation("insert", list_name, [value, index], line=line)

    def _parse_list_replace(self) -> ListOperation:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "replace")
        self._match(TokenType.KEYWORD, "item")
        index = self._parse_expression()
        self._match(TokenType.KEYWORD, "of")
        list_name = self._parse_string_or_id()
        # "with <value>"
        self._match_identifier("with")
        value = self._parse_expression()
        self._skip_newlines()
        return ListOperation("replace", list_name, [index, value], line=line)

    def _parse_named_block(self) -> Statement:
        """Parse a named block like 'move 10', 'say "Hello"', etc."""
        line = self._current().line
        parts: list[str] = []
        args: list[Expression] = []

        # Collect the block name and arguments
        while self._current().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.INDENT, TokenType.DEDENT):
            tok = self._current()

            # If it looks like an argument (number, string, expression in parens, color)
            if tok.type in (TokenType.NUMBER, TokenType.STRING, TokenType.COLOR, TokenType.LPAREN):
                args.append(self._parse_expression())
            elif tok.type == TokenType.OPERATOR and tok.value == "-" and self._peek(1).type == TokenType.NUMBER:
                args.append(self._parse_expression())
            elif tok.type in (TokenType.IDENTIFIER, TokenType.KEYWORD):
                # Could be part of block name or a variable reference as argument
                # Heuristic: if it looks like part of a multi-word block name, add to parts
                # If we already have a recognized block name, treat as argument
                candidate = " ".join(parts + [tok.value])
                from .opcodes import OPCODES

                if candidate in OPCODES or any(k.startswith(candidate) for k in OPCODES):
                    parts.append(self._advance().value)
                elif " ".join(parts) in OPCODES and tok.type == TokenType.IDENTIFIER:
                    # This is an argument
                    args.append(self._parse_expression())
                elif parts and tok.type == TokenType.KEYWORD and tok.value in ("to", "by", "for", "of", "until"):
                    # These prepositions are part of block names
                    parts.append(self._advance().value)
                else:
                    parts.append(self._advance().value)
            else:
                break

        name = " ".join(parts)
        self._skip_newlines()

        # Check if it's a custom block call
        if name in self._custom_blocks:
            return CustomBlockCall(name=name, args=args, line=line)

        return Block(name=name, args=args, line=line)

    # --- Declarations ---

    def _parse_variable_decl(self, is_global: bool = False) -> VariableDecl:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "variable")
        name = self._parse_string_or_id()
        initial: float | int | str = 0
        if self._match(TokenType.OPERATOR, "="):
            initial = self._parse_literal_value()
        self._skip_newlines()
        return VariableDecl(name=name, initial_value=initial, is_global=is_global, line=line)

    def _parse_list_decl(self, is_global: bool = False) -> ListDecl:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "list")
        name = self._parse_string_or_id()
        values: list = []
        if self._match(TokenType.OPERATOR, "="):
            values = self._parse_literal_list()
        self._skip_newlines()
        return ListDecl(name=name, initial_values=values, is_global=is_global, line=line)

    def _parse_custom_block_def(self) -> CustomBlockDef:
        line = self._current().line
        self._expect(TokenType.KEYWORD, "define")
        name = self._parse_string_or_id()
        params: list[str] = []
        param_types: list[str] = []

        # Parse parameter list in parens
        if self._match(TokenType.LPAREN):
            while not self._match(TokenType.RPAREN):
                if self._match(TokenType.COMMA):
                    continue
                pname = self._parse_string_or_id()
                ptype = "string"
                if self._match(TokenType.COLON):
                    ptype = self._parse_string_or_id()
                params.append(pname)
                param_types.append(ptype)

        self._custom_blocks.add(name)
        self._skip_newlines()

        body: list[Statement] = []
        if self._match(TokenType.INDENT):
            body = self._parse_block_list()
            self._match(TokenType.DEDENT)

        return CustomBlockDef(name=name, params=params, param_types=param_types, body=body, line=line)

    # --- Expression parsing (precedence climbing) ---

    def _parse_atomic_arg(self) -> Expression:
        """Parse a single atomic argument for a function/reporter.

        Parses up through arithmetic but stops before comparison and logical ops,
        so that 'touching "edge" and x > 5' correctly parses "edge" as the
        argument to touching rather than consuming the 'and'.
        """
        return self._parse_addition()

    def _parse_expression(self) -> Expression:
        return self._parse_or()

    def _parse_or(self) -> Expression:
        left = self._parse_and()
        while self._match(TokenType.KEYWORD, "or"):
            right = self._parse_and()
            left = BinaryOp("or", left, right, line=left.line)
        return left

    def _parse_and(self) -> Expression:
        left = self._parse_not()
        while self._match(TokenType.KEYWORD, "and"):
            right = self._parse_not()
            left = BinaryOp("and", left, right, line=left.line)
        return left

    def _parse_not(self) -> Expression:
        if self._match(TokenType.KEYWORD, "not"):
            operand = self._parse_not()
            return UnaryOp("not", operand, line=operand.line)
        return self._parse_comparison()

    def _parse_comparison(self) -> Expression:
        left = self._parse_addition()
        if self._current().type == TokenType.OPERATOR and self._current().value in (">", "<", "="):
            op = self._advance().value
            right = self._parse_addition()
            return BinaryOp(op, left, right, line=left.line)
        return left

    def _parse_addition(self) -> Expression:
        left = self._parse_multiplication()
        while self._current().type == TokenType.OPERATOR and self._current().value in ("+", "-"):
            op = self._advance().value
            right = self._parse_multiplication()
            left = BinaryOp(op, left, right, line=left.line)
        return left

    def _parse_multiplication(self) -> Expression:
        left = self._parse_mod()
        while self._current().type == TokenType.OPERATOR and self._current().value in ("*", "/"):
            op = self._advance().value
            right = self._parse_mod()
            left = BinaryOp(op, left, right, line=left.line)
        return left

    def _parse_mod(self) -> Expression:
        left = self._parse_unary()
        while self._match(TokenType.KEYWORD, "mod"):
            right = self._parse_unary()
            left = BinaryOp("mod", left, right, line=left.line)
        return left

    def _parse_unary(self) -> Expression:
        if self._current().type == TokenType.OPERATOR and self._current().value == "-":
            self._advance()
            operand = self._parse_primary()
            return UnaryOp("-", operand, line=operand.line)
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        tok = self._current()

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        # Number
        if tok.type == TokenType.NUMBER:
            self._advance()
            val = float(tok.value) if "." in tok.value else int(tok.value)
            return Literal(val, line=tok.line)

        # String
        if tok.type == TokenType.STRING:
            self._advance()
            return Literal(tok.value, line=tok.line)

        # Color
        if tok.type == TokenType.COLOR:
            self._advance()
            return ColorLiteral(tok.value, line=tok.line)

        # Boolean keywords
        if tok.type == TokenType.KEYWORD and tok.value == "true":
            self._advance()
            return Literal("true", line=tok.line)
        if tok.type == TokenType.KEYWORD and tok.value == "false":
            self._advance()
            return Literal("false", line=tok.line)

        # Built-in reporters/functions
        if tok.type == TokenType.IDENTIFIER or tok.type == TokenType.KEYWORD:
            return self._parse_reporter_or_var()

        raise ParseError(f"Unexpected token in expression: {tok.type.name} ({tok.value!r})", tok.line)

    def _parse_reporter_or_var(self) -> Expression:
        """Parse a reporter block call or variable reference."""
        tok = self._current()
        line = tok.line

        from .opcodes import OPCODES

        # Try to match multi-word reporter names
        parts = [self._advance().value]

        while self._current().type in (TokenType.IDENTIFIER, TokenType.KEYWORD):
            candidate = " ".join(parts + [self._current().value])
            if candidate in OPCODES:
                parts.append(self._advance().value)
                break
            elif any(k.startswith(candidate) for k in OPCODES):
                parts.append(self._advance().value)
            else:
                break

        name = " ".join(parts)

        # Check if this is a known reporter with arguments
        if name in OPCODES:
            entry = OPCODES[name]
            if entry.is_reporter or entry.is_boolean:
                args = []
                for _inp in entry.inputs:
                    if self._current().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.DEDENT,
                                                     TokenType.RPAREN, TokenType.COMMA):
                        # Parse only an atomic expression — don't consume logical/comparison ops
                        args.append(self._parse_atomic_arg())
                return FunctionCall(name, args, line=line)

        # Known function-like reporters
        func_reporters = {
            "pick random": 2, "join": 2, "letter of": 2,
            "length of": 1, "contains": 2, "round": 1,
            "item of": 1, "item # of in": 1, "length of list": 0,
            "list contains": 1, "distance to": 1,
        }
        if name in func_reporters:
            arg_count = func_reporters[name]
            args = []
            for _ in range(arg_count):
                if self._current().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.DEDENT,
                                                 TokenType.RPAREN):
                    args.append(self._parse_atomic_arg())
            return FunctionCall(name, args, line=line)

        # Single-word — could be a variable reference
        if len(parts) == 1:
            return VarRef(parts[0], line=line)

        # Multi-word — try as function call
        return FunctionCall(name, [], line=line)

    # --- Helper methods ---

    def _parse_string_list(self) -> list[str]:
        """Parse a list of strings/identifiers on the same line."""
        items: list[str] = []
        while self._current().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.INDENT, TokenType.DEDENT):
            if self._current().type == TokenType.COMMA:
                self._advance()
                continue
            items.append(self._parse_string_or_id())
        return items

    def _parse_number(self) -> float:
        tok = self._current()
        negative = False
        if tok.type == TokenType.OPERATOR and tok.value == "-":
            negative = True
            self._advance()
            tok = self._current()
        if tok.type != TokenType.NUMBER:
            raise ParseError(f"Expected number but got {tok.value!r}", tok.line)
        self._advance()
        val = float(tok.value) if "." in tok.value else int(tok.value)
        return -val if negative else val

    def _parse_number_str(self) -> str:
        tok = self._current()
        if tok.type == TokenType.NUMBER:
            self._advance()
            return tok.value
        raise ParseError(f"Expected number but got {tok.value!r}", tok.line)

    def _parse_literal_value(self):
        tok = self._current()
        if tok.type == TokenType.NUMBER:
            self._advance()
            return float(tok.value) if "." in tok.value else int(tok.value)
        if tok.type == TokenType.STRING:
            self._advance()
            return tok.value
        if tok.type == TokenType.OPERATOR and tok.value == "-":
            self._advance()
            return -self._parse_number()
        raise ParseError(f"Expected literal value but got {tok.value!r}", tok.line)

    def _parse_literal_list(self) -> list:
        """Parse [1, 2, 3] or a, b, c."""
        values = []
        # Consume opening bracket if present
        has_bracket = self._current().type == TokenType.IDENTIFIER and self._current().value == "["
        if has_bracket:
            self._advance()

        while self._current().type not in (TokenType.NEWLINE, TokenType.EOF):
            if self._match(TokenType.COMMA):
                continue
            if has_bracket and self._current().value == "]":
                self._advance()
                break
            values.append(self._parse_literal_value())

        return values

    def _error(self, message: str):
        """Record a parse error and continue."""
        line = self._current().line
        self.errors.append(f"Line {line}: {message}")


def parse(source: str) -> Project:
    """Parse ScratchScript source code into a Project AST."""
    tokens = tokenize(source)
    parser = Parser(tokens)
    project = parser.parse()
    if parser.errors:
        raise ParseError("\n".join(parser.errors))
    return project
