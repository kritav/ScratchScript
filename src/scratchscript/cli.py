"""Click-based CLI for ScratchScript."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__


@click.command(cls=click.Group)
@click.version_option(version=__version__)
@click.pass_context
def main(ctx):
    """ScratchScript — convert natural language to Scratch 3.0 .sb3 files.

    \b
    Usage:
      scratchscript generate "make a cat that chases the mouse pointer"
      scratchscript compile game.scratchscript
      scratchscript generate --provider ollama "make a platformer"
    """
    pass


@main.command()
@click.argument("prompt")
@click.option("--provider", "-p", type=str, default=None, help="LLM provider (ollama, claude, openai, gemini)")
@click.option("--model", "-m", type=str, default=None, help="Model name to use")
@click.option("--output", "-o", type=str, default=None, help="Output .sb3 file path")
@click.option("--retries", "-r", type=int, default=3, help="Max retry attempts on error")
@click.option("--fast", "-f", is_flag=True, help="Skip reviewer (faster, less polished)")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def generate(prompt, provider, model, output, retries, fast, verbose):
    """Generate a Scratch project from a natural language prompt."""
    asyncio.run(_generate(prompt, provider, model, output, retries, fast, verbose))


@main.command()
@click.argument("source_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=str, default=None, help="Output .sb3 file path")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def compile(source_file, output, verbose):
    """Compile a .scratchscript file to .sb3."""
    asyncio.run(_compile_file(source_file, output, verbose))


@main.command(name="import")
@click.argument("sb3_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=str, default=None, help="Output .scratchscript file path (default: stdout)")
@click.option("--modify", "-m", type=str, default=None, help="Modify the imported project via LLM")
@click.option("--provider", "-p", type=str, default=None, help="LLM provider for --modify")
@click.option("--model", type=str, default=None, help="Model name for --modify")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def import_sb3(sb3_file, output, modify, provider, model, verbose):
    """Import an .sb3 file and decompile to ScratchScript."""
    asyncio.run(_import_sb3(sb3_file, output, modify, provider, model, verbose))


async def _generate(
    prompt: str,
    provider_name: Optional[str],
    model: Optional[str],
    output: Optional[str],
    max_retries: int,
    fast: bool,
    verbose: bool,
):
    """Generate ScratchScript from a prompt and compile to .sb3."""
    from .prompts import get_system_prompt
    from .providers import detect_provider
    from .reviewer import Reviewer, build_revision_prompt, extract_scratchscript

    # Detect provider
    try:
        provider = await detect_provider(provider_name, model)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    provider_label = type(provider).__name__.replace("Provider", "")
    click.echo(f"Using {provider_label} provider...")

    system_prompt = get_system_prompt()

    # Generate ScratchScript
    click.echo("Generating ScratchScript...")
    try:
        scratchscript = await provider.generate(prompt, system_prompt)
    except Exception as e:
        click.echo(f"Error generating code: {e}", err=True)
        sys.exit(1)

    click.echo(f"Generated ({len(scratchscript)} chars)")

    if verbose:
        click.echo("\n--- Generated ScratchScript ---")
        click.echo(scratchscript)
        click.echo("--- End ---\n")

    # Review loop (unless --fast)
    if not fast:
        reviewer = Reviewer(provider)
        max_review_cycles = 1

        for cycle in range(max_review_cycles):
            click.echo(f"Reviewing... (cycle {cycle + 1}/{max_review_cycles})")
            try:
                result = await reviewer.review(prompt, scratchscript)
            except Exception as e:
                click.echo(f"Review failed: {e}", err=True)
                break

            if result.verdict == "PASS":
                click.echo("Review passed")
                break

            click.echo(f"Reviewer found {result.summary()}")
            for issue in result.issues:
                click.echo(f"  [{issue.severity}] {issue.where}: {issue.problem}")
            if verbose:
                for issue in result.issues:
                    if issue.fix:
                        click.echo(f"    Fix: {issue.fix}")

            click.echo("Revising based on feedback...")
            revision_prompt = build_revision_prompt(prompt, scratchscript, result)
            try:
                raw = await provider.generate(revision_prompt, system_prompt)
                scratchscript = extract_scratchscript(raw)
            except Exception as e:
                click.echo(f"Revision failed: {e}", err=True)
                break

            click.echo(f"Revised ({len(scratchscript)} chars)")
            if verbose:
                click.echo("\n--- Revised ScratchScript ---")
                click.echo(scratchscript)
                click.echo("--- End ---\n")

    # Compile with retry loop
    for attempt in range(max_retries + 1):
        result = _try_compile(scratchscript, verbose)

        if result is not None:
            # Success — bundle to .sb3
            project_json = result
            output_path = output or _default_output_name(prompt)

            try:
                from .compiler.bundler import bundle

                path = await bundle(project_json, output_path)
                click.echo(f"Created: {path}")
                return
            except Exception as e:
                click.echo(f"Error bundling .sb3: {e}", err=True)
                # Try sync fallback
                from .compiler.bundler import bundle_sync

                path = bundle_sync(project_json, output_path)
                click.echo(f"Created: {path} (without asset resolution)")
                return

        # Compilation failed
        if attempt < max_retries:
            error_text = _get_compile_errors(scratchscript)
            click.echo(f"Compilation failed (attempt {attempt + 1}/{max_retries + 1}), retrying...")
            if verbose:
                click.echo(f"Errors: {error_text}")

            try:
                scratchscript = await provider.fix(scratchscript, error_text, system_prompt)
                if verbose:
                    click.echo("\n--- Fixed ScratchScript ---")
                    click.echo(scratchscript)
                    click.echo("--- End ---\n")
            except Exception as e:
                click.echo(f"Error during fix attempt: {e}", err=True)
                break
        else:
            click.echo("Failed to compile after all retries.", err=True)
            click.echo("\nGenerated ScratchScript:")
            click.echo(scratchscript)
            sys.exit(1)


async def _compile_file(source_file: str, output: Optional[str], verbose: bool):
    """Compile a .scratchscript file to .sb3."""
    source = Path(source_file).read_text()

    if verbose:
        click.echo(f"Compiling {source_file}...")

    result = _try_compile(source, verbose)
    if result is None:
        error_text = _get_compile_errors(source)
        click.echo(f"Compilation failed:\n{error_text}", err=True)
        sys.exit(1)

    output_path = output or str(Path(source_file).with_suffix(".sb3"))

    try:
        from .compiler.bundler import bundle

        path = await bundle(result, output_path)
        click.echo(f"Created: {path}")
    except Exception:
        from .compiler.bundler import bundle_sync

        path = bundle_sync(result, output_path)
        click.echo(f"Created: {path}")


def _try_compile(source: str, verbose: bool) -> Optional[dict]:
    """Try to compile ScratchScript source. Returns project.json dict or None."""
    from .compiler.autorepair import repair_project
    from .compiler.parser import ParseError, parse
    from .compiler.codegen import generate
    from .compiler.validator import validate

    try:
        project = parse(source)
    except ParseError as e:
        if verbose:
            click.echo(f"Parse error: {e}", err=True)
        return None

    # Deterministically fix near-miss block/event/reporter names before
    # validation — no LLM round-trip needed for confident matches
    repairs = repair_project(project)
    for note in repairs:
        click.echo(f"  {note}")

    # Validate
    result = validate(project)
    if not result.is_valid:
        if verbose:
            click.echo(f"Validation errors:\n{result.format_errors()}", err=True)
        # Continue anyway — validation errors are often non-fatal
        # Only block on truly broken code (parse errors)

    try:
        project_json = generate(project)
        return project_json
    except Exception as e:
        if verbose:
            click.echo(f"Codegen error: {e}", err=True)
        return None


def _get_compile_errors(source: str) -> str:
    """Get compile error messages for a source string."""
    from .compiler.autorepair import repair_project
    from .compiler.parser import ParseError, parse
    from .compiler.validator import validate

    errors = []
    try:
        project = parse(source)
        # Apply the same auto-repairs as _try_compile so the LLM only sees
        # errors it actually needs to fix
        repair_project(project)
        result = validate(project)
        if not result.is_valid:
            errors.append(result.format_errors())
    except ParseError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(str(e))

    return "\n".join(errors) if errors else "Unknown compilation error"


def _default_output_name(prompt: str) -> str:
    """Generate a default output filename from the prompt."""
    # Take first few words
    words = prompt.lower().split()[:4]
    name = "-".join(w for w in words if w.isalnum())
    if not name:
        name = "output"
    return f"{name}.sb3"


async def _import_sb3(
    sb3_file: str,
    output: Optional[str],
    modify: Optional[str],
    provider_name: Optional[str],
    model: Optional[str],
    verbose: bool,
):
    """Import an .sb3 file, decompile, and optionally modify."""
    from .compiler.bundler import unbundle
    from .compiler.decompiler import decompile

    # Unbundle
    click.echo(f"Importing {sb3_file}...", err=True)
    try:
        project_json = unbundle(sb3_file)
    except Exception as e:
        click.echo(f"Error reading .sb3: {e}", err=True)
        sys.exit(1)

    # Decompile
    try:
        scratchscript = decompile(project_json)
    except Exception as e:
        click.echo(f"Error decompiling: {e}", err=True)
        sys.exit(1)

    # Count targets for summary
    targets = project_json.get("targets", [])
    sprites = [t for t in targets if not t.get("isStage", False)]
    scripts = sum(
        1 for t in targets
        for b in t.get("blocks", {}).values()
        if isinstance(b, dict) and b.get("topLevel") and not b.get("shadow")
    )
    click.echo(
        f"Decompiled ({len(scratchscript)} chars, {len(sprites)} sprites, {scripts} scripts)",
        err=True,
    )

    # Optionally modify via LLM
    if modify:
        from .prompts import get_system_prompt
        from .providers import detect_provider

        try:
            provider = await detect_provider(provider_name, model)
        except RuntimeError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

        provider_label = type(provider).__name__.replace("Provider", "")
        click.echo(f"Using {provider_label} to modify...", err=True)

        system_prompt = get_system_prompt()
        modification_prompt = (
            f"Here is an existing ScratchScript project:\n"
            f"{scratchscript}\n\n"
            f"The user wants to modify it: {modify}\n\n"
            f"Output the complete modified ScratchScript with the requested changes applied."
        )

        try:
            scratchscript = await provider.generate(modification_prompt, system_prompt)
        except Exception as e:
            click.echo(f"Error during modification: {e}", err=True)
            sys.exit(1)

        click.echo(f"Modified ({len(scratchscript)} chars)", err=True)

        # Compile the modified code to .sb3
        result = _try_compile(scratchscript, verbose)
        if result is not None:
            sb3_output = output or str(Path(sb3_file).with_suffix("")) + "-modified.sb3"
            try:
                from .compiler.bundler import bundle
                path = await bundle(result, sb3_output)
                click.echo(f"Created: {path}", err=True)
            except Exception:
                from .compiler.bundler import bundle_sync
                path = bundle_sync(result, sb3_output)
                click.echo(f"Created: {path}", err=True)
        else:
            click.echo("Modified code failed to compile. Outputting ScratchScript:", err=True)
            click.echo(scratchscript)
        return

    # Output decompiled ScratchScript
    if output:
        Path(output).write_text(scratchscript)
        click.echo(f"Written to: {output}", err=True)
    else:
        click.echo(scratchscript)
