"""Decompiler: Scratch 3.0 project.json → ScratchScript text."""

from __future__ import annotations

from typing import Any, Optional

from .opcodes import BINARY_OPS, MENU_FIELDS, MENU_OPCODES, OPCODES, UNARY_OPS

# ---------------------------------------------------------------------------
# Reverse lookup tables (built once at import time)
# ---------------------------------------------------------------------------

# opcode → list of (dsl_name, OpcodeEntry) — list because some opcodes map to
# multiple DSL names (e.g. looks_costumenumbername → "costume number" / "costume name")
_REVERSE_OPCODES: dict[str, list[tuple[str, Any]]] = {}
for _name, _entry in OPCODES.items():
    _REVERSE_OPCODES.setdefault(_entry.opcode, []).append((_name, _entry))

_REVERSE_BINARY_OPS: dict[str, str] = {v: k for k, v in BINARY_OPS.items()}
_REVERSE_UNARY_OPS: dict[str, str] = {v: k for k, v in UNARY_OPS.items()}

# Set of opcodes that are menu shadow blocks — we skip these during chain walks
_MENU_BLOCK_OPCODES: set[str] = set(MENU_OPCODES.values())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def decompile(project_json: dict) -> str:
    """Decompile a Scratch 3.0 project.json dict to ScratchScript text."""
    dc = _Decompiler(project_json)
    return dc.run()


# ---------------------------------------------------------------------------
# Decompiler implementation
# ---------------------------------------------------------------------------


class _Decompiler:
    def __init__(self, project_json: dict):
        self.project = project_json
        self.lines: list[str] = []
        self.indent = 0

        # Maps built per-target
        self.blocks: dict[str, dict] = {}
        self.var_ids: dict[str, str] = {}  # uuid → name
        self.list_ids: dict[str, str] = {}  # uuid → name
        self.broadcast_ids: dict[str, str] = {}  # uuid → name

        # Stage variable/list names (for detecting globals in sprites)
        self.stage_var_names: set[str] = set()
        self.stage_list_names: set[str] = set()

        # Custom block proccode → name mapping (per target)
        self.custom_procs: dict[str, _ProcInfo] = {}

    # -- Output helpers --

    def _emit(self, text: str = ""):
        self.lines.append("  " * self.indent + text)

    def _blank(self):
        if self.lines and self.lines[-1].strip() != "":
            self.lines.append("")

    # -- Main entry point --

    def run(self) -> str:
        targets = self.project.get("targets", [])
        if not targets:
            return ""

        # Separate stage and sprites
        stage = None
        sprites: list[dict] = []
        for t in targets:
            if t.get("isStage", False):
                stage = t
            else:
                sprites.append(t)

        # Project name
        project_name = "Imported Project"
        self._emit(f'project "{project_name}"')
        self._blank()

        # Stage globals
        if stage:
            self._build_id_maps(stage)
            self.stage_var_names = set(self.var_ids.values())
            self.stage_list_names = set(self.list_ids.values())

            # Emit global variables
            for uid, (name, value) in stage.get("variables", {}).items():
                self._emit(f"variable {_quote_if_needed(name)} = {_format_value(value)}")
            for uid, (name, values) in stage.get("lists", {}).items():
                vals = ", ".join(_format_value(v) for v in values)
                self._emit(f"list {_quote_if_needed(name)} = {vals}")

            has_globals = stage.get("variables") or stage.get("lists")
            if has_globals:
                self._blank()

            # Stage block
            self._emit_stage(stage)

        # Sprites
        for sprite in sprites:
            self._blank()
            self._emit_sprite(sprite)

        # Strip trailing blank lines
        while self.lines and self.lines[-1].strip() == "":
            self.lines.pop()

        return "\n".join(self.lines) + "\n"

    # -- ID map building --

    def _build_id_maps(self, target: dict):
        self.var_ids = {}
        self.list_ids = {}
        self.broadcast_ids = {}
        self.blocks = target.get("blocks", {})
        self.custom_procs = {}

        for uid, val in target.get("variables", {}).items():
            self.var_ids[uid] = val[0]
        for uid, val in target.get("lists", {}).items():
            self.list_ids[uid] = val[0]
        for uid, val in target.get("broadcasts", {}).items():
            self.broadcast_ids[uid] = val

        # Scan for custom block definitions
        self._scan_custom_blocks()

    def _scan_custom_blocks(self):
        """Find procedures_definition blocks and extract proccode/arg info."""
        for bid, block in self.blocks.items():
            if block.get("opcode") != "procedures_definition":
                continue
            custom_block_input = block.get("inputs", {}).get("custom_block")
            if not custom_block_input:
                continue
            proto_id = _extract_block_ref(custom_block_input)
            if not proto_id or proto_id not in self.blocks:
                continue
            proto = self.blocks[proto_id]
            mutation = proto.get("mutation", {})
            proccode = mutation.get("proccode", "")
            arg_names = _parse_json_list(mutation.get("argumentnames", "[]"))
            arg_ids = _parse_json_list(mutation.get("argumentids", "[]"))
            arg_defaults = _parse_json_list(mutation.get("argumentdefaults", "[]"))

            # Derive a clean name from proccode (strip %s/%b placeholders)
            name = proccode
            for placeholder in ("%s", "%b"):
                name = name.replace(placeholder, "")
            name = " ".join(name.split()).strip()

            # Determine param types from proccode placeholders
            param_types: list[str] = []
            for part in proccode.split():
                if part == "%s":
                    param_types.append("string")
                elif part == "%b":
                    param_types.append("boolean")

            self.custom_procs[proccode] = _ProcInfo(
                name=name,
                proccode=proccode,
                arg_names=arg_names,
                arg_ids=arg_ids,
                param_types=param_types,
                def_block_id=bid,
            )

    # -- Stage emission --

    def _emit_stage(self, stage: dict):
        self._build_id_maps(stage)

        # Merge stage broadcasts into the broadcast map used globally
        for uid, val in stage.get("broadcasts", {}).items():
            self.broadcast_ids[uid] = val

        costumes = stage.get("costumes", [])
        has_scripts = self._has_scripts(stage)
        has_custom = bool(self.custom_procs)

        # Only emit stage block if there's content
        if not costumes and not has_scripts and not has_custom:
            return

        self._emit("stage")
        self.indent += 1

        # Backdrops
        if costumes:
            names = ", ".join(f'"{c["name"]}"' for c in costumes
                              if c.get("name") != "backdrop1" or len(costumes) > 1)
            if names:
                self._emit(f"backdrops {names}")

        # Scripts
        self._emit_scripts(stage)

        # Custom blocks
        self._emit_custom_block_defs()

        self.indent -= 1

    # -- Sprite emission --

    def _emit_sprite(self, sprite: dict):
        self._build_id_maps(sprite)

        # Also include stage vars/lists in lookup for this sprite
        # (stage target's vars were already captured)

        name = sprite.get("name", "Sprite1")
        self._emit(f"sprite {_quote_if_needed(name)}")
        self.indent += 1

        # Costumes
        costumes = sprite.get("costumes", [])
        if costumes:
            names = ", ".join(f'"{c["name"]}"' for c in costumes)
            self._emit(f"costumes {names}")

        # Sounds
        sounds = sprite.get("sounds", [])
        if sounds:
            names = ", ".join(f'"{s["name"]}"' for s in sounds)
            self._emit(f"sounds {names}")

        # Position / size / direction
        x = sprite.get("x", 0)
        y = sprite.get("y", 0)
        if x != 0 or y != 0:
            self._emit(f"position {_format_num(x)}, {_format_num(y)}")

        size = sprite.get("size", 100)
        if size != 100:
            self._emit(f"size {_format_num(size)}")

        direction = sprite.get("direction", 90)
        if direction != 90:
            self._emit(f"direction {_format_num(direction)}")

        visible = sprite.get("visible", True)
        if not visible:
            self._emit("visible false")

        rotation = sprite.get("rotationStyle", "all around")
        if rotation != "all around":
            self._emit(f"rotation {rotation}")

        # Sprite-local variables
        for uid, (vname, vval) in sprite.get("variables", {}).items():
            if vname in self.stage_var_names:
                self._emit(f"global variable {_quote_if_needed(vname)} = {_format_value(vval)}")
            else:
                self._emit(f"variable {_quote_if_needed(vname)} = {_format_value(vval)}")

        # Sprite-local lists
        for uid, (lname, lvals) in sprite.get("lists", {}).items():
            vals = ", ".join(_format_value(v) for v in lvals)
            if lname in self.stage_list_names:
                self._emit(f"global list {_quote_if_needed(lname)} = {vals}")
            else:
                self._emit(f"list {_quote_if_needed(lname)} = {vals}")

        # Scripts
        self._emit_scripts(sprite)

        # Custom blocks
        self._emit_custom_block_defs()

        self.indent -= 1

    # -- Script finding and emission --

    def _has_scripts(self, target: dict) -> bool:
        blocks = target.get("blocks", {})
        for bid, block in blocks.items():
            if not isinstance(block, dict):
                continue
            if block.get("topLevel") and not block.get("shadow"):
                opcode = block.get("opcode", "")
                if opcode != "procedures_definition":
                    return True
        return False

    def _emit_scripts(self, target: dict):
        """Find and emit all scripts (hat block chains) in a target."""
        blocks = self.blocks

        # Find all top-level hat blocks (excluding procedure definitions)
        hat_ids: list[str] = []
        for bid, block in blocks.items():
            if not isinstance(block, dict):
                continue
            if not block.get("topLevel"):
                continue
            if block.get("shadow"):
                continue
            opcode = block.get("opcode", "")
            if opcode == "procedures_definition":
                continue  # handled separately
            hat_ids.append(bid)

        for hat_id in hat_ids:
            self._blank()
            self._emit_script(hat_id)

    def _emit_script(self, hat_id: str):
        """Emit a single script starting from a hat block."""
        block = self.blocks.get(hat_id)
        if not block:
            return

        self._emit("script")
        self.indent += 1

        # Event trigger
        event_line = self._decode_hat(block)
        self._emit(event_line)

        # Walk the chain from hat.next
        next_id = block.get("next")
        self._walk_chain(next_id)

        self.indent -= 1

    def _emit_custom_block_defs(self):
        """Emit all custom block definitions for the current target."""
        for proccode, info in self.custom_procs.items():
            self._blank()
            self._emit_custom_block_def(info)

    def _emit_custom_block_def(self, info: _ProcInfo):
        """Emit a define block."""
        params = []
        for i, pname in enumerate(info.arg_names):
            ptype = info.param_types[i] if i < len(info.param_types) else "string"
            if ptype == "boolean":
                params.append(f"{pname}: boolean")
            else:
                params.append(pname)

        param_str = f"({', '.join(params)})" if params else ""
        self._emit(f"define {_quote_if_needed(info.name)}{param_str}")
        self.indent += 1

        # Walk body from definition block's next
        def_block = self.blocks.get(info.def_block_id, {})
        next_id = def_block.get("next")
        self._walk_chain(next_id)

        self.indent -= 1

    # -- Hat block decoding --

    def _decode_hat(self, block: dict) -> str:
        opcode = block.get("opcode", "")
        fields = block.get("fields", {})
        inputs = block.get("inputs", {})

        if opcode == "event_whenflagclicked":
            return "when flag clicked"
        if opcode == "event_whenkeypressed":
            key = _field_value(fields, "KEY_OPTION", "space")
            return f'when key "{key}" pressed'
        if opcode == "event_whenthisspriteclicked":
            return "when this sprite clicked"
        if opcode == "event_whenstageclicked":
            return "when stage clicked"
        if opcode == "event_whenbroadcastreceived":
            msg = _field_value(fields, "BROADCAST_OPTION", "message1")
            return f'when I receive "{msg}"'
        if opcode == "event_whenbackdropswitchesto":
            name = _field_value(fields, "BACKDROP", "backdrop1")
            return f'when backdrop switches to "{name}"'
        if opcode == "event_whengreaterthan":
            sensor = _field_value(fields, "WHENGREATERTHANMENU", "LOUDNESS")
            value = self._decode_input(inputs.get("VALUE"), fallback="10")
            return f"when {sensor.lower()} > {value}"
        if opcode == "control_start_as_clone":
            return "when I start as a clone"

        return "when flag clicked"

    # -- Block chain walking --

    def _walk_chain(self, block_id: Optional[str]):
        """Walk a linear chain of blocks via 'next' pointers, emitting statements."""
        while block_id and block_id in self.blocks:
            block = self.blocks[block_id]
            if not isinstance(block, dict):
                break
            self._emit_statement(block)
            block_id = block.get("next")

    def _emit_statement(self, block: dict):
        """Emit a single statement block."""
        opcode = block.get("opcode", "")
        inputs = block.get("inputs", {})
        fields = block.get("fields", {})

        # -- Control flow --
        if opcode == "control_if":
            self._emit_if(block, has_else=False)
            return
        if opcode == "control_if_else":
            self._emit_if(block, has_else=True)
            return
        if opcode == "control_forever":
            self._emit_forever(block)
            return
        if opcode == "control_repeat":
            self._emit_repeat(block)
            return
        if opcode == "control_repeat_until":
            self._emit_repeat_until(block)
            return

        # -- Data: variables --
        if opcode == "data_setvariableto":
            var = _field_value(fields, "VARIABLE", "var")
            val = self._decode_input(inputs.get("VALUE"), fallback="0")
            self._emit(f"set {_quote_if_needed(var)} to {val}")
            return
        if opcode == "data_changevariableby":
            var = _field_value(fields, "VARIABLE", "var")
            val = self._decode_input(inputs.get("VALUE"), fallback="1")
            self._emit(f"change {_quote_if_needed(var)} by {val}")
            return
        if opcode == "data_showvariable":
            var = _field_value(fields, "VARIABLE", "var")
            self._emit(f"show variable {_quote_if_needed(var)}")
            return
        if opcode == "data_hidevariable":
            var = _field_value(fields, "VARIABLE", "var")
            self._emit(f"hide variable {_quote_if_needed(var)}")
            return

        # -- Data: lists --
        if opcode == "data_addtolist":
            lst = _field_value(fields, "LIST", "list")
            item = self._decode_input(inputs.get("ITEM"), fallback='""')
            self._emit(f"add {item} to {_quote_if_needed(lst)}")
            return
        if opcode == "data_deleteoflist":
            lst = _field_value(fields, "LIST", "list")
            idx = self._decode_input(inputs.get("INDEX"), fallback="1")
            self._emit(f"delete {idx} of {_quote_if_needed(lst)}")
            return
        if opcode == "data_deletealloflist":
            lst = _field_value(fields, "LIST", "list")
            self._emit(f"delete all of {_quote_if_needed(lst)}")
            return
        if opcode == "data_insertatlist":
            lst = _field_value(fields, "LIST", "list")
            item = self._decode_input(inputs.get("ITEM"), fallback='""')
            idx = self._decode_input(inputs.get("INDEX"), fallback="1")
            self._emit(f"insert {item} at {idx} of {_quote_if_needed(lst)}")
            return
        if opcode == "data_replaceitemoflist":
            lst = _field_value(fields, "LIST", "list")
            idx = self._decode_input(inputs.get("INDEX"), fallback="1")
            item = self._decode_input(inputs.get("ITEM"), fallback='""')
            self._emit(f"replace item {idx} of {_quote_if_needed(lst)} with {item}")
            return
        if opcode == "data_showlist":
            lst = _field_value(fields, "LIST", "list")
            self._emit(f"show list {_quote_if_needed(lst)}")
            return
        if opcode == "data_hidelist":
            lst = _field_value(fields, "LIST", "list")
            self._emit(f"hide list {_quote_if_needed(lst)}")
            return

        # -- Clone / Stop --
        if opcode == "control_create_clone_of":
            target = self._decode_menu_or_input(inputs.get("CLONE_OPTION"), "myself")
            if target == "_myself_":
                target = "myself"
            self._emit(f"create clone of {_quote_if_needed(target)}")
            return
        if opcode == "control_delete_this_clone":
            self._emit("delete this clone")
            return
        if opcode == "control_stop":
            mode = _field_value(fields, "STOP_OPTION", "all")
            self._emit(f"stop {mode}")
            return

        # -- Wait --
        if opcode == "control_wait":
            dur = self._decode_input(inputs.get("DURATION"), fallback="1")
            self._emit(f"wait {dur}")
            return
        if opcode == "control_wait_until":
            cond = self._decode_bool_input(inputs.get("CONDITION"))
            self._emit(f"wait until {cond}")
            return

        # -- Broadcast --
        if opcode == "event_broadcast":
            msg = self._decode_input(inputs.get("BROADCAST_INPUT"), fallback='"message1"')
            self._emit(f"broadcast {msg}")
            return
        if opcode == "event_broadcastandwait":
            msg = self._decode_input(inputs.get("BROADCAST_INPUT"), fallback='"message1"')
            self._emit(f"broadcast and wait {msg}")
            return

        # -- Custom block call --
        if opcode == "procedures_call":
            self._emit_custom_call(block)
            return

        # -- Generic block (motion, looks, sound, sensing, pen, etc.) --
        self._emit_generic_block(opcode, inputs, fields)

    # -- Control flow emission --

    def _emit_if(self, block: dict, has_else: bool):
        inputs = block.get("inputs", {})
        cond = self._decode_bool_input(inputs.get("CONDITION"))
        self._emit(f"if {cond}")
        self.indent += 1
        substack_id = _extract_block_ref(inputs.get("SUBSTACK"))
        self._walk_chain(substack_id)
        self.indent -= 1

        if has_else:
            self._emit("else")
            self.indent += 1
            substack2_id = _extract_block_ref(inputs.get("SUBSTACK2"))
            self._walk_chain(substack2_id)
            self.indent -= 1

    def _emit_forever(self, block: dict):
        inputs = block.get("inputs", {})
        self._emit("forever")
        self.indent += 1
        substack_id = _extract_block_ref(inputs.get("SUBSTACK"))
        self._walk_chain(substack_id)
        self.indent -= 1

    def _emit_repeat(self, block: dict):
        inputs = block.get("inputs", {})
        times = self._decode_input(inputs.get("TIMES"), fallback="10")
        self._emit(f"repeat {times}")
        self.indent += 1
        substack_id = _extract_block_ref(inputs.get("SUBSTACK"))
        self._walk_chain(substack_id)
        self.indent -= 1

    def _emit_repeat_until(self, block: dict):
        inputs = block.get("inputs", {})
        cond = self._decode_bool_input(inputs.get("CONDITION"))
        self._emit(f"repeat until {cond}")
        self.indent += 1
        substack_id = _extract_block_ref(inputs.get("SUBSTACK"))
        self._walk_chain(substack_id)
        self.indent -= 1

    # -- Custom call emission --

    def _emit_custom_call(self, block: dict):
        mutation = block.get("mutation", {})
        proccode = mutation.get("proccode", "")
        arg_ids = _parse_json_list(mutation.get("argumentids", "[]"))
        inputs = block.get("inputs", {})

        info = self.custom_procs.get(proccode)
        name = info.name if info else proccode.replace("%s", "").replace("%b", "").strip()

        args: list[str] = []
        for aid in arg_ids:
            val = self._decode_input(inputs.get(aid), fallback='""')
            args.append(val)

        arg_str = " " + ", ".join(args) if args else ""
        self._emit(f"{_quote_if_needed(name)}{arg_str}")

    # -- Generic block emission --

    def _emit_generic_block(self, opcode: str, inputs: dict, fields: dict):
        """Emit a generic named block using reverse opcode lookup."""
        candidates = _REVERSE_OPCODES.get(opcode, [])
        if not candidates:
            # Unknown opcode — emit as comment
            self._emit(f"// unknown: {opcode}")
            return

        # Disambiguate by field values
        dsl_name, entry = self._pick_candidate(candidates, fields)

        # Build argument list matching the entry's input/field order
        args: list[str] = []
        for inp_spec in entry.inputs:
            if inp_spec.type == "substack":
                continue
            if inp_spec.type == "bool":
                args.append(self._decode_bool_input(inputs.get(inp_spec.name)))
            elif inp_spec.type == "menu":
                args.append(self._decode_menu_or_input(inputs.get(inp_spec.name), ""))
            elif inp_spec.type == "color":
                args.append(self._decode_color_input(inputs.get(inp_spec.name)))
            else:
                args.append(self._decode_input(inputs.get(inp_spec.name), fallback="0"))

        # Fields that aren't used for disambiguation are emitted as args
        for field_spec in entry.fields:
            val = _field_value(fields, field_spec.name, "")
            if val and not self._is_disambiguator(field_spec.name, candidates):
                args.append(f'"{val}"')

        arg_str = " " + ", ".join(args) if args else ""
        self._emit(f"{dsl_name}{arg_str}")

    def _pick_candidate(
        self, candidates: list[tuple[str, Any]], fields: dict
    ) -> tuple[str, Any]:
        """Pick the right DSL name when an opcode maps to multiple entries."""
        if len(candidates) == 1:
            return candidates[0]

        # Disambiguate by field values.
        # e.g. looks_costumenumbername: NUMBER_NAME=number → "costume number",
        #      NUMBER_NAME=name → "costume name"
        for dsl_name, entry in candidates:
            match = True
            for fspec in entry.fields:
                actual = _field_value(fields, fspec.name, None)
                if actual is None:
                    continue
                # Check if the DSL name itself encodes the field value
                if fspec.values and actual in fspec.values:
                    # "costume number" should match when NUMBER_NAME=number
                    if actual.lower() in dsl_name.lower():
                        return dsl_name, entry
            # If no specific field match, continue checking
        # Fallback to first candidate
        return candidates[0]

    def _is_disambiguator(self, field_name: str, candidates: list) -> bool:
        """Check if a field is used to disambiguate between multiple DSL names."""
        if len(candidates) <= 1:
            return False
        # Fields like NUMBER_NAME that distinguish "costume number" vs "costume name"
        return field_name in ("NUMBER_NAME",)

    # -- Input decoding --

    def _decode_input(self, inp: Any, fallback: str = "0") -> str:
        """Decode a Scratch input to a ScratchScript expression string.

        Input formats:
          [1, [4, "10"]]          → number literal
          [1, [10, "hello"]]      → string literal
          [1, [9, "#ff0000"]]     → color literal
          [3, [12, name, id], ..] → variable reference
          [3, [13, name, id], ..] → list reference
          [3, block_id, ..]       → reporter block (recurse)
          [2, block_id]           → boolean block (recurse)
          [1, shadow_id]          → menu shadow block
        """
        if inp is None:
            return fallback

        if not isinstance(inp, list) or len(inp) < 2:
            return fallback

        outer_type = inp[0]  # 1=shadow, 2=bool, 3=var/reporter
        value = inp[1]

        # Literal values: [1, [type_code, "value"]]
        if isinstance(value, list) and len(value) >= 2:
            type_code = value[0]
            literal_val = value[1]

            if type_code == 12:
                # Variable reference: [12, name, id]
                return _quote_if_needed(str(literal_val))
            if type_code == 13:
                # List reference: [13, name, id]
                return _quote_if_needed(str(literal_val))
            if type_code == 9:
                # Color literal
                return str(literal_val)
            if type_code == 4:
                # Number literal
                return _format_literal(literal_val)
            if type_code == 10:
                # String literal
                return _format_string_literal(literal_val)
            # Other type codes — treat as literal
            return _format_literal(literal_val)

        # Block reference: value is a block ID string
        if isinstance(value, str) and value in self.blocks:
            block = self.blocks[value]
            if isinstance(block, dict):
                # Check if it's a menu shadow block
                if block.get("shadow"):
                    return self._decode_menu_block(value)
                # Otherwise it's a reporter — recurse
                return self._decode_reporter(value)

        # outer_type 3 with a nested array may have the reporter in position 1
        # and a fallback literal in position 2
        if outer_type == 3 and isinstance(value, str) and value in self.blocks:
            return self._decode_reporter(value)

        return fallback

    def _decode_bool_input(self, inp: Any) -> str:
        """Decode a boolean input [2, block_id]."""
        if inp is None:
            return "false"
        if not isinstance(inp, list) or len(inp) < 2:
            return "false"
        value = inp[1]
        if isinstance(value, str) and value in self.blocks:
            return self._decode_reporter(value)
        return "false"

    def _decode_color_input(self, inp: Any) -> str:
        """Decode a color input."""
        if inp is None:
            return "#000000"
        if isinstance(inp, list) and len(inp) >= 2:
            value = inp[1]
            if isinstance(value, list) and len(value) >= 2 and value[0] == 9:
                return str(value[1])
        return "#000000"

    def _decode_menu_or_input(self, inp: Any, fallback: str) -> str:
        """Decode a menu input — could be a shadow menu block or a literal."""
        if inp is None:
            return fallback
        if not isinstance(inp, list) or len(inp) < 2:
            return fallback

        value = inp[1]

        # [1, shadow_block_id] — menu shadow
        if isinstance(value, str) and value in self.blocks:
            block = self.blocks[value]
            if isinstance(block, dict) and block.get("shadow"):
                return self._decode_menu_block(value)
            # Non-shadow block — it's a reporter overriding the menu
            return self._decode_reporter(value)

        # Literal array
        if isinstance(value, list) and len(value) >= 2:
            type_code = value[0]
            if type_code in (12, 13):
                return _quote_if_needed(str(value[1]))
            return _format_literal(value[1])

        return fallback

    def _decode_menu_block(self, block_id: str) -> str:
        """Extract the field value from a menu shadow block."""
        block = self.blocks.get(block_id)
        if not block or not isinstance(block, dict):
            return '""'
        fields = block.get("fields", {})
        # Menu blocks have a single field — get its value
        for fname, fval in fields.items():
            if isinstance(fval, list) and fval:
                return f'"{fval[0]}"'
        return '""'

    # -- Reporter decoding (expressions) --

    def _decode_reporter(self, block_id: str) -> str:
        """Decode a reporter/boolean block into an expression string."""
        block = self.blocks.get(block_id)
        if not block or not isinstance(block, dict):
            return "0"

        opcode = block.get("opcode", "")
        inputs = block.get("inputs", {})
        fields = block.get("fields", {})

        # Binary operators
        if opcode in _REVERSE_BINARY_OPS:
            op = _REVERSE_BINARY_OPS[opcode]
            if op in ("and", "or"):
                left = self._decode_bool_input(inputs.get("OPERAND1"))
                right = self._decode_bool_input(inputs.get("OPERAND2"))
            elif op in (">", "<", "="):
                left = self._decode_input(inputs.get("OPERAND1"), fallback="0")
                right = self._decode_input(inputs.get("OPERAND2"), fallback="0")
            else:
                left = self._decode_input(inputs.get("NUM1"), fallback="0")
                right = self._decode_input(inputs.get("NUM2"), fallback="0")
            return f"({left} {op} {right})"

        # Unary operators
        if opcode in _REVERSE_UNARY_OPS:
            op = _REVERSE_UNARY_OPS[opcode]
            if op == "not":
                operand = self._decode_bool_input(inputs.get("OPERAND"))
                return f"(not {operand})"

        # Argument reporters (custom block parameters)
        if opcode in ("argument_reporter_string_number", "argument_reporter_boolean"):
            val = _field_value(fields, "VALUE", "param")
            return val

        # Named reporters — use reverse lookup
        candidates = _REVERSE_OPCODES.get(opcode, [])
        if candidates:
            dsl_name, entry = self._pick_candidate(candidates, fields)
            if entry.is_reporter or entry.is_boolean:
                args: list[str] = []
                for inp_spec in entry.inputs:
                    if inp_spec.type == "bool":
                        args.append(self._decode_bool_input(inputs.get(inp_spec.name)))
                    elif inp_spec.type == "menu":
                        args.append(self._decode_menu_or_input(inputs.get(inp_spec.name), '""'))
                    elif inp_spec.type == "color":
                        args.append(self._decode_color_input(inputs.get(inp_spec.name)))
                    else:
                        args.append(self._decode_input(inputs.get(inp_spec.name), fallback="0"))

                # Fields that aren't disambiguation
                for fspec in entry.fields:
                    val = _field_value(fields, fspec.name, "")
                    if val and not self._is_disambiguator(fspec.name, candidates):
                        args.append(f'"{val}"')

                if args:
                    return f"{dsl_name}({', '.join(args)})"
                return dsl_name

        return "0"


# ---------------------------------------------------------------------------
# Helper dataclass for custom blocks
# ---------------------------------------------------------------------------


class _ProcInfo:
    __slots__ = ("name", "proccode", "arg_names", "arg_ids", "param_types", "def_block_id")

    def __init__(self, name: str, proccode: str, arg_names: list[str],
                 arg_ids: list[str], param_types: list[str], def_block_id: str):
        self.name = name
        self.proccode = proccode
        self.arg_names = arg_names
        self.arg_ids = arg_ids
        self.param_types = param_types
        self.def_block_id = def_block_id


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _field_value(fields: dict, name: str, default: Any = "") -> Any:
    """Extract the value from a Scratch field entry."""
    val = fields.get(name)
    if isinstance(val, list) and val:
        return val[0]
    return default


def _extract_block_ref(inp: Any) -> Optional[str]:
    """Extract a block ID from a substack input like [2, block_id]."""
    if isinstance(inp, list) and len(inp) >= 2:
        val = inp[1]
        if isinstance(val, str):
            return val
    return None


def _parse_json_list(s: str) -> list[str]:
    """Parse a JSON-encoded list string from mutation data."""
    import json
    try:
        result = json.loads(s)
        if isinstance(result, list):
            return [str(x) for x in result]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _format_value(val: Any) -> str:
    """Format a variable/list initial value for ScratchScript."""
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return str(val)
    return str(val)


def _format_literal(val: Any) -> str:
    """Format a literal value from a Scratch input."""
    s = str(val)
    # If it looks numeric, emit as number
    try:
        f = float(s)
        if f == int(f) and "." not in s:
            return str(int(f))
        return s
    except (ValueError, TypeError):
        pass
    return f'"{s}"'


def _format_string_literal(val: Any) -> str:
    """Format a string literal — always quote it."""
    return f'"{val}"'


def _format_num(val: float | int) -> str:
    """Format a number, dropping .0 for integers."""
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    return str(val)


def _quote_if_needed(name: str) -> str:
    """Quote a name if it contains spaces or special characters."""
    if not name:
        return '""'
    if " " in name or '"' in name or not name.replace("_", "").replace("-", "").isalnum():
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return name


def _needs_quotes(s: str) -> bool:
    """Check if a string needs quoting."""
    return " " in s or not s.replace("_", "").replace("-", "").isalnum()
