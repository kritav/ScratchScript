"""Code generator: AST → Scratch 3.0 project.json structure."""

from __future__ import annotations

import uuid
from typing import Any, Optional

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
from .opcodes import BINARY_OPS, MENU_FIELDS, OPCODES, UNARY_OPS


def _uid() -> str:
    return uuid.uuid4().hex[:20]


class CodeGenerator:
    def __init__(self):
        self.blocks: dict[str, dict] = {}
        self.variables: dict[str, tuple[str, Any]] = {}  # id → (name, value)
        self.lists: dict[str, tuple[str, list]] = {}     # id → (name, values)
        self.broadcasts: dict[str, str] = {}              # id → name
        self.extensions: set[str] = set()
        self.monitors: list[dict] = []
        self._var_name_to_id: dict[str, str] = {}
        self._list_name_to_id: dict[str, str] = {}
        self._broadcast_name_to_id: dict[str, str] = {}
        self._custom_block_procodes: dict[str, str] = {}  # name → proccode
        self._custom_block_arg_ids: dict[str, list[str]] = {}
        self._custom_block_arg_names: dict[str, list[str]] = {}

    def generate(self, project: Project) -> dict:
        """Generate complete project.json dict from AST."""
        targets = []

        # Stage target
        stage = self._generate_stage(project)
        targets.append(stage)

        # Sprite targets
        for i, sprite in enumerate(project.sprites):
            target = self._generate_sprite(sprite, layer_order=i + 1)
            targets.append(target)

        # Collect extensions
        ext_list = sorted(self.extensions)

        return {
            "targets": targets,
            "monitors": self.monitors,
            "extensions": ext_list,
            "meta": {
                "semver": "3.0.0",
                "vm": "2.3.4",
                "agent": "ScratchScript",
            },
        }

    def _generate_stage(self, project: Project) -> dict:
        """Generate the Stage target."""
        self.blocks = {}
        self.variables = {}
        self.lists = {}
        self._var_name_to_id = {}
        self._list_name_to_id = {}

        # Register global variables
        for v in project.variables:
            vid = _uid()
            self.variables[vid] = (v.name, v.initial_value)
            self._var_name_to_id[v.name] = vid

        # Register global lists
        for lst in project.lists:
            lid = _uid()
            self.lists[lid] = (lst.name, lst.initial_values)
            self._list_name_to_id[lst.name] = lid

        # Scan all sprites for global vars/lists too
        for sprite in project.sprites:
            for v in sprite.variables:
                if v.is_global and v.name not in self._var_name_to_id:
                    vid = _uid()
                    self.variables[vid] = (v.name, v.initial_value)
                    self._var_name_to_id[v.name] = vid
            for lst in sprite.lists:
                if lst.is_global and lst.name not in self._list_name_to_id:
                    lid = _uid()
                    self.lists[lid] = (lst.name, lst.initial_values)
                    self._list_name_to_id[lst.name] = lid

        # Scan all scripts for broadcasts
        self._scan_broadcasts(project)

        # Generate stage scripts
        for script in project.stage_scripts:
            self._generate_script(script)

        for cb in project.stage_custom_blocks:
            self._generate_custom_block_def(cb)

        # Build costumes
        costumes = self._build_stage_costumes(project.backdrops)

        return {
            "isStage": True,
            "name": "Stage",
            "variables": {k: list(v) for k, v in self.variables.items()},
            "lists": {k: [v[0], v[1]] for k, v in self.lists.items()},
            "broadcasts": dict(self.broadcasts),
            "blocks": dict(self.blocks),
            "comments": {},
            "currentCostume": 0,
            "costumes": costumes,
            "sounds": [],
            "volume": project.volume,
            "layerOrder": 0,
            "tempo": project.tempo,
            "videoTransparency": 50,
            "videoState": "on",
            "textToSpeechLanguage": None,
        }

    def _generate_sprite(self, sprite: Sprite, layer_order: int) -> dict:
        """Generate a sprite target."""
        sprite_blocks = {}
        sprite_vars: dict[str, tuple[str, Any]] = {}
        sprite_lists: dict[str, tuple[str, list]] = {}
        sprite_var_name_to_id: dict[str, str] = {}
        sprite_list_name_to_id: dict[str, str] = {}

        # Register sprite-local variables
        for v in sprite.variables:
            if not v.is_global:
                vid = _uid()
                sprite_vars[vid] = (v.name, v.initial_value)
                sprite_var_name_to_id[v.name] = vid

        # Register sprite-local lists
        for lst in sprite.lists:
            if not lst.is_global:
                lid = _uid()
                sprite_lists[lid] = (lst.name, lst.initial_values)
                sprite_list_name_to_id[lst.name] = lid

        # Save and set context
        old_blocks = self.blocks
        old_var_map = self._var_name_to_id.copy()
        old_list_map = self._list_name_to_id.copy()
        self.blocks = sprite_blocks
        self._var_name_to_id.update(sprite_var_name_to_id)
        self._list_name_to_id.update(sprite_list_name_to_id)

        # Register custom blocks
        for cb in sprite.custom_blocks:
            self._register_custom_block(cb)

        # Generate scripts
        for script in sprite.scripts:
            self._generate_script(script)

        for cb in sprite.custom_blocks:
            self._generate_custom_block_def(cb)

        # Build costumes and sounds
        costumes = self._build_sprite_costumes(sprite.costumes, sprite.name)
        sounds = self._build_sprite_sounds(sprite.sounds)

        target = {
            "isStage": False,
            "name": sprite.name,
            "variables": {k: list(v) for k, v in sprite_vars.items()},
            "lists": {k: [v[0], v[1]] for k, v in sprite_lists.items()},
            "broadcasts": {},
            "blocks": dict(self.blocks),
            "comments": {},
            "currentCostume": 0,
            "costumes": costumes,
            "sounds": sounds,
            "volume": 100,
            "layerOrder": layer_order,
            "visible": sprite.visible,
            "x": sprite.x,
            "y": sprite.y,
            "size": sprite.size,
            "direction": sprite.direction,
            "draggable": False,
            "rotationStyle": sprite.rotation_style,
        }

        # Restore context
        self.blocks = old_blocks
        self.blocks.update(sprite_blocks)
        self._var_name_to_id = old_var_map
        self._var_name_to_id.update(sprite_var_name_to_id)
        self._list_name_to_id = old_list_map
        self._list_name_to_id.update(sprite_list_name_to_id)

        return target

    def _generate_script(self, script: Script):
        """Generate blocks for a script (event hat + body)."""
        hat_id = self._generate_hat_block(script)
        if not hat_id:
            return

        # Generate body blocks
        block_ids = self._generate_block_chain(script.body)

        # Link hat to first body block
        if block_ids:
            self.blocks[hat_id]["next"] = block_ids[0]
            self.blocks[block_ids[0]]["parent"] = hat_id

    def _generate_hat_block(self, script: Script) -> Optional[str]:
        """Generate the hat (event trigger) block."""
        block_id = _uid()
        event = script.event

        if event == "when flag clicked":
            self.blocks[block_id] = {
                "opcode": "event_whenflagclicked",
                "next": None, "parent": None,
                "inputs": {}, "fields": {},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }
        elif event == "when key pressed":
            key = script.event_args[0] if script.event_args else "space"
            self.blocks[block_id] = {
                "opcode": "event_whenkeypressed",
                "next": None, "parent": None,
                "inputs": {},
                "fields": {"KEY_OPTION": [key, None]},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }
        elif event == "when this sprite clicked":
            self.blocks[block_id] = {
                "opcode": "event_whenthisspriteclicked",
                "next": None, "parent": None,
                "inputs": {}, "fields": {},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }
        elif event == "when stage clicked":
            self.blocks[block_id] = {
                "opcode": "event_whenstageclicked",
                "next": None, "parent": None,
                "inputs": {}, "fields": {},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }
        elif event == "when I receive":
            msg = script.event_args[0] if script.event_args else "message1"
            bid = self._ensure_broadcast(msg)
            self.blocks[block_id] = {
                "opcode": "event_whenbroadcastreceived",
                "next": None, "parent": None,
                "inputs": {},
                "fields": {"BROADCAST_OPTION": [msg, bid]},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }
        elif event == "when backdrop switches to":
            name = script.event_args[0] if script.event_args else "backdrop1"
            self.blocks[block_id] = {
                "opcode": "event_whenbackdropswitchesto",
                "next": None, "parent": None,
                "inputs": {},
                "fields": {"BACKDROP": [name, None]},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }
        elif event == "when I start as a clone":
            self.blocks[block_id] = {
                "opcode": "control_start_as_clone",
                "next": None, "parent": None,
                "inputs": {}, "fields": {},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }
        elif event == "when loudness >":
            sensor = script.event_args[0] if script.event_args else "LOUDNESS"
            value = script.event_args[1] if len(script.event_args) > 1 else "10"
            self.blocks[block_id] = {
                "opcode": "event_whengreaterthan",
                "next": None, "parent": None,
                "inputs": {"VALUE": [1, [4, str(value)]]},
                "fields": {"WHENGREATERTHANMENU": [sensor, None]},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }
        else:
            # Unknown event, default to flag clicked
            self.blocks[block_id] = {
                "opcode": "event_whenflagclicked",
                "next": None, "parent": None,
                "inputs": {}, "fields": {},
                "shadow": False, "topLevel": True,
                "x": 0, "y": 0,
            }

        return block_id

    def _generate_block_chain(self, stmts: list[Statement]) -> list[str]:
        """Generate a chain of statement blocks, linking next/parent."""
        block_ids: list[str] = []

        for stmt in stmts:
            bid = self._generate_statement(stmt)
            if bid:
                block_ids.append(bid)

        # Chain blocks together
        for i in range(len(block_ids) - 1):
            self.blocks[block_ids[i]]["next"] = block_ids[i + 1]
            self.blocks[block_ids[i + 1]]["parent"] = block_ids[i]

        return block_ids

    def _generate_statement(self, stmt: Statement) -> Optional[str]:
        """Generate a single statement block, return its ID."""
        if isinstance(stmt, Block):
            return self._generate_block(stmt)
        elif isinstance(stmt, IfBlock):
            return self._generate_if(stmt)
        elif isinstance(stmt, ForeverBlock):
            return self._generate_forever(stmt)
        elif isinstance(stmt, RepeatBlock):
            return self._generate_repeat(stmt)
        elif isinstance(stmt, RepeatUntilBlock):
            return self._generate_repeat_until(stmt)
        elif isinstance(stmt, SetVariable):
            return self._generate_set_variable(stmt)
        elif isinstance(stmt, ChangeVariable):
            return self._generate_change_variable(stmt)
        elif isinstance(stmt, ShowVariable):
            return self._generate_show_variable(stmt)
        elif isinstance(stmt, HideVariable):
            return self._generate_hide_variable(stmt)
        elif isinstance(stmt, ListOperation):
            return self._generate_list_operation(stmt)
        elif isinstance(stmt, CustomBlockCall):
            return self._generate_custom_block_call(stmt)
        elif isinstance(stmt, CloneBlock):
            return self._generate_clone(stmt)
        elif isinstance(stmt, StopBlock):
            return self._generate_stop(stmt)
        return None

    def _generate_block(self, block: Block) -> Optional[str]:
        """Generate a named block (motion, looks, sound, etc.)."""
        block_id = _uid()
        name = block.name.lower().strip()

        # Look up in opcode table
        if name in OPCODES:
            entry = OPCODES[name]
            inputs = {}
            fields = {}

            # Check for extension
            if entry.extension:
                self.extensions.add(entry.extension)

            # Map arguments to inputs
            arg_idx = 0
            for inp_spec in entry.inputs:
                if arg_idx < len(block.args):
                    arg_expr = block.args[arg_idx]
                    if inp_spec.menu_opcode:
                        inputs[inp_spec.name] = self._encode_menu_input(
                            arg_expr, inp_spec.menu_opcode, block_id
                        )
                    elif inp_spec.type == "bool":
                        inputs[inp_spec.name] = self._encode_bool_input(arg_expr, block_id)
                    elif inp_spec.type == "color":
                        inputs[inp_spec.name] = self._encode_color_input(arg_expr)
                    elif inp_spec.type == "substack":
                        pass  # handled differently for control blocks
                    else:
                        inputs[inp_spec.name] = self._encode_input(arg_expr, block_id)
                    arg_idx += 1

            # Handle fields
            for i, field_spec in enumerate(entry.fields):
                if arg_idx < len(block.args):
                    val = self._extract_literal_str(block.args[arg_idx])
                    fields[field_spec.name] = [val, None]
                    arg_idx += 1
                elif field_spec.values:
                    fields[field_spec.name] = [field_spec.values[0], None]

            self.blocks[block_id] = {
                "opcode": entry.opcode,
                "next": None, "parent": None,
                "inputs": inputs, "fields": fields,
                "shadow": False, "topLevel": False,
            }
            return block_id

        # Handle special blocks not in the opcode table
        if name == "delete this clone":
            self.blocks[block_id] = {
                "opcode": "control_delete_this_clone",
                "next": None, "parent": None,
                "inputs": {}, "fields": {},
                "shadow": False, "topLevel": False,
            }
            return block_id

        # Unknown block — emit as a comment/noop
        # Try to emit it anyway with best-effort matching
        self.blocks[block_id] = {
            "opcode": "event_whenflagclicked",  # placeholder
            "next": None, "parent": None,
            "inputs": {}, "fields": {},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_if(self, node: IfBlock) -> str:
        block_id = _uid()
        inputs: dict[str, Any] = {}

        # Condition
        inputs["CONDITION"] = self._encode_bool_input(node.condition, block_id)

        # If-body substack
        if node.body:
            body_ids = self._generate_block_chain(node.body)
            if body_ids:
                inputs["SUBSTACK"] = [2, body_ids[0]]
                self.blocks[body_ids[0]]["parent"] = block_id

        opcode = "control_if"

        # Else-body
        if node.else_body:
            opcode = "control_if_else"
            else_ids = self._generate_block_chain(node.else_body)
            if else_ids:
                inputs["SUBSTACK2"] = [2, else_ids[0]]
                self.blocks[else_ids[0]]["parent"] = block_id

        self.blocks[block_id] = {
            "opcode": opcode,
            "next": None, "parent": None,
            "inputs": inputs, "fields": {},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_forever(self, node: ForeverBlock) -> str:
        block_id = _uid()
        inputs: dict[str, Any] = {}

        if node.body:
            body_ids = self._generate_block_chain(node.body)
            if body_ids:
                inputs["SUBSTACK"] = [2, body_ids[0]]
                self.blocks[body_ids[0]]["parent"] = block_id

        self.blocks[block_id] = {
            "opcode": "control_forever",
            "next": None, "parent": None,
            "inputs": inputs, "fields": {},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_repeat(self, node: RepeatBlock) -> str:
        block_id = _uid()
        inputs: dict[str, Any] = {}

        inputs["TIMES"] = self._encode_input(node.times, block_id)

        if node.body:
            body_ids = self._generate_block_chain(node.body)
            if body_ids:
                inputs["SUBSTACK"] = [2, body_ids[0]]
                self.blocks[body_ids[0]]["parent"] = block_id

        self.blocks[block_id] = {
            "opcode": "control_repeat",
            "next": None, "parent": None,
            "inputs": inputs, "fields": {},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_repeat_until(self, node: RepeatUntilBlock) -> str:
        block_id = _uid()
        inputs: dict[str, Any] = {}

        inputs["CONDITION"] = self._encode_bool_input(node.condition, block_id)

        if node.body:
            body_ids = self._generate_block_chain(node.body)
            if body_ids:
                inputs["SUBSTACK"] = [2, body_ids[0]]
                self.blocks[body_ids[0]]["parent"] = block_id

        self.blocks[block_id] = {
            "opcode": "control_repeat_until",
            "next": None, "parent": None,
            "inputs": inputs, "fields": {},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_set_variable(self, stmt: SetVariable) -> str:
        block_id = _uid()
        var_id = self._ensure_variable(stmt.name)

        self.blocks[block_id] = {
            "opcode": "data_setvariableto",
            "next": None, "parent": None,
            "inputs": {"VALUE": self._encode_input(stmt.value, block_id)},
            "fields": {"VARIABLE": [stmt.name, var_id]},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_change_variable(self, stmt: ChangeVariable) -> str:
        block_id = _uid()
        var_id = self._ensure_variable(stmt.name)

        self.blocks[block_id] = {
            "opcode": "data_changevariableby",
            "next": None, "parent": None,
            "inputs": {"VALUE": self._encode_input(stmt.value, block_id)},
            "fields": {"VARIABLE": [stmt.name, var_id]},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_show_variable(self, stmt: ShowVariable) -> str:
        block_id = _uid()
        var_id = self._ensure_variable(stmt.name)

        self.blocks[block_id] = {
            "opcode": "data_showvariable",
            "next": None, "parent": None,
            "inputs": {},
            "fields": {"VARIABLE": [stmt.name, var_id]},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_hide_variable(self, stmt: HideVariable) -> str:
        block_id = _uid()
        var_id = self._ensure_variable(stmt.name)

        self.blocks[block_id] = {
            "opcode": "data_hidevariable",
            "next": None, "parent": None,
            "inputs": {},
            "fields": {"VARIABLE": [stmt.name, var_id]},
            "shadow": False, "topLevel": False,
        }
        return block_id

    def _generate_list_operation(self, stmt: ListOperation) -> str:
        block_id = _uid()
        list_id = self._ensure_list(stmt.list_name)

        if stmt.operation == "add":
            value_input = self._encode_input(stmt.args[0], block_id) if stmt.args else [1, [10, ""]]
            self.blocks[block_id] = {
                "opcode": "data_addtolist",
                "next": None, "parent": None,
                "inputs": {"ITEM": value_input},
                "fields": {"LIST": [stmt.list_name, list_id]},
                "shadow": False, "topLevel": False,
            }
        elif stmt.operation == "delete":
            index_input = self._encode_input(stmt.args[0], block_id) if stmt.args else [1, [4, "1"]]
            self.blocks[block_id] = {
                "opcode": "data_deleteoflist",
                "next": None, "parent": None,
                "inputs": {"INDEX": index_input},
                "fields": {"LIST": [stmt.list_name, list_id]},
                "shadow": False, "topLevel": False,
            }
        elif stmt.operation == "delete_all":
            self.blocks[block_id] = {
                "opcode": "data_deletealloflist",
                "next": None, "parent": None,
                "inputs": {},
                "fields": {"LIST": [stmt.list_name, list_id]},
                "shadow": False, "topLevel": False,
            }
        elif stmt.operation == "insert":
            item_input = self._encode_input(stmt.args[0], block_id) if len(stmt.args) > 0 else [1, [10, ""]]
            index_input = self._encode_input(stmt.args[1], block_id) if len(stmt.args) > 1 else [1, [4, "1"]]
            self.blocks[block_id] = {
                "opcode": "data_insertatlist",
                "next": None, "parent": None,
                "inputs": {"ITEM": item_input, "INDEX": index_input},
                "fields": {"LIST": [stmt.list_name, list_id]},
                "shadow": False, "topLevel": False,
            }
        elif stmt.operation == "replace":
            index_input = self._encode_input(stmt.args[0], block_id) if len(stmt.args) > 0 else [1, [4, "1"]]
            item_input = self._encode_input(stmt.args[1], block_id) if len(stmt.args) > 1 else [1, [10, ""]]
            self.blocks[block_id] = {
                "opcode": "data_replaceitemoflist",
                "next": None, "parent": None,
                "inputs": {"INDEX": index_input, "ITEM": item_input},
                "fields": {"LIST": [stmt.list_name, list_id]},
                "shadow": False, "topLevel": False,
            }

        return block_id

    def _generate_clone(self, stmt: CloneBlock) -> str:
        block_id = _uid()

        if stmt.action == "create":
            target = stmt.target or "myself"
            # Create menu block
            menu_id = _uid()
            self.blocks[menu_id] = {
                "opcode": "control_create_clone_of_menu",
                "next": None, "parent": block_id,
                "inputs": {},
                "fields": {"CLONE_OPTION": ["_myself_" if target == "myself" else target, None]},
                "shadow": True, "topLevel": False,
            }
            self.blocks[block_id] = {
                "opcode": "control_create_clone_of",
                "next": None, "parent": None,
                "inputs": {"CLONE_OPTION": [1, menu_id]},
                "fields": {},
                "shadow": False, "topLevel": False,
            }
        elif stmt.action == "delete":
            self.blocks[block_id] = {
                "opcode": "control_delete_this_clone",
                "next": None, "parent": None,
                "inputs": {}, "fields": {},
                "shadow": False, "topLevel": False,
            }

        return block_id

    def _generate_stop(self, stmt: StopBlock) -> str:
        block_id = _uid()
        self.blocks[block_id] = {
            "opcode": "control_stop",
            "next": None, "parent": None,
            "inputs": {},
            "fields": {"STOP_OPTION": [stmt.mode, None]},
            "shadow": False, "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "hasnext": "false" if stmt.mode == "all" else "true",
            },
        }
        return block_id

    def _generate_custom_block_call(self, stmt: CustomBlockCall) -> str:
        block_id = _uid()
        proccode = self._custom_block_procodes.get(stmt.name, stmt.name)
        arg_ids = self._custom_block_arg_ids.get(stmt.name, [])
        arg_names = self._custom_block_arg_names.get(stmt.name, [])

        inputs = {}
        argumentids = []
        for i, aid in enumerate(arg_ids):
            input_id = _uid()
            argumentids.append(input_id)
            if i < len(stmt.args):
                inputs[input_id] = self._encode_input(stmt.args[i], block_id)
            else:
                inputs[input_id] = [1, [10, ""]]

        self.blocks[block_id] = {
            "opcode": "procedures_call",
            "next": None, "parent": None,
            "inputs": inputs,
            "fields": {},
            "shadow": False, "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": proccode,
                "argumentids": str(argumentids).replace("'", '"'),
                "warp": "false",
            },
        }
        return block_id

    def _register_custom_block(self, cb: CustomBlockDef):
        """Register a custom block for later call resolution."""
        placeholders = " ".join(["%s"] * len(cb.params))
        proccode = f"{cb.name} {placeholders}".strip()
        arg_ids = [_uid() for _ in cb.params]
        self._custom_block_procodes[cb.name] = proccode
        self._custom_block_arg_ids[cb.name] = arg_ids
        self._custom_block_arg_names[cb.name] = cb.params

    def _generate_custom_block_def(self, cb: CustomBlockDef):
        """Generate procedures_definition + procedures_prototype blocks."""
        self._register_custom_block(cb)

        def_id = _uid()
        proto_id = _uid()
        proccode = self._custom_block_procodes[cb.name]
        arg_ids = self._custom_block_arg_ids[cb.name]

        # Create argument reporter blocks
        arg_reporter_inputs = {}
        for i, (aid, pname) in enumerate(zip(arg_ids, cb.params)):
            reporter_id = _uid()
            ptype = cb.param_types[i] if i < len(cb.param_types) else "string"
            reporter_opcode = "argument_reporter_string_number"
            if ptype == "boolean":
                reporter_opcode = "argument_reporter_boolean"

            self.blocks[reporter_id] = {
                "opcode": reporter_opcode,
                "next": None, "parent": proto_id,
                "inputs": {},
                "fields": {"VALUE": [pname, None]},
                "shadow": True, "topLevel": False,
            }
            arg_reporter_inputs[aid] = [1, reporter_id]

        # Prototype
        argumentnames = [p for p in cb.params]
        argumentdefaults = ["" for _ in cb.params]
        self.blocks[proto_id] = {
            "opcode": "procedures_prototype",
            "next": None, "parent": def_id,
            "inputs": arg_reporter_inputs,
            "fields": {},
            "shadow": True, "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": proccode,
                "argumentids": str(arg_ids).replace("'", '"'),
                "argumentnames": str(argumentnames).replace("'", '"'),
                "argumentdefaults": str(argumentdefaults).replace("'", '"'),
                "warp": "false",
            },
        }

        # Definition
        self.blocks[def_id] = {
            "opcode": "procedures_definition",
            "next": None, "parent": None,
            "inputs": {"custom_block": [1, proto_id]},
            "fields": {},
            "shadow": False, "topLevel": True,
            "x": 0, "y": 0,
        }

        # Generate body
        body_ids = self._generate_block_chain(cb.body)
        if body_ids:
            self.blocks[def_id]["next"] = body_ids[0]
            self.blocks[body_ids[0]]["parent"] = def_id

    # --- Input encoding ---

    def _encode_input(self, expr: Expression, parent_id: str) -> list:
        """Encode an expression as a Scratch input value."""
        if isinstance(expr, Literal):
            if isinstance(expr.value, (int, float)):
                return [1, [4, str(expr.value)]]
            return [1, [10, str(expr.value)]]

        if isinstance(expr, ColorLiteral):
            return [1, [9, expr.value]]

        if isinstance(expr, VarRef):
            var_id = self._ensure_variable(expr.name)
            return [3, [12, expr.name, var_id], [4, "0"]]

        if isinstance(expr, ListRef):
            list_id = self._ensure_list(expr.name)
            return [3, [13, expr.name, list_id], [4, ""]]

        # Complex expression — generate a reporter block
        reporter_id = self._generate_reporter(expr, parent_id)
        if reporter_id:
            return [3, reporter_id, [4, "0"]]

        return [1, [10, ""]]

    def _encode_bool_input(self, expr: Expression, parent_id: str) -> list:
        """Encode a boolean expression as a Scratch input."""
        reporter_id = self._generate_reporter(expr, parent_id)
        if reporter_id:
            return [2, reporter_id]
        return [2, None]

    def _encode_color_input(self, expr: Expression) -> list:
        """Encode a color expression."""
        if isinstance(expr, ColorLiteral):
            return [1, [9, expr.value]]
        if isinstance(expr, Literal) and isinstance(expr.value, str) and expr.value.startswith("#"):
            return [1, [9, expr.value]]
        return [1, [9, "#000000"]]

    def _encode_menu_input(self, expr: Expression, menu_opcode: str, parent_id: str) -> list:
        """Encode a menu input with shadow block."""
        menu_id = _uid()
        value = self._extract_literal_str(expr)

        field_name = MENU_FIELDS.get(menu_opcode, "VALUE")

        self.blocks[menu_id] = {
            "opcode": menu_opcode,
            "next": None, "parent": parent_id,
            "inputs": {},
            "fields": {field_name: [value, None]},
            "shadow": True, "topLevel": False,
        }

        return [1, menu_id]

    def _generate_reporter(self, expr: Expression, parent_id: str) -> Optional[str]:
        """Generate a reporter block for a complex expression. Returns block ID."""
        if isinstance(expr, Literal):
            # Literals don't need reporter blocks — they're inlined
            return None

        if isinstance(expr, VarRef):
            # Variable reporters are encoded inline, not as blocks
            return None

        if isinstance(expr, BinaryOp):
            return self._generate_binary_op(expr, parent_id)

        if isinstance(expr, UnaryOp):
            return self._generate_unary_op(expr, parent_id)

        if isinstance(expr, FunctionCall):
            return self._generate_function_call(expr, parent_id)

        return None

    def _generate_binary_op(self, expr: BinaryOp, parent_id: str) -> str:
        block_id = _uid()
        opcode = BINARY_OPS.get(expr.op)
        if not opcode:
            opcode = "operator_add"  # fallback

        if expr.op in ("and", "or"):
            # Boolean binary ops
            self.blocks[block_id] = {
                "opcode": opcode,
                "next": None, "parent": parent_id,
                "inputs": {
                    "OPERAND1": self._encode_bool_input(expr.left, block_id),
                    "OPERAND2": self._encode_bool_input(expr.right, block_id),
                },
                "fields": {},
                "shadow": False, "topLevel": False,
            }
        elif expr.op in (">", "<", "="):
            # Comparison ops
            self.blocks[block_id] = {
                "opcode": opcode,
                "next": None, "parent": parent_id,
                "inputs": {
                    "OPERAND1": self._encode_input(expr.left, block_id),
                    "OPERAND2": self._encode_input(expr.right, block_id),
                },
                "fields": {},
                "shadow": False, "topLevel": False,
            }
        else:
            # Arithmetic ops
            self.blocks[block_id] = {
                "opcode": opcode,
                "next": None, "parent": parent_id,
                "inputs": {
                    "NUM1": self._encode_input(expr.left, block_id),
                    "NUM2": self._encode_input(expr.right, block_id),
                },
                "fields": {},
                "shadow": False, "topLevel": False,
            }

        return block_id

    def _generate_unary_op(self, expr: UnaryOp, parent_id: str) -> str:
        block_id = _uid()

        if expr.op == "not":
            self.blocks[block_id] = {
                "opcode": "operator_not",
                "next": None, "parent": parent_id,
                "inputs": {
                    "OPERAND": self._encode_bool_input(expr.operand, block_id),
                },
                "fields": {},
                "shadow": False, "topLevel": False,
            }
        elif expr.op == "-":
            # Negate: 0 - operand
            self.blocks[block_id] = {
                "opcode": "operator_subtract",
                "next": None, "parent": parent_id,
                "inputs": {
                    "NUM1": [1, [4, "0"]],
                    "NUM2": self._encode_input(expr.operand, block_id),
                },
                "fields": {},
                "shadow": False, "topLevel": False,
            }

        return block_id

    def _generate_function_call(self, expr: FunctionCall, parent_id: str) -> str:
        """Generate a reporter function call block."""
        block_id = _uid()
        name = expr.name.lower().strip()

        if name in OPCODES:
            entry = OPCODES[name]
            inputs = {}
            fields = {}

            if entry.extension:
                self.extensions.add(entry.extension)

            arg_idx = 0
            for inp_spec in entry.inputs:
                if arg_idx < len(expr.args):
                    if inp_spec.menu_opcode:
                        inputs[inp_spec.name] = self._encode_menu_input(
                            expr.args[arg_idx], inp_spec.menu_opcode, block_id
                        )
                    elif inp_spec.type == "bool":
                        inputs[inp_spec.name] = self._encode_bool_input(expr.args[arg_idx], block_id)
                    else:
                        inputs[inp_spec.name] = self._encode_input(expr.args[arg_idx], block_id)
                    arg_idx += 1

            for field_spec in entry.fields:
                if arg_idx < len(expr.args):
                    val = self._extract_literal_str(expr.args[arg_idx])
                    fields[field_spec.name] = [val, None]
                    arg_idx += 1
                elif field_spec.values:
                    fields[field_spec.name] = [field_spec.values[0], None]

            self.blocks[block_id] = {
                "opcode": entry.opcode,
                "next": None, "parent": parent_id,
                "inputs": inputs, "fields": fields,
                "shadow": False, "topLevel": False,
            }
            return block_id

        # Fallback — unknown reporter
        self.blocks[block_id] = {
            "opcode": "operator_add",
            "next": None, "parent": parent_id,
            "inputs": {"NUM1": [1, [4, "0"]], "NUM2": [1, [4, "0"]]},
            "fields": {},
            "shadow": False, "topLevel": False,
        }
        return block_id

    # --- Helpers ---

    def _ensure_variable(self, name: str) -> str:
        """Get or create a variable ID for the given name."""
        if name in self._var_name_to_id:
            return self._var_name_to_id[name]
        vid = _uid()
        self.variables[vid] = (name, 0)
        self._var_name_to_id[name] = vid
        return vid

    def _ensure_list(self, name: str) -> str:
        if name in self._list_name_to_id:
            return self._list_name_to_id[name]
        lid = _uid()
        self.lists[lid] = (name, [])
        self._list_name_to_id[name] = lid
        return lid

    def _ensure_broadcast(self, name: str) -> str:
        if name in self._broadcast_name_to_id:
            return self._broadcast_name_to_id[name]
        bid = _uid()
        self.broadcasts[bid] = name
        self._broadcast_name_to_id[name] = bid
        return bid

    def _scan_broadcasts(self, project: Project):
        """Scan the entire project for broadcast names and register them."""
        all_scripts = list(project.stage_scripts)
        for sprite in project.sprites:
            all_scripts.extend(sprite.scripts)

        for script in all_scripts:
            if script.event == "when I receive" and script.event_args:
                self._ensure_broadcast(script.event_args[0])
            self._scan_stmts_for_broadcasts(script.body)

    def _scan_stmts_for_broadcasts(self, stmts: list[Statement]):
        for stmt in stmts:
            if isinstance(stmt, Block) and stmt.name in ("broadcast", "broadcast and wait"):
                if stmt.args and isinstance(stmt.args[0], Literal):
                    self._ensure_broadcast(str(stmt.args[0].value))
            if isinstance(stmt, IfBlock):
                self._scan_stmts_for_broadcasts(stmt.body)
                self._scan_stmts_for_broadcasts(stmt.else_body)
            elif isinstance(stmt, ForeverBlock):
                self._scan_stmts_for_broadcasts(stmt.body)
            elif isinstance(stmt, RepeatBlock):
                self._scan_stmts_for_broadcasts(stmt.body)
            elif isinstance(stmt, RepeatUntilBlock):
                self._scan_stmts_for_broadcasts(stmt.body)

    def _extract_literal_str(self, expr: Expression) -> str:
        """Extract a string value from an expression for use in fields/menus."""
        if isinstance(expr, Literal):
            return str(expr.value)
        if isinstance(expr, VarRef):
            return expr.name
        if isinstance(expr, ColorLiteral):
            return expr.value
        return ""

    def _build_stage_costumes(self, backdrops: list[str]) -> list[dict]:
        """Build costume entries for the stage."""
        if not backdrops:
            return [_default_backdrop()]

        costumes = []
        for i, name in enumerate(backdrops):
            costumes.append({
                "name": name,
                "dataFormat": "svg",
                "assetId": _placeholder_hash(name),
                "md5ext": f"{_placeholder_hash(name)}.svg",
                "rotationCenterX": 240,
                "rotationCenterY": 180,
            })
        return costumes or [_default_backdrop()]

    def _build_sprite_costumes(self, costume_names: list[str], sprite_name: str) -> list[dict]:
        """Build costume entries for a sprite."""
        if not costume_names:
            return [_default_costume(sprite_name)]

        costumes = []
        for name in costume_names:
            costumes.append({
                "name": name,
                "dataFormat": "svg",
                "assetId": _placeholder_hash(name),
                "md5ext": f"{_placeholder_hash(name)}.svg",
                "rotationCenterX": 48,
                "rotationCenterY": 50,
            })
        return costumes

    def _build_sprite_sounds(self, sound_names: list[str]) -> list[dict]:
        if not sound_names:
            return []
        sounds = []
        for name in sound_names:
            sounds.append({
                "name": name,
                "assetId": _placeholder_hash(name),
                "dataFormat": "wav",
                "md5ext": f"{_placeholder_hash(name)}.wav",
                "rate": 48000,
                "sampleCount": 0,
            })
        return sounds


def _default_backdrop() -> dict:
    return {
        "name": "backdrop1",
        "dataFormat": "svg",
        "assetId": "cd21514d0531fdffb22204e0ec5ed84a",
        "md5ext": "cd21514d0531fdffb22204e0ec5ed84a.svg",
        "rotationCenterX": 240,
        "rotationCenterY": 180,
    }


def _default_costume(sprite_name: str) -> dict:
    return {
        "name": f"{sprite_name}-a",
        "dataFormat": "svg",
        "assetId": "bcf454acf82e4504149f7ffe07081dbc",
        "md5ext": "bcf454acf82e4504149f7ffe07081dbc.svg",
        "rotationCenterX": 48,
        "rotationCenterY": 50,
    }


def _placeholder_hash(name: str) -> str:
    """Generate a deterministic placeholder hash for an asset name.
    This will be replaced with real asset hashes by the bundler."""
    import hashlib

    return hashlib.md5(name.encode()).hexdigest()


def generate(project) -> dict:
    """Generate project.json from a Project AST."""
    gen = CodeGenerator()
    return gen.generate(project)
