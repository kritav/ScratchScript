"""Flask-based GUI for ScratchScript — serves on localhost, opens in browser."""

from __future__ import annotations

import asyncio
import json
import queue
import socket
import tempfile
import threading
import time
import webbrowser
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

/* -- Chat Panel -- */
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

/* -- Input Area -- */
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

/* -- Divider -- */
#divider {
    flex: 0 0 4px;
    background: transparent;
    cursor: col-resize;
    transition: background 100ms ease-out;
}
#divider:hover, #divider.dragging { background: rgba(74, 158, 255, 0.3); }

/* -- Preview Panel -- */
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
#code-stream {
    display: none;
    padding: 8px 12px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-y: auto;
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: var(--bg-primary);
    z-index: 1;
}
#code-stream.visible { display: block; }
.stream-think { color: var(--text-disabled); font-style: italic; }
.stream-waiting {
    color: var(--text-disabled);
    animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 1; }
}
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

/* -- Status Bar -- */
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

/* -- Scrollbar -- */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }

/* -- Syntax highlighting -- */
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
            <div id="code-stream"></div>
            <textarea id="code-editor" spellcheck="false"></textarea>
        </div>
        <div id="status-bar">Initializing...</div>
    </div>
</div>
<script>
/* -- Constants -- */
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

/* -- State -- */
var generating = false;
var editMode = false;
var currentCode = '';
var streamBuffer = '';
var lastPrompt = '';
var currentStatusGroup = null;

/* -- Element references -- */
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
var codeStream = document.getElementById('code-stream');
var compileBtn = document.getElementById('compile-btn');
var editLink = document.getElementById('edit-link');

/* -- Server-Sent Events -- */
var evtSource = new EventSource('/api/events');
evtSource.addEventListener('status', function(e) { onStatus(JSON.parse(e.data)); });
evtSource.addEventListener('code', function(e) { onCode(JSON.parse(e.data)); });
evtSource.addEventListener('download', function(e) { onDownload(JSON.parse(e.data)); });
evtSource.addEventListener('compile_result', function(e) { onCompileResult(JSON.parse(e.data)); });
evtSource.addEventListener('stream_start', function(e) {
    console.log('[sse] stream_start');
    streamBuffer = '';
    codeEmpty.style.display = 'none';
    codeDisplay.classList.remove('visible');
    codeStream.classList.add('visible');
    codeStream.innerHTML = '<span class="stream-waiting">Waiting for model response\u2026</span>';
});
evtSource.addEventListener('stream', function(e) {
    var data = JSON.parse(e.data);
    streamBuffer += data.token;
    if (streamBuffer.length <= data.token.length) {
        console.log('[sse] first stream token:', data.token.substring(0, 40));
    }
    renderStreamContent(streamBuffer);
});
evtSource.addEventListener('generating_done', function(e) { generating = false; });

/* -- Event handlers -- */
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
        case 'reviewing':
            icon = '\u25cf'; cls = 'status-progress';
            text = 'Reviewing...' + (data.cycle ? ' (cycle ' + data.cycle + ')' : '');
            break;
        case 'review_passed':
            icon = '\u2713'; cls = 'status-success';
            text = 'Review passed';
            break;
        case 'review_revise':
            icon = '\u2717'; cls = 'status-error';
            text = 'Reviewer found ' + (data.summary || 'issues');
            if (data.issues) {
                addStatusLine(icon, cls, text);
                for (var i = 0; i < data.issues.length; i++) {
                    var issue = data.issues[i];
                    addStatusLine(' ', '', '  \u00b7 [' + issue.severity + '] ' + issue.where + ': ' + issue.problem);
                }
                return;
            }
            break;
        case 'revising':
            icon = '\u25cf'; cls = 'status-progress';
            text = 'Revising based on feedback...';
            break;
        case 'revised':
            icon = '\u2713'; cls = 'status-success';
            text = 'Revised (' + (data.chars||'?') + ' chars)';
            break;
        case 'review_error':
            icon = '\u2717'; cls = 'status-error';
            text = 'Review failed: ' + (data.message || 'unknown error');
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
    codeStream.classList.remove('visible');
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
    a.href = '/api/download';
    a.download = filename;
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

/* -- Message rendering -- */
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
            fetch('/api/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({prompt: lastPrompt})
            });
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

/* -- Code rendering -- */
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

function renderStreamContent(text) {
    var html = '';
    var i = 0;
    while (i < text.length) {
        var thinkStart = text.indexOf('<think>', i);
        if (thinkStart === -1) {
            html += escapeHtml(text.substring(i));
            break;
        }
        if (thinkStart > i) {
            html += escapeHtml(text.substring(i, thinkStart));
        }
        var thinkEnd = text.indexOf('</think>', thinkStart);
        if (thinkEnd === -1) {
            html += '<span class="stream-think">' + escapeHtml(text.substring(thinkStart + 7)) + '</span>';
            break;
        }
        html += '<span class="stream-think">' + escapeHtml(text.substring(thinkStart + 7, thinkEnd)) + '</span>';
        i = thinkEnd + 8;
    }
    codeStream.innerHTML = html;
    codeStream.scrollTop = codeStream.scrollHeight;
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

/* -- Edit mode -- */
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
    fetch('/api/compile', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({code: code})
    });
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

/* -- Input handling -- */
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
    fetch('/api/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt: text})
    });
}

/* -- Divider drag -- */
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

/* -- Keyboard shortcuts -- */
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        var a = document.createElement('a');
        a.href = '/api/download';
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
        e.preventDefault();
        if (currentCode) navigator.clipboard.writeText(currentCode);
    }
    if (e.key === 'Escape' && generating) {
        fetch('/api/cancel', {method: 'POST'});
    }
});

/* -- Utilities -- */
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

/* -- Init -- */
fetch('/api/provider').then(function(r) { return r.json(); }).then(onProvider);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class _State:
    """Mutable state shared between Flask routes and background threads."""

    def __init__(self):
        self.provider = None
        self.provider_name: str = ""
        self.model_name: str = ""
        self.sb3_path: Optional[str] = None
        self.sb3_filename: str = "project.sb3"
        self.generating: bool = False
        self.cancel = threading.Event()
        self._queues: list[queue.Queue] = []
        self._lock = threading.Lock()

    def emit(self, event: str, data: dict):
        """Push an SSE event to every connected client."""
        msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        with self._lock:
            for q in list(self._queues):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=4096)
        with self._lock:
            self._queues.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self._queues:
                self._queues.remove(q)

    def provider_info(self) -> dict:
        if self.provider:
            return {
                "available": True,
                "name": self.provider_name,
                "model": self.model_name,
            }
        return {"available": False}


# ---------------------------------------------------------------------------
# Pipeline helpers (run in background threads, push results via SSE)
# ---------------------------------------------------------------------------

def _detect_provider(state: _State):
    try:
        from .providers import detect_provider

        provider = asyncio.run(detect_provider())
        state.provider = provider
        state.provider_name = (
            type(provider).__name__.replace("Provider", "").lower()
        )
        state.model_name = getattr(provider, "model", "default")
    except Exception as e:
        print(f"[provider] No provider detected: {type(e).__name__}: {e}")
        state.provider = None


def _try_compile(source: str) -> Optional[dict]:
    from .compiler.codegen import generate
    from .compiler.parser import ParseError, parse
    from .compiler.validator import validate

    try:
        project = parse(source)
    except ParseError:
        return None
    validate(project)
    try:
        return generate(project)
    except Exception:
        return None


def _get_compile_errors(source: str) -> str:
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


def _bundle_result(state: _State, project_json: dict, name: str):
    words = name.lower().split()[:4]
    fname = "-".join(w for w in words if w.isalnum())
    if not fname:
        fname = "project"
    state.sb3_filename = f"{fname}.sb3"

    tmp = tempfile.NamedTemporaryFile(suffix=".sb3", delete=False)
    tmp.close()
    state.sb3_path = tmp.name

    try:
        from .compiler.bundler import bundle

        asyncio.run(bundle(project_json, state.sb3_path))
    except Exception:
        from .compiler.bundler import bundle_sync

        bundle_sync(project_json, state.sb3_path)

    size = Path(state.sb3_path).stat().st_size
    state.emit("status", {"step": "done", "detail": state.sb3_filename})
    state.emit("download", {"filename": state.sb3_filename, "size": size})


def _run_generate(state: _State, prompt: str):
    if state.generating:
        return
    if not state.provider:
        state.emit(
            "status",
            {
                "step": "error",
                "message": (
                    "No LLM provider available. "
                    "Write ScratchScript in the editor and compile it directly."
                ),
            },
        )
        state.emit("generating_done", {})
        return

    state.generating = True
    state.cancel.clear()
    max_retries = 3
    max_review_cycles = 2

    try:
        from .prompts import get_system_prompt
        from .reviewer import Reviewer, build_revision_prompt

        system_prompt = get_system_prompt()

        # Set up token streaming for providers that support it
        gen_kwargs = {}
        try:
            from .providers.ollama import OllamaProvider

            if isinstance(state.provider, OllamaProvider):
                gen_kwargs["on_token"] = lambda tok: state.emit(
                    "stream", {"token": tok}
                )
        except ImportError:
            pass

        # --- Step 1: Generate ---
        state.emit(
            "status",
            {"step": "generating", "attempt": 1, "max_attempts": max_retries + 1},
        )
        if gen_kwargs:
            state.emit("stream_start", {})
        scratchscript = asyncio.run(
            state.provider.generate(prompt, system_prompt, **gen_kwargs)
        )

        if state.cancel.is_set():
            state.emit("status", {"step": "error", "message": "Cancelled"})
            return

        state.emit("status", {"step": "generated", "chars": len(scratchscript)})
        state.emit("code", {"text": scratchscript})

        # --- Step 2: Review loop ---
        reviewer = Reviewer(state.provider)
        for cycle in range(max_review_cycles):
            if state.cancel.is_set():
                state.emit("status", {"step": "error", "message": "Cancelled"})
                return

            state.emit("status", {"step": "reviewing", "cycle": cycle + 1})
            try:
                review_result = asyncio.run(
                    reviewer.review(prompt, scratchscript)
                )
            except Exception as e:
                state.emit(
                    "status",
                    {"step": "review_error", "message": str(e)},
                )
                break

            if review_result.verdict == "PASS":
                state.emit("status", {"step": "review_passed"})
                break

            # Emit issues for display
            issues_data = [
                {
                    "severity": iss.severity,
                    "where": iss.where,
                    "problem": iss.problem,
                }
                for iss in review_result.issues
            ]
            state.emit(
                "status",
                {
                    "step": "review_revise",
                    "summary": review_result.summary(),
                    "issues": issues_data,
                },
            )

            # Revise
            state.emit("status", {"step": "revising"})
            revision_prompt = build_revision_prompt(
                prompt, scratchscript, review_result
            )
            try:
                if gen_kwargs:
                    state.emit("stream_start", {})
                scratchscript = asyncio.run(
                    state.provider.generate(
                        revision_prompt, system_prompt, **gen_kwargs
                    )
                )
            except Exception as e:
                state.emit(
                    "status",
                    {"step": "error", "message": f"Revision failed: {e}"},
                )
                break

            if state.cancel.is_set():
                state.emit("status", {"step": "error", "message": "Cancelled"})
                return

            state.emit(
                "status", {"step": "revised", "chars": len(scratchscript)}
            )
            state.emit("code", {"text": scratchscript})

        # --- Step 3: Compile with retry loop ---
        for attempt in range(max_retries + 1):
            if state.cancel.is_set():
                state.emit("status", {"step": "error", "message": "Cancelled"})
                return

            state.emit("status", {"step": "compiling"})
            result = _try_compile(scratchscript)

            if result is not None:
                state.emit("status", {"step": "bundling"})
                _bundle_result(state, result, prompt)
                return

            error_text = _get_compile_errors(scratchscript)

            if attempt < max_retries:
                state.emit(
                    "status",
                    {
                        "step": "fix_error",
                        "message": f"Compile error: {error_text[:200]}",
                    },
                )
                state.emit(
                    "status",
                    {
                        "step": "retrying",
                        "attempt": attempt + 2,
                        "max_attempts": max_retries + 1,
                    },
                )
                try:
                    if gen_kwargs:
                        state.emit("stream_start", {})
                    scratchscript = asyncio.run(
                        state.provider.fix(
                            scratchscript, error_text, system_prompt, **gen_kwargs
                        )
                    )
                    if state.cancel.is_set():
                        state.emit(
                            "status", {"step": "error", "message": "Cancelled"}
                        )
                        return
                    state.emit(
                        "status",
                        {"step": "generated", "chars": len(scratchscript)},
                    )
                    state.emit("code", {"text": scratchscript})
                except Exception as e:
                    state.emit(
                        "status",
                        {"step": "error", "message": f"Fix attempt failed: {e}"},
                    )
                    break
            else:
                state.emit(
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
        import traceback
        traceback.print_exc()
        msg = str(e) or repr(e)
        state.emit("status", {"step": "error", "message": f"{type(e).__name__}: {msg}"})
    finally:
        state.generating = False
        state.emit("generating_done", {})


def _run_compile(state: _State, scratchscript: str):
    result = _try_compile(scratchscript)
    if result is not None:
        _bundle_result(state, result, "project")
        state.emit("compile_result", {"success": True})
    else:
        error_text = _get_compile_errors(scratchscript)
        state.emit("compile_result", {"success": False, "error": error_text})


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Launch the ScratchScript GUI (Flask server + browser)."""
    try:
        from flask import Flask, Response, jsonify, request, send_file
    except ImportError:
        print("Flask is required for the GUI. Install with:")
        print("  pip install scratchscript[gui]")
        raise SystemExit(1)

    import logging

    state = _State()
    _detect_provider(state)

    app = Flask(__name__)

    # Quiet request logging
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # ── Routes ──

    @app.route("/")
    def index():
        return _HTML

    @app.route("/api/provider")
    def api_provider():
        return jsonify(state.provider_info())

    @app.route("/api/generate", methods=["POST"])
    def api_generate():
        data = request.get_json(force=True)
        prompt = data.get("prompt", "")
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        threading.Thread(
            target=_run_generate, args=(state, prompt), daemon=True
        ).start()
        return jsonify({"ok": True})

    @app.route("/api/compile", methods=["POST"])
    def api_compile():
        data = request.get_json(force=True)
        code = data.get("code", "")
        if not code:
            return jsonify({"error": "No code provided"}), 400
        threading.Thread(
            target=_run_compile, args=(state, code), daemon=True
        ).start()
        return jsonify({"ok": True})

    @app.route("/api/download")
    def api_download():
        if state.sb3_path and Path(state.sb3_path).exists():
            return send_file(
                state.sb3_path,
                as_attachment=True,
                download_name=state.sb3_filename,
            )
        return "", 404

    @app.route("/api/cancel", methods=["POST"])
    def api_cancel():
        state.cancel.set()
        return jsonify({"ok": True})

    @app.route("/api/events")
    def api_events():
        def stream():
            q = state.subscribe()
            try:
                while True:
                    try:
                        msg = q.get(timeout=30)
                        yield msg
                    except queue.Empty:
                        yield ": keepalive\n\n"
            except GeneratorExit:
                pass
            finally:
                state.unsubscribe(q)

        return Response(
            stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # ── Start ──

    port = _find_free_port()
    print(f"ScratchScript running at http://localhost:{port}")

    def _open_browser():
        time.sleep(0.8)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=port, threaded=True)


if __name__ == "__main__":
    main()
