"""Complete opcode table mapping DSL block names to Scratch 3.0 opcodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InputSpec:
    name: str
    type: str  # "number", "string", "bool", "substack", "menu", "color", "angle"
    menu_opcode: Optional[str] = None  # for menu-type inputs


@dataclass
class FieldSpec:
    name: str
    values: Optional[list[str]] = None  # allowed values, None = freeform


@dataclass
class OpcodeEntry:
    opcode: str
    inputs: list[InputSpec] = field(default_factory=list)
    fields: list[FieldSpec] = field(default_factory=list)
    is_hat: bool = False
    is_reporter: bool = False
    is_boolean: bool = False
    is_terminal: bool = False
    extension: Optional[str] = None


# fmt: off
OPCODES: dict[str, OpcodeEntry] = {
    # === EVENTS (hat blocks) ===
    "when flag clicked": OpcodeEntry(
        opcode="event_whenflagclicked", is_hat=True,
    ),
    "when key pressed": OpcodeEntry(
        opcode="event_whenkeypressed", is_hat=True,
        fields=[FieldSpec("KEY_OPTION", ["space", "up arrow", "down arrow", "left arrow", "right arrow", "any", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])],
    ),
    "when this sprite clicked": OpcodeEntry(
        opcode="event_whenthisspriteclicked", is_hat=True,
    ),
    "when stage clicked": OpcodeEntry(
        opcode="event_whenstageclicked", is_hat=True,
    ),
    "when backdrop switches to": OpcodeEntry(
        opcode="event_whenbackdropswitchesto", is_hat=True,
        fields=[FieldSpec("BACKDROP")],
    ),
    "when loudness >": OpcodeEntry(
        opcode="event_whengreaterthan", is_hat=True,
        fields=[FieldSpec("WHENGREATERTHANMENU", ["LOUDNESS", "TIMER"])],
        inputs=[InputSpec("VALUE", "number")],
    ),
    "when I receive": OpcodeEntry(
        opcode="event_whenbroadcastreceived", is_hat=True,
        fields=[FieldSpec("BROADCAST_OPTION")],
    ),
    "broadcast": OpcodeEntry(
        opcode="event_broadcast",
        inputs=[InputSpec("BROADCAST_INPUT", "string")],
    ),
    "broadcast and wait": OpcodeEntry(
        opcode="event_broadcastandwait",
        inputs=[InputSpec("BROADCAST_INPUT", "string")],
    ),
    "when I start as a clone": OpcodeEntry(
        opcode="control_start_as_clone", is_hat=True,
    ),

    # === MOTION ===
    "move": OpcodeEntry(
        opcode="motion_movesteps",
        inputs=[InputSpec("STEPS", "number")],
    ),
    "turn right": OpcodeEntry(
        opcode="motion_turnright",
        inputs=[InputSpec("DEGREES", "number")],
    ),
    "turn left": OpcodeEntry(
        opcode="motion_turnleft",
        inputs=[InputSpec("DEGREES", "number")],
    ),
    "go to": OpcodeEntry(
        opcode="motion_goto",
        inputs=[InputSpec("TO", "menu", "motion_goto_menu")],
    ),
    "go to x y": OpcodeEntry(
        opcode="motion_gotoxy",
        inputs=[InputSpec("X", "number"), InputSpec("Y", "number")],
    ),
    "glide to": OpcodeEntry(
        opcode="motion_glideto",
        inputs=[InputSpec("SECS", "number"), InputSpec("TO", "menu", "motion_glideto_menu")],
    ),
    "glide to x y": OpcodeEntry(
        opcode="motion_glidesecstoxy",
        inputs=[InputSpec("SECS", "number"), InputSpec("X", "number"), InputSpec("Y", "number")],
    ),
    "point in direction": OpcodeEntry(
        opcode="motion_pointindirection",
        inputs=[InputSpec("DIRECTION", "angle")],
    ),
    "point towards": OpcodeEntry(
        opcode="motion_pointtowards",
        inputs=[InputSpec("TOWARDS", "menu", "motion_pointtowards_menu")],
    ),
    "change x by": OpcodeEntry(
        opcode="motion_changexby",
        inputs=[InputSpec("DX", "number")],
    ),
    "change y by": OpcodeEntry(
        opcode="motion_changeyby",
        inputs=[InputSpec("DY", "number")],
    ),
    "set x to": OpcodeEntry(
        opcode="motion_setx",
        inputs=[InputSpec("X", "number")],
    ),
    "set y to": OpcodeEntry(
        opcode="motion_sety",
        inputs=[InputSpec("Y", "number")],
    ),
    "if on edge bounce": OpcodeEntry(opcode="motion_ifonedgebounce"),
    "set rotation style": OpcodeEntry(
        opcode="motion_setrotationstyle",
        fields=[FieldSpec("STYLE", ["left-right", "don't rotate", "all around"])],
    ),
    # Motion reporters
    "x position": OpcodeEntry(opcode="motion_xposition", is_reporter=True),
    "y position": OpcodeEntry(opcode="motion_yposition", is_reporter=True),
    "direction": OpcodeEntry(opcode="motion_direction", is_reporter=True),

    # === LOOKS ===
    "say for": OpcodeEntry(
        opcode="looks_sayforsecs",
        inputs=[InputSpec("MESSAGE", "string"), InputSpec("SECS", "number")],
    ),
    "say": OpcodeEntry(
        opcode="looks_say",
        inputs=[InputSpec("MESSAGE", "string")],
    ),
    "think for": OpcodeEntry(
        opcode="looks_thinkforsecs",
        inputs=[InputSpec("MESSAGE", "string"), InputSpec("SECS", "number")],
    ),
    "think": OpcodeEntry(
        opcode="looks_think",
        inputs=[InputSpec("MESSAGE", "string")],
    ),
    "switch costume to": OpcodeEntry(
        opcode="looks_switchcostumeto",
        inputs=[InputSpec("COSTUME", "menu", "looks_costume")],
    ),
    "next costume": OpcodeEntry(opcode="looks_nextcostume"),
    "switch backdrop to": OpcodeEntry(
        opcode="looks_switchbackdropto",
        inputs=[InputSpec("BACKDROP", "menu", "looks_backdrops")],
    ),
    "switch backdrop to and wait": OpcodeEntry(
        opcode="looks_switchbackdroptoandwait",
        inputs=[InputSpec("BACKDROP", "menu", "looks_backdrops")],
    ),
    "next backdrop": OpcodeEntry(opcode="looks_nextbackdrop"),
    "change size by": OpcodeEntry(
        opcode="looks_changesizeby",
        inputs=[InputSpec("CHANGE", "number")],
    ),
    "set size to": OpcodeEntry(
        opcode="looks_setsizeto",
        inputs=[InputSpec("SIZE", "number")],
    ),
    "change effect by": OpcodeEntry(
        opcode="looks_changeeffectby",
        fields=[FieldSpec("EFFECT", ["COLOR", "FISHEYE", "WHIRL", "PIXELATE", "MOSAIC", "BRIGHTNESS", "GHOST"])],
        inputs=[InputSpec("CHANGE", "number")],
    ),
    "set effect to": OpcodeEntry(
        opcode="looks_seteffectto",
        fields=[FieldSpec("EFFECT", ["COLOR", "FISHEYE", "WHIRL", "PIXELATE", "MOSAIC", "BRIGHTNESS", "GHOST"])],
        inputs=[InputSpec("VALUE", "number")],
    ),
    "clear graphic effects": OpcodeEntry(opcode="looks_cleargraphiceffects"),
    "show": OpcodeEntry(opcode="looks_show"),
    "hide": OpcodeEntry(opcode="looks_hide"),
    "go to layer": OpcodeEntry(
        opcode="looks_gotofrontback",
        fields=[FieldSpec("FRONT_BACK", ["front", "back"])],
    ),
    "change layer by": OpcodeEntry(
        opcode="looks_goforwardbackwardlayers",
        fields=[FieldSpec("FORWARD_BACKWARD", ["forward", "backward"])],
        inputs=[InputSpec("NUM", "number")],
    ),
    # Looks reporters
    "costume number": OpcodeEntry(opcode="looks_costumenumbername", is_reporter=True, fields=[FieldSpec("NUMBER_NAME", ["number", "name"])]),
    "costume name": OpcodeEntry(opcode="looks_costumenumbername", is_reporter=True, fields=[FieldSpec("NUMBER_NAME", ["number", "name"])]),
    "backdrop number": OpcodeEntry(opcode="looks_backdropnumbername", is_reporter=True, fields=[FieldSpec("NUMBER_NAME", ["number", "name"])]),
    "backdrop name": OpcodeEntry(opcode="looks_backdropnumbername", is_reporter=True, fields=[FieldSpec("NUMBER_NAME", ["number", "name"])]),
    "size": OpcodeEntry(opcode="looks_size", is_reporter=True),

    # === SOUND ===
    "play sound until done": OpcodeEntry(
        opcode="sound_playuntildone",
        inputs=[InputSpec("SOUND_MENU", "menu", "sound_sounds_menu")],
    ),
    "start sound": OpcodeEntry(
        opcode="sound_play",
        inputs=[InputSpec("SOUND_MENU", "menu", "sound_sounds_menu")],
    ),
    "stop all sounds": OpcodeEntry(opcode="sound_stopallsounds"),
    "change volume by": OpcodeEntry(
        opcode="sound_changevolumeby",
        inputs=[InputSpec("VOLUME", "number")],
    ),
    "set volume to": OpcodeEntry(
        opcode="sound_setvolumeto",
        inputs=[InputSpec("VOLUME", "number")],
    ),
    "change sound effect by": OpcodeEntry(
        opcode="sound_changeeffectby",
        fields=[FieldSpec("EFFECT", ["PITCH", "PAN"])],
        inputs=[InputSpec("VALUE", "number")],
    ),
    "set sound effect to": OpcodeEntry(
        opcode="sound_seteffectto",
        fields=[FieldSpec("EFFECT", ["PITCH", "PAN"])],
        inputs=[InputSpec("VALUE", "number")],
    ),
    "clear sound effects": OpcodeEntry(opcode="sound_cleareffects"),
    "volume": OpcodeEntry(opcode="sound_volume", is_reporter=True),

    # === CONTROL ===
    "wait": OpcodeEntry(
        opcode="control_wait",
        inputs=[InputSpec("DURATION", "number")],
    ),
    "wait until": OpcodeEntry(
        opcode="control_wait_until",
        inputs=[InputSpec("CONDITION", "bool")],
    ),
    "create clone of": OpcodeEntry(
        opcode="control_create_clone_of",
        inputs=[InputSpec("CLONE_OPTION", "menu", "control_create_clone_of_menu")],
    ),
    "delete this clone": OpcodeEntry(opcode="control_delete_this_clone", is_terminal=True),
    "stop all": OpcodeEntry(
        opcode="control_stop", is_terminal=True,
        fields=[FieldSpec("STOP_OPTION", ["all", "this script", "other scripts in sprite"])],
    ),

    # === SENSING ===
    "touching": OpcodeEntry(
        opcode="sensing_touchingobject", is_boolean=True,
        inputs=[InputSpec("TOUCHINGOBJECTMENU", "menu", "sensing_touchingobjectmenu")],
    ),
    "touching color": OpcodeEntry(
        opcode="sensing_touchingcolor", is_boolean=True,
        inputs=[InputSpec("COLOR", "color")],
    ),
    "color is touching": OpcodeEntry(
        opcode="sensing_coloristouchingcolor", is_boolean=True,
        inputs=[InputSpec("COLOR", "color"), InputSpec("COLOR2", "color")],
    ),
    "distance to": OpcodeEntry(
        opcode="sensing_distanceto", is_reporter=True,
        inputs=[InputSpec("DISTANCETOMENU", "menu", "sensing_distancetomenu")],
    ),
    "ask and wait": OpcodeEntry(
        opcode="sensing_askandwait",
        inputs=[InputSpec("QUESTION", "string")],
    ),
    "answer": OpcodeEntry(opcode="sensing_answer", is_reporter=True),
    "key pressed": OpcodeEntry(
        opcode="sensing_keypressed", is_boolean=True,
        inputs=[InputSpec("KEY_OPTION", "menu", "sensing_keyoptions")],
    ),
    "mouse down": OpcodeEntry(opcode="sensing_mousedown", is_boolean=True),
    "mouse x": OpcodeEntry(opcode="sensing_mousex", is_reporter=True),
    "mouse y": OpcodeEntry(opcode="sensing_mousey", is_reporter=True),
    "set drag mode": OpcodeEntry(
        opcode="sensing_setdragmode",
        fields=[FieldSpec("DRAG_MODE", ["draggable", "not draggable"])],
    ),
    "loudness": OpcodeEntry(opcode="sensing_loudness", is_reporter=True),
    "timer": OpcodeEntry(opcode="sensing_timer", is_reporter=True),
    "reset timer": OpcodeEntry(opcode="sensing_resettimer"),
    "current": OpcodeEntry(
        opcode="sensing_current", is_reporter=True,
        fields=[FieldSpec("CURRENTMENU", ["YEAR", "MONTH", "DATE", "DAYOFWEEK", "HOUR", "MINUTE", "SECOND"])],
    ),
    "days since 2000": OpcodeEntry(opcode="sensing_dayssince2000", is_reporter=True),
    "username": OpcodeEntry(opcode="sensing_username", is_reporter=True),

    # === OPERATORS (reporters) ===
    "pick random": OpcodeEntry(
        opcode="operator_random", is_reporter=True,
        inputs=[InputSpec("FROM", "number"), InputSpec("TO", "number")],
    ),
    "join": OpcodeEntry(
        opcode="operator_join", is_reporter=True,
        inputs=[InputSpec("STRING1", "string"), InputSpec("STRING2", "string")],
    ),
    "letter of": OpcodeEntry(
        opcode="operator_letter_of", is_reporter=True,
        inputs=[InputSpec("LETTER", "number"), InputSpec("STRING", "string")],
    ),
    "length of": OpcodeEntry(
        opcode="operator_length", is_reporter=True,
        inputs=[InputSpec("STRING", "string")],
    ),
    "contains": OpcodeEntry(
        opcode="operator_contains", is_boolean=True,
        inputs=[InputSpec("STRING1", "string"), InputSpec("STRING2", "string")],
    ),
    "round": OpcodeEntry(
        opcode="operator_round", is_reporter=True,
        inputs=[InputSpec("NUM", "number")],
    ),
    "mathop": OpcodeEntry(
        opcode="operator_mathop", is_reporter=True,
        fields=[FieldSpec("OPERATOR", ["abs", "floor", "ceiling", "sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "ln", "log", "e ^", "10 ^"])],
        inputs=[InputSpec("NUM", "number")],
    ),

    # === DATA (variables/lists) ===
    "set variable to": OpcodeEntry(
        opcode="data_setvariableto",
        fields=[FieldSpec("VARIABLE")],
        inputs=[InputSpec("VALUE", "string")],
    ),
    "change variable by": OpcodeEntry(
        opcode="data_changevariableby",
        fields=[FieldSpec("VARIABLE")],
        inputs=[InputSpec("VALUE", "number")],
    ),
    "show variable": OpcodeEntry(
        opcode="data_showvariable",
        fields=[FieldSpec("VARIABLE")],
    ),
    "hide variable": OpcodeEntry(
        opcode="data_hidevariable",
        fields=[FieldSpec("VARIABLE")],
    ),
    "add to list": OpcodeEntry(
        opcode="data_addtolist",
        fields=[FieldSpec("LIST")],
        inputs=[InputSpec("ITEM", "string")],
    ),
    "delete of list": OpcodeEntry(
        opcode="data_deleteoflist",
        fields=[FieldSpec("LIST")],
        inputs=[InputSpec("INDEX", "number")],
    ),
    "delete all of list": OpcodeEntry(
        opcode="data_deletealloflist",
        fields=[FieldSpec("LIST")],
    ),
    "insert at list": OpcodeEntry(
        opcode="data_insertatlist",
        fields=[FieldSpec("LIST")],
        inputs=[InputSpec("ITEM", "string"), InputSpec("INDEX", "number")],
    ),
    "replace item of list": OpcodeEntry(
        opcode="data_replaceitemoflist",
        fields=[FieldSpec("LIST")],
        inputs=[InputSpec("INDEX", "number"), InputSpec("ITEM", "string")],
    ),
    "item of list": OpcodeEntry(
        opcode="data_itemoflist", is_reporter=True,
        fields=[FieldSpec("LIST")],
        inputs=[InputSpec("INDEX", "number")],
    ),
    "item # of in list": OpcodeEntry(
        opcode="data_itemnumoflist", is_reporter=True,
        fields=[FieldSpec("LIST")],
        inputs=[InputSpec("ITEM", "string")],
    ),
    "length of list": OpcodeEntry(
        opcode="data_lengthoflist", is_reporter=True,
        fields=[FieldSpec("LIST")],
    ),
    "list contains": OpcodeEntry(
        opcode="data_listcontainsitem", is_boolean=True,
        fields=[FieldSpec("LIST")],
        inputs=[InputSpec("ITEM", "string")],
    ),
    "show list": OpcodeEntry(
        opcode="data_showlist",
        fields=[FieldSpec("LIST")],
    ),
    "hide list": OpcodeEntry(
        opcode="data_hidelist",
        fields=[FieldSpec("LIST")],
    ),

    # === PEN EXTENSION ===
    "pen erase all": OpcodeEntry(opcode="pen_clear", extension="pen"),
    "pen stamp": OpcodeEntry(opcode="pen_stamp", extension="pen"),
    "pen down": OpcodeEntry(opcode="pen_penDown", extension="pen"),
    "pen up": OpcodeEntry(opcode="pen_penUp", extension="pen"),
    "set pen color to": OpcodeEntry(
        opcode="pen_setPenColorToColor", extension="pen",
        inputs=[InputSpec("COLOR", "color")],
    ),
    "change pen color by": OpcodeEntry(
        opcode="pen_changePenColorParamBy", extension="pen",
        inputs=[InputSpec("VALUE", "number")],
        fields=[FieldSpec("colorParam", ["color", "saturation", "brightness", "transparency"])],
    ),
    "set pen color param to": OpcodeEntry(
        opcode="pen_setPenColorParamTo", extension="pen",
        inputs=[InputSpec("VALUE", "number")],
        fields=[FieldSpec("colorParam", ["color", "saturation", "brightness", "transparency"])],
    ),
    "change pen size by": OpcodeEntry(
        opcode="pen_changePenSizeBy", extension="pen",
        inputs=[InputSpec("SIZE", "number")],
    ),
    "set pen size to": OpcodeEntry(
        opcode="pen_setPenSizeTo", extension="pen",
        inputs=[InputSpec("SIZE", "number")],
    ),

    # === MUSIC EXTENSION ===
    "play drum for beats": OpcodeEntry(
        opcode="music_playDrumForBeats", extension="music",
        inputs=[InputSpec("DRUM", "number"), InputSpec("BEATS", "number")],
    ),
    "rest for beats": OpcodeEntry(
        opcode="music_restForBeats", extension="music",
        inputs=[InputSpec("BEATS", "number")],
    ),
    "play note for beats": OpcodeEntry(
        opcode="music_playNoteForBeats", extension="music",
        inputs=[InputSpec("NOTE", "number"), InputSpec("BEATS", "number")],
    ),
    "set instrument to": OpcodeEntry(
        opcode="music_setInstrument", extension="music",
        inputs=[InputSpec("INSTRUMENT", "number")],
    ),
    "set tempo to": OpcodeEntry(
        opcode="music_setTempo", extension="music",
        inputs=[InputSpec("TEMPO", "number")],
    ),
    "change tempo by": OpcodeEntry(
        opcode="music_changeTempo", extension="music",
        inputs=[InputSpec("TEMPO", "number")],
    ),
    "tempo": OpcodeEntry(opcode="music_getTempo", is_reporter=True, extension="music"),
}
# fmt: on

# Menu block opcodes — these create shadow blocks for dropdown menus
MENU_OPCODES: dict[str, str] = {
    "motion_goto_menu": "motion_goto_menu",
    "motion_glideto_menu": "motion_glideto_menu",
    "motion_pointtowards_menu": "motion_pointtowards_menu",
    "looks_costume": "looks_costume",
    "looks_backdrops": "looks_backdrops",
    "sound_sounds_menu": "sound_sounds_menu",
    "control_create_clone_of_menu": "control_create_clone_of_menu",
    "sensing_touchingobjectmenu": "sensing_touchingobjectmenu",
    "sensing_distancetomenu": "sensing_distancetomenu",
    "sensing_keyoptions": "sensing_keyoptions",
}

# Menu field names — which field the menu value goes into
MENU_FIELDS: dict[str, str] = {
    "motion_goto_menu": "TO",
    "motion_glideto_menu": "TO",
    "motion_pointtowards_menu": "TOWARDS",
    "looks_costume": "COSTUME",
    "looks_backdrops": "BACKDROP",
    "sound_sounds_menu": "SOUND_MENU",
    "control_create_clone_of_menu": "CLONE_OPTION",
    "sensing_touchingobjectmenu": "TOUCHINGOBJECTMENU",
    "sensing_distancetomenu": "DISTANCETOMENU",
    "sensing_keyoptions": "KEY_OPTION",
}

# Operators that map to binary operator blocks
BINARY_OPS: dict[str, str] = {
    "+": "operator_add",
    "-": "operator_subtract",
    "*": "operator_multiply",
    "/": "operator_divide",
    ">": "operator_gt",
    "<": "operator_lt",
    "=": "operator_equals",
    "and": "operator_and",
    "or": "operator_or",
    "mod": "operator_mod",
}

UNARY_OPS: dict[str, str] = {
    "not": "operator_not",
}

# All block names for fuzzy matching
ALL_BLOCK_NAMES: list[str] = list(OPCODES.keys())
