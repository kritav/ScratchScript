# ScratchScript
<div align="center">
  <img src="/images/scratchscript.png" width="500" />
</div>

<div align="center">
  <img src="/images/prompt.gif" width="500" />
</div>

Convert natural language descriptions into working Scratch 3.0 `.sb3` files.

Uses a two-stage architecture: an LLM generates ScratchScript DSL code, then a deterministic compiler converts it to `.sb3`.

## Install

```bash
pip install -e .

# With LLM provider support:
pip install -e ".[claude]"    # Anthropic Claude
pip install -e ".[openai]"    # OpenAI
pip install -e ".[gemini]"    # Google Gemini
pip install -e ".[all]"       # All providers
```

## Usage

### Generate from natural language (requires an LLM provider)

```bash
scratchscript generate "make a cat that chases the mouse pointer"
scratchscript generate --provider ollama "make a platformer"
scratchscript generate --provider claude -o game.sb3 "make a pong game"
```

### Compile a .scratchscript file directly

```bash
scratchscript compile game.scratchscript
scratchscript compile game.scratchscript -o output.sb3
```

## ScratchScript DSL

ScratchScript is an indentation-based language that maps to Scratch blocks:

```
project
  backdrops "Blue Sky"
  variable score = 0

  sprite Cat
    costumes "cat-a", "cat-b"
    sounds "Meow"
    position 0, 0
    size 100

    script
      when flag clicked
        forever
          move 10
          if on edge bounce
          next costume
          wait 0.2

    script
      when this sprite clicked
        play sound until done "Meow"
        change score by 1
```

See `examples/` for complete game examples (Flappy Bird, Pong, platformer).

## LLM Providers

ScratchScript auto-detects available providers in this order:

1. **Ollama** (if running locally) — `ollama serve`
2. **Claude** — set `ANTHROPIC_API_KEY`
3. **OpenAI** — set `OPENAI_API_KEY`
4. **Gemini** — set `GEMINI_API_KEY`

Override with `--provider`:
```bash
scratchscript generate --provider claude --model claude-sonnet-4-6 "make a game"
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/
ruff check src/
```

## Architecture

```
User prompt -> LLM Provider -> ScratchScript text -> Compiler -> Validation + retry loop -> .sb3 file
```

- **Lexer** (`lexer.py`): indentation-aware tokenizer
- **Parser** (`parser.py`): recursive descent parser producing AST
- **Code Generator** (`codegen.py`): AST to Scratch 3.0 project.json
- **Bundler** (`bundler.py`): project.json + assets into .sb3 ZIP
- **Validator** (`validator.py`): error checking with fuzzy suggestions
- **Asset Library** (`assets/library.py`): Scratch asset CDN download + cache

## License

MIT
