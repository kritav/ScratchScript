"""PyWebView-based GUI for ScratchScript."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Optional

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
:root {
    --bg-primary: #1a1a1e;
    --bg-secondary: #222226;
    --bg-tertiary: #2a2a2e;
    --border: rgba(255, 255, 255, 0.08);
    --text-primary: #e0e0e0;
    --text-secondary: #888;
    --text-disabled: #555;
    --accent: #4a9eff;
    --success: #4ec965;
    --error: #e55555;
    --warning: #e5a03c;
    --string: #98c379;
    --number: #d19a66;
    --keyword: #4a9eff;
    --comment: #555;
    --font-mono: "JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", "Consolas", monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}
html, body { height: 100%; overflow: hidden; }
body {
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 14px;
}
#app {
    display: flex;
    height: 100vh;
    width: 100vw;
}

/* ── Chat Panel ── */
#chat {
    flex: 0 0 55%;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--border);
    min-width: 300px;
}
#messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
}
.msg { margin-bottom: 12px; }
.msg-label {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: lowercase;
    margin-bottom: 2px;
}
.msg-user .msg-text {
    font-family: var(--font-sans);
    font-size: 14px;
    color: var(--text-primary);
    line-height: 1.4;
}
.msg-status {
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.6;
    color: var(--text-secondary);
}
.msg-status .status-line { display: block; }
.status-progress { color: var(--accent); }
.status-success { color: var(--success); }
.status-error { color: var(--error); }
.msg-agent .msg-text {
    font-family: var(--font-sans);
    font-size: 14px;
    color: var(--text-primary);
    line-height: 1.4;
}
.msg-download { margin-top: 4px; }
.msg-download a {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
    text-decoration: none;
    cursor: pointer;
    transition: color 100ms ease-out;
}
.msg-download a:hover { color: var(--accent); }
.msg-actions { margin-top: 4px; }
.msg-actions a {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
    text-decoration: none;
    cursor: pointer;
    margin-right: 16px;
    transition: color 100ms ease-out;
}
.msg-actions a:hover { color: var(--accent); }

/* ── Input Area ── */
#input-area {
    border-top: 1px solid var(--border);
    padding: 12px 16px;
}
#prompt-input {
    width: 100%;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 14px;
    padding: 8px 12px;
    resize: none;
    outline: none;
    line-height: 1.4;
    max-height: 96px;
    overflow-y: auto;
}
#prompt-input::placeholder { color: var(--text-disabled); }
#prompt-input:focus { border-color: rgba(255, 255, 255, 0.15); }

/* ── Divider ── */
#divider {
    flex: 0 0 4px;
    background: transparent;
    cursor: col-resize;
    transition: background 100ms ease-out;
}
#divider:hover, #divider.dragging { background: rgba(74, 158, 255, 0.3); }

/* ── Preview Panel ── */
#preview {
    flex: 0 0 calc(45% - 4px);
    display: flex;
    flex-direction: column;
    min-width: 250px;
}
#preview-header {
    display: none;
    padding: 6px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    align-items: center;
    gap: 8px;
}
#preview-header.visible { display: flex; }
#compile-btn {
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 3px;
    cursor: pointer;
    transition: border-color 100ms ease-out;
}
#compile-btn:hover { border-color: var(--accent); }
#edit-label {
    font-size: 11px;
    color: var(--text-secondary);
}
#code-container {
    flex: 1;
    overflow: auto;
    position: relative;
}
#code-empty {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 13px;
    color: var(--text-disabled);
    text-align: center;
    line-height: 2;
}
#code-empty a {
    color: var(--text-disabled);
    text-decoration: none;
    font-size: 12px;
    transition: color 100ms ease-out;
}
#code-empty a:hover { color: var(--accent); }
#code-display { display: none; }
#code-display.visible { display: block; }
.code-line {
    display: flex;
    line-height: 1.5;
    font-family: var(--font-mono);
    font-size: 13px;
}
.code-line:hover { background: rgba(255, 255, 255, 0.02); }
.code-line .ln {
    flex: 0 0 44px;
    text-align: right;
    padding-right: 12px;
    color: var(--text-disabled);
    user-select: none;
}
.code-line .code {
    flex: 1;
    white-space: pre;
    padding-right: 16px;
}
.code-line.error-line { border-left: 2px solid var(--error); }
#code-editor {
    display: none;
    width: 100%;
    height: 100%;
    background: var(--bg-primary);
    border: none;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 13px;
    padding: 8px 12px;
    resize: none;
    outline: none;
    line-height: 1.5;
    tab-size: 2;
}
#code-editor.visible { display: block; }

/* ── Status Bar ── */
#status-bar {
    padding: 4px 12px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-secondary);
    border-top: 1px solid var(--border);
    background: var(--bg-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }

/* ── Syntax highlighting ── */
.syn-kw { color: var(--keyword); }
.syn-str { color: var(--string); }
.syn-num { color: var(--number); }
.syn-cmt { color: var(--comment); font-style: italic; }
</style>
</head>
<body>
<div id="app">
    <div id="chat">
        <div id="messages"></div>
        <div id="input-area">
            <textarea id="prompt-input" placeholder="Describe a Scratch project..." rows="1"></textarea>
        </div>
    </div>
    <div id="divider"></div>
    <div id="preview">
        <div id="preview-header">
            <button id="compile-btn">Compile</button>
            <span id="edit-label">editing</span>
        </div>
        <div id="code-container">
            <div id="code-empty">ScratchScript will appear here<br><a href="#" id="edit-link">or write it yourself</a></div>
            <div id="code-display"></div>
            <textarea id="code-editor" spellcheck="false"></textarea>
        </div>
        <div id="status-bar">Initializing...</div>
    </div>
</div>
<script>
/* ── Constants ── */
var KEYWORDS = new Set([
    'project','sprite','stage','script','when','if','else','end',
    'forever','repeat','until','define','variable','list','broadcast',
    'costumes','costume','sounds','sound','backdrops','backdrop',
    'position','size','direction','flag','clicked','pressed','receive',
    'not','and','or','set','change','add','delete','insert','replace',
    'show','hide','global','clone','stop','to','by','of','at','in',
    'wait','move','turn','go','glide','point','say','think','switch',
    'next','play','start','create','touching','color','ask','key',
    'mouse','timer','distance','loudness','pick','random','join',
    'letter','length','round','abs','mod','forever','pen','stamp',
    'erase','clear'
]);

/* ── State ── */
var generating = false;
var editMode = false;
var currentCode = '';
var lastPrompt = '';
var currentStatusGroup = null;

/* ── Element references ── */
var chat = document.getElementById('chat');
var messages = document.getElementById('messages');
var promptInput = document.getElementById('prompt-input');
var divider = document.getElementById('divider');
var preview = document.getElementById('preview');
var previewHeader = document.getElementById('preview-header');
var codeEmpty = document.getElementById('code-empty');
var codeDisplay = document.getElementById('code-display');
var codeEditor = document.getElementById('code-editor');
var statusBar = document.getElementById('status-bar');
var compileBtn = document.getElementById('compile-btn');
var editLink = document.getElementById('edit-link');

/* ── Event dispatcher (called from Python) ── */
window.handleEvent = function(event, data) {
    switch (event) {
        case 'status': onStatus(data); break;
        case 'code': onCode(data); break;
        case 'download': onDownload(data); break;
        case 'provider': onProvider(data); break;
        case 'compile_result': onCompileResult(data); break;
        case 'generating_done': generating = false; break;
    }
};

/* ── Event handlers ── */
function onStatus(data) {
    var icon, cls, text;
    switch (data.step) {
        case 'generating':
            icon = '\u25cf'; cls = 'status-progress';
            text = 'Generating ScratchScript... (attempt ' + (data.attempt||1) + '/' + (data.max_attempts||4) + ')';
            break;
        case 'generated':
            icon = '\u2713'; cls = 'status-success';
            text = 'Generated (' + (data.chars||'?') + ' chars)';
            break;
        case 'compiling':
            icon = '\u25cf'; cls = 'status-progress';
            text = 'Compiling...';
            break;
        case 'bundling':
            icon = '\u25cf'; cls = 'status-progress';
            text = 'Bundling .sb3...';
            break;
        case 'fix_error':
            icon = '\u2717'; cls = 'status-error';
            text = data.message || 'Compile error';
            break;
        case 'retrying':
            icon = '\u25cf'; cls = 'status-progress';
            text = 'Retrying (attempt ' + data.attempt + '/' + data.max_attempts + ')...';
            break;
        case 'done':
            icon = '\u2713'; cls = 'status-success';
            text = 'Compiled successfully \u2014 ' + (data.detail || '');
            break;
        case 'failed':
            icon = '\u2717'; cls = 'status-error';
            text = data.message || 'Failed after all retries';
            addFailureActions();
            break;
        case 'error':
            icon = '\u2717'; cls = 'status-error';
            text = data.message || 'Error';
            break;
        default:
            icon = '\u25cf'; cls = 'status-progress';
            text = data.message || data.step;
    }
    addStatusLine(icon, cls, text);
}

function onCode(data) {
    currentCode = data.text;
    renderCode(data.text);
    exitEditMode();
}

function onDownload(data) {
    var filename = data.filename || 'project.sb3';
    var sizeText = data.size ? ' (' + formatSize(data.size) + ')' : '';
    var div = document.createElement('div');
    div.className = 'msg msg-download';
    var a = document.createElement('a');
    a.textContent = '\u2193 ' + filename + sizeText;
    a.href = '#';
    a.onclick = function(e) {
        e.preventDefault();
        pywebview.api.save_file();
    };
    div.appendChild(a);
    messages.appendChild(div);
    scrollChat();
}

function onProvider(data) {
    if (data.available) {
        statusBar.textContent = 'Provider: ' + data.name + ' / ' + data.model + ' \u00b7 Ready';
    } else {
        statusBar.textContent = 'No LLM provider detected \u00b7 Compile-only mode';
    }
}

function onCompileResult(data) {
    if (data.success) {
        currentCode = codeEditor.value;
        renderCode(currentCode);
        exitEditMode();
    } else {
        addStatusLine('\u2717', 'status-error', 'Compile error: ' + data.error);
    }
}

/* ── Message rendering ── */
function addUserMessage(text) {
    var div = document.createElement('div');
    div.className = 'msg msg-user';
    var label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = 'you';
    var body = document.createElement('div');
    body.className = 'msg-text';
    body.textContent = text;
    div.appendChild(label);
    div.appendChild(body);
    messages.appendChild(div);
    scrollChat();
}

function startStatusGroup() {
    currentStatusGroup = document.createElement('div');
    currentStatusGroup.className = 'msg msg-status';
    messages.appendChild(currentStatusGroup);
}

function addStatusLine(icon, cls, text) {
    if (!currentStatusGroup) startStatusGroup();
    var span = document.createElement('span');
    span.className = 'status-line';
    var iconSpan = document.createElement('span');
    iconSpan.className = cls;
    iconSpan.textContent = icon;
    span.appendChild(iconSpan);
    span.appendChild(document.createTextNode(' ' + text));
    currentStatusGroup.appendChild(span);
    scrollChat();
}

function addFailureActions() {
    var div = document.createElement('div');
    div.className = 'msg msg-actions';
    var tryAgain = document.createElement('a');
    tryAgain.textContent = 'Try again';
    tryAgain.href = '#';
    tryAgain.onclick = function(e) {
        e.preventDefault();
        if (lastPrompt && !generating) {
            generating = true;
            addUserMessage(lastPrompt);
            startStatusGroup();
            pywebview.api.generate(lastPrompt);
        }
    };
    var editBtn = document.createElement('a');
    editBtn.textContent = 'Edit ScratchScript';
    editBtn.href = '#';
    editBtn.onclick = function(e) {
        e.preventDefault();
        enterEditMode();
    };
    div.appendChild(tryAgain);
    div.appendChild(editBtn);
    messages.appendChild(div);
    scrollChat();
}

/* ── Code rendering ── */
function renderCode(text) {
    if (!text) {
        codeEmpty.style.display = 'block';
        codeDisplay.classList.remove('visible');
        return;
    }
    codeEmpty.style.display = 'none';
    codeDisplay.classList.add('visible');
    var lines = text.split('\n');
    var html = '';
    for (var i = 0; i < lines.length; i++) {
        html += '<div class="code-line"><span class="ln">' + (i+1) + '</span><span class="code">' + highlightLine(lines[i]) + '</span></div>';
    }
    codeDisplay.innerHTML = html;
}

function highlightLine(line) {
    var result = '';
    var i = 0;
    while (i < line.length) {
        /* String literal */
        if (line[i] === '"') {
            var end = line.indexOf('"', i + 1);
            if (end < 0) end = line.length - 1;
            result += '<span class="syn-str">' + escapeHtml(line.substring(i, end + 1)) + '</span>';
            i = end + 1;
            continue;
        }
        /* Color literal #rrggbb */
        if (line[i] === '#') {
            var rest = line.substring(i);
            var cm = rest.match(/^#[0-9a-fA-F]{6}\b/);
            if (cm) {
                result += '<span class="syn-num">' + escapeHtml(cm[0]) + '</span>';
                i += cm[0].length;
                continue;
            }
            /* Comment */
            result += '<span class="syn-cmt">' + escapeHtml(rest) + '</span>';
            break;
        }
        /* // comment */
        if (line[i] === '/' && i + 1 < line.length && line[i+1] === '/') {
            result += '<span class="syn-cmt">' + escapeHtml(line.substring(i)) + '</span>';
            break;
        }
        /* Number */
        if (/[0-9]/.test(line[i]) && (i === 0 || /[\s,(\-+*/=<>]/.test(line[i-1]))) {
            var j = i;
            while (j < line.length && /[0-9.]/.test(line[j])) j++;
            result += '<span class="syn-num">' + escapeHtml(line.substring(i, j)) + '</span>';
            i = j;
            continue;
        }
        /* Word (potential keyword) */
        if (/[a-zA-Z_]/.test(line[i])) {
            var j = i;
            while (j < line.length && /[a-zA-Z_0-9]/.test(line[j])) j++;
            var word = line.substring(i, j);
            if (KEYWORDS.has(word)) {
                result += '<span class="syn-kw">' + escapeHtml(word) + '</span>';
            } else {
                result += escapeHtml(word);
            }
            i = j;
            continue;
        }
        /* Regular character */
        result += escapeHtml(line[i]);
        i++;
    }
    return result;
}

/* ── Edit mode ── */
function enterEditMode() {
    editMode = true;
    codeEmpty.style.display = 'none';
    codeDisplay.classList.remove('visible');
    codeEditor.classList.add('visible');
    codeEditor.value = currentCode;
    previewHeader.classList.add('visible');
    codeEditor.focus();
}

function exitEditMode() {
    editMode = false;
    codeEditor.classList.remove('visible');
    codeDisplay.classList.add('visible');
    previewHeader.classList.remove('visible');
}

editLink.addEventListener('click', function(e) {
    e.preventDefault();
    enterEditMode();
});

compileBtn.addEventListener('click', function() {
    var code = codeEditor.value;
    currentCode = code;
    startStatusGroup();
    addStatusLine('\u25cf', 'status-progress', 'Compiling...');
    pywebview.api.compile_text(code);
});

/* Tab key in editor inserts 2 spaces */
codeEditor.addEventListener('keydown', function(e) {
    if (e.key === 'Tab') {
        e.preventDefault();
        var start = this.selectionStart;
        var end = this.selectionEnd;
        this.value = this.value.substring(0, start) + '  ' + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 2;
    }
});

/* ── Input handling ── */
promptInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitPrompt();
    }
});

promptInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 96) + 'px';
});

function submitPrompt() {
    var text = promptInput.value.trim();
    if (!text || generating) return;
    generating = true;
    lastPrompt = text;
    addUserMessage(text);
    startStatusGroup();
    promptInput.value = '';
    promptInput.style.height = 'auto';
    pywebview.api.generate(text);
}

/* ── Divider drag ── */
var dragging = false;

divider.addEventListener('mousedown', function(e) {
    dragging = true;
    divider.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
});

document.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    var pct = (e.clientX / window.innerWidth) * 100;
    var clamped = Math.max(30, Math.min(70, pct));
    chat.style.flex = '0 0 ' + clamped + '%';
    preview.style.flex = '0 0 ' + (100 - clamped - 0.3) + '%';
});

document.addEventListener('mouseup', function() {
    if (dragging) {
        dragging = false;
        divider.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
});

/* ── Keyboard shortcuts ── */
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        pywebview.api.save_file();
    }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
        e.preventDefault();
        if (currentCode) navigator.clipboard.writeText(currentCode);
    }
    if (e.key === 'Escape' && generating) {
        pywebview.api.cancel();
    }
});

/* ── Utilities ── */
function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function scrollChat() {
    messages.scrollTop = messages.scrollHeight;
}

/* ── Init ── */
window.addEventListener('pywebviewready', function() {
    pywebview.api.init_provider();
});
</script>
</body>
</html>
"""


class Api:
    """Python-to-JavaScript bridge for the ScratchScript GUI."""

    def __init__(self):
        self._window = None
        self._provider = None
        self._provider_name = ""
        self._model_name = ""
        self._sb3_path: Optional[str] = None
        self._sb3_filename: str = "project.sb3"
        self._generating = False
        self._cancel = threading.Event()

    def set_window(self, window):
        self._window = window

    def _emit(self, event: str, data: dict):
        """Push an event to the frontend."""
        js = f"window.handleEvent({json.dumps(event)}, {json.dumps(data)})"
        if self._window:
            self._window.evaluate_js(js)

    # ── Public API (called from JS) ──

    def init_provider(self):
        """Detect an LLM provider on startup."""
        try:
            from .providers import detect_provider

            provider = asyncio.run(detect_provider())
            self._provider = provider
            self._provider_name = type(provider).__name__.replace("Provider", "").lower()
            self._model_name = getattr(provider, "model", "default")
            self._emit(
                "provider",
                {
                    "available": True,
                    "name": self._provider_name,
                    "model": self._model_name,
                },
            )
        except Exception:
            self._provider = None
            self._emit("provider", {"available": False})

    def generate(self, prompt: str):
        """Full pipeline: LLM generate -> compile -> retry -> bundle."""
        if self._generating:
            return
        if not self._provider:
            self._emit(
                "status",
                {
                    "step": "error",
                    "message": (
                        "No LLM provider available. "
                        "Write ScratchScript in the editor and compile it directly."
                    ),
                },
            )
            self._emit("generating_done", {})
            return

        self._generating = True
        self._cancel.clear()
        max_retries = 3

        try:
            from .prompts import get_system_prompt

            system_prompt = get_system_prompt()

            # Generate
            self._emit(
                "status",
                {"step": "generating", "attempt": 1, "max_attempts": max_retries + 1},
            )
            scratchscript = asyncio.run(
                self._provider.generate(prompt, system_prompt)
            )

            if self._cancel.is_set():
                self._emit("status", {"step": "error", "message": "Cancelled"})
                return

            self._emit("status", {"step": "generated", "chars": len(scratchscript)})
            self._emit("code", {"text": scratchscript})

            # Compile with retry loop
            for attempt in range(max_retries + 1):
                if self._cancel.is_set():
                    self._emit("status", {"step": "error", "message": "Cancelled"})
                    return

                self._emit("status", {"step": "compiling"})
                result = self._try_compile(scratchscript)

                if result is not None:
                    self._emit("status", {"step": "bundling"})
                    self._bundle_result(result, prompt)
                    return

                # Compilation failed
                error_text = self._get_compile_errors(scratchscript)

                if attempt < max_retries:
                    self._emit(
                        "status",
                        {
                            "step": "fix_error",
                            "message": f"Compile error: {error_text[:200]}",
                        },
                    )
                    self._emit(
                        "status",
                        {
                            "step": "retrying",
                            "attempt": attempt + 2,
                            "max_attempts": max_retries + 1,
                        },
                    )

                    try:
                        scratchscript = asyncio.run(
                            self._provider.fix(
                                scratchscript, error_text, system_prompt
                            )
                        )
                        if self._cancel.is_set():
                            self._emit(
                                "status", {"step": "error", "message": "Cancelled"}
                            )
                            return
                        self._emit(
                            "status",
                            {"step": "generated", "chars": len(scratchscript)},
                        )
                        self._emit("code", {"text": scratchscript})
                    except Exception as e:
                        self._emit(
                            "status",
                            {"step": "error", "message": f"Fix attempt failed: {e}"},
                        )
                        break
                else:
                    self._emit(
                        "status",
                        {
                            "step": "failed",
                            "message": (
                                f"Failed after {max_retries + 1} attempts: "
                                f"{error_text[:200]}"
                            ),
                        },
                    )
        except Exception as e:
            self._emit("status", {"step": "error", "message": str(e)})
        finally:
            self._generating = False
            self._emit("generating_done", {})

    def compile_text(self, scratchscript: str):
        """Compile user-edited ScratchScript text."""
        result = self._try_compile(scratchscript)
        if result is not None:
            self._bundle_result(result, "project")
            self._emit("compile_result", {"success": True})
        else:
            error_text = self._get_compile_errors(scratchscript)
            self._emit("compile_result", {"success": False, "error": error_text})

    def save_file(self):
        """Open a native save dialog for the compiled .sb3."""
        if not self._sb3_path or not Path(self._sb3_path).exists():
            return
        try:
            import webview

            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=self._sb3_filename,
                file_types=("Scratch Project (*.sb3)",),
            )
            if result:
                dest = result[0] if isinstance(result, (list, tuple)) else result
                shutil.copy2(self._sb3_path, dest)
        except Exception:
            pass

    def cancel(self):
        """Cancel the current generation."""
        self._cancel.set()

    # ── Internal helpers ──

    def _try_compile(self, source: str) -> Optional[dict]:
        """Parse + validate + codegen. Returns project.json dict or None."""
        from .compiler.codegen import generate
        from .compiler.parser import ParseError, parse
        from .compiler.validator import validate

        try:
            project = parse(source)
        except ParseError:
            return None

        validate(project)  # non-fatal — continue anyway

        try:
            return generate(project)
        except Exception:
            return None

    def _get_compile_errors(self, source: str) -> str:
        """Collect error messages from a failed compilation."""
        from .compiler.parser import ParseError, parse
        from .compiler.validator import validate

        errors: list[str] = []
        try:
            project = parse(source)
            result = validate(project)
            if not result.is_valid:
                errors.append(result.format_errors())
        except ParseError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(str(e))

        return "\n".join(errors) if errors else "Unknown compilation error"

    def _bundle_result(self, project_json: dict, name: str):
        """Bundle a compiled project to a temp .sb3 and emit the download event."""
        words = name.lower().split()[:4]
        fname = "-".join(w for w in words if w.isalnum())
        if not fname:
            fname = "project"
        self._sb3_filename = f"{fname}.sb3"

        tmp = tempfile.NamedTemporaryFile(suffix=".sb3", delete=False)
        tmp.close()
        self._sb3_path = tmp.name

        try:
            from .compiler.bundler import bundle

            asyncio.run(bundle(project_json, self._sb3_path))
        except Exception:
            from .compiler.bundler import bundle_sync

            bundle_sync(project_json, self._sb3_path)

        size = Path(self._sb3_path).stat().st_size
        self._emit("status", {"step": "done", "detail": self._sb3_filename})
        self._emit("download", {"filename": self._sb3_filename, "size": size})


def main():
    """Launch the ScratchScript GUI."""
    try:
        import webview
    except ImportError:
        print("pywebview is required for the GUI. Install with:")
        print("  pip install scratchscript[gui]")
        raise SystemExit(1)

    api = Api()
    window = webview.create_window(
        title="ScratchScript",
        html=_HTML,
        js_api=api,
        width=1100,
        height=700,
        min_size=(800, 500),
        resizable=True,
        background_color="#1a1a1e",
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
