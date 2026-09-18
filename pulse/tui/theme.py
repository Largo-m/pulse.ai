from __future__ import annotations

BG = "#000000"
BG_PANEL = "#121212"
LIME = "#A2D729"
LIME_MUTED = "#4A5F1A"
TEXT = "#E0E0E0"
TEXT_MUTED = "#888888"
ACCENT_YELLOW = "#D4AF37"
BORDER = "#333333"

COCKPIT_CSS = f"""
Screen {{
    background: {BG};
    color: {TEXT};
}}

AppHeader {{
    dock: top;
    height: 3;
    layout: vertical;
    background: {BG};
    color: {TEXT_MUTED};
    padding: 0 1;
}}

#cockpit-body {{
    height: 1fr;
    width: 100%;
    layout: horizontal;
}}

AppHeader #header-top,
AppHeader #header-sub {{
    width: 100%;
    height: 1;
}}

AppHeader .brand {{
    color: {TEXT_MUTED};
    width: auto;
}}

AppHeader .run-status {{
    color: {LIME};
    text-align: right;
    width: 1fr;
    overflow: hidden;
}}

AppHeader .pipeline-badge {{
    background: {LIME_MUTED};
    color: {LIME};
    padding: 0 1;
    text-style: bold;
}}

AppHeader .workflow-label {{
    color: {TEXT_MUTED};
    padding: 0 1;
    width: 1fr;
}}

PhaseSidebar {{
    width: 32%;
    min-width: 28;
    height: 100%;
    background: {BG};
    border-right: solid {BORDER};
    padding: 1 1;
    overflow-y: auto;
}}

PhaseSidebar #phase-content {{
    width: 100%;
    height: auto;
}}

LogStream {{
    width: 1fr;
    height: 100%;
    background: {BG};
    padding: 0 1;
    layout: vertical;
}}

LogStream #stream-header {{
    height: 1;
}}

LogStream #stream-meta {{
    height: 1;
    margin-bottom: 1;
}}

LogStream #stream-body {{
    height: 1fr;
    scrollbar-color: {LIME_MUTED};
}}

LogStream #stream-content {{
    width: 100%;
    height: auto;
}}

LogStream #prompt-slot {{
    width: 100%;
    height: auto;
    max-height: 70%;
}}

LogStream .stream-title {{
    color: {LIME};
    text-style: bold;
}}

LogStream .stream-meta {{
    color: {TEXT_MUTED};
}}

ArtifactPane {{
    width: 42%;
    min-width: 36;
    height: 100%;
    background: {BG};
    border-left: solid {BORDER};
    padding: 1 0 0 0;
    layout: vertical;
}}

ArtifactPane.-collapsed {{
    width: 8;
    min-width: 8;
    padding: 1 0;
}}

#cockpit-body.artifacts-open PhaseSidebar {{
    width: 22%;
    min-width: 20;
}}

ArtifactPane:focus {{
    border-left: solid {LIME};
}}

ArtifactPane #artifact-open {{
    display: none;
    width: 100%;
    height: 1fr;
    color: {LIME};
    text-align: center;
    content-align: center top;
    padding: 1 0;
}}

ArtifactPane.-collapsed #artifact-open {{
    display: block;
}}

ArtifactPane #artifact-title-row {{
    height: 1;
    width: 100%;
    padding: 0 1;
}}

ArtifactPane #artifact-header {{
    width: 1fr;
    height: 1;
    color: {LIME};
    text-style: bold;
}}

ArtifactPane #artifact-close {{
    width: 3;
    height: 1;
    content-align: right middle;
    color: {TEXT_MUTED};
}}

ArtifactPane #artifact-close:hover {{
    color: {LIME};
}}

ArtifactPane #artifact-meta {{
    height: 1;
    padding: 0 1;
    color: {TEXT_MUTED};
    margin-bottom: 1;
}}

ArtifactPane #artifact-tabs {{
    height: 1;
    width: 100%;
    padding: 0 1;
    overflow-x: auto;
}}

ArtifactPane .artifact-tab {{
    width: auto;
    height: 1;
    color: {TEXT_MUTED};
}}

ArtifactPane .artifact-tab.-active {{
    color: {LIME};
    text-style: bold;
}}

ArtifactPane #artifact-body {{
    height: 1fr;
    scrollbar-color: {LIME_MUTED};
}}

ArtifactPane Markdown {{
    height: auto;
    margin: 0;
    padding: 0 1 1 1;
    background: {BG};
}}

AppFooter {{
    dock: bottom;
    height: 1;
    background: {BG};
    color: {TEXT_MUTED};
    padding: 0 1;
}}

AppFooter .key {{
    color: {LIME};
}}

HomeScreen {{
    background: {BG};
    align: center middle;
}}

HomeScreen #home-content {{
    width: auto;
    height: auto;
    max-width: 80%;
    align: center middle;
}}

HomeScreen .home-brand {{
    width: 100%;
    color: {LIME};
    text-style: bold;
    text-align: center;
    margin-bottom: 1;
}}

HomeScreen .home-sub {{
    width: 100%;
    color: {TEXT_MUTED};
    text-align: center;
    margin-bottom: 2;
}}

HomeScreen OptionList {{
    width: 60;
    max-width: 100%;
    height: auto;
    max-height: 16;
    background: {BG_PANEL};
    border: solid {BORDER};
    color: {TEXT};
}}

HomeScreen OptionList:focus {{
    border: solid {LIME};
}}

HomeScreen .home-hint {{
    width: 100%;
    color: {TEXT_MUTED};
    margin-top: 1;
    text-align: center;
}}

HomeScreen #workflow-prompt {{
    width: 60;
    max-width: 100%;
    margin-top: 1;
}}

HistoryListScreen {{
    background: {BG};
    align: center middle;
}}

HistoryListScreen #history-content {{
    width: 80%;
    max-width: 90;
    height: auto;
    align: center middle;
}}

HistoryListScreen .history-title {{
    width: 100%;
    color: {LIME};
    text-style: bold;
    text-align: center;
    margin-bottom: 1;
}}

HistoryListScreen .history-hint {{
    width: 100%;
    color: {TEXT_MUTED};
    text-align: center;
    margin-bottom: 1;
}}

HistoryListScreen #history-search {{
    width: 100%;
    margin-bottom: 1;
}}

HistoryListScreen OptionList {{
    width: 100%;
    height: 16;
    max-height: 18;
    background: {BG_PANEL};
    border: solid {BORDER};
    color: {TEXT};
}}

HistoryListScreen OptionList:focus {{
    border: solid {LIME};
}}

HistoryListScreen .history-empty {{
    width: 100%;
    color: {TEXT_MUTED};
    text-align: center;
    margin-top: 1;
}}

PromptDock {{
    width: 100%;
    height: 100%;
    layout: vertical;
    background: {BG_PANEL};
    border-top: solid {LIME};
    padding: 0 1;
}}

PromptDock .prompt-title {{
    color: {LIME};
    text-style: bold;
    height: 1;
}}

PromptDock .prompt-text {{
    color: {TEXT};
    height: auto;
}}

PromptDock .prompt-hint {{
    color: {TEXT_MUTED};
    height: 1;
}}

PromptDock OptionList {{
    width: 100%;
    color: {TEXT};
    background: {BG_PANEL};
    border: none;
    padding: 0 1;
}}

PromptDock OptionList:focus {{
    border: none;
}}

PromptDock Input {{
    margin: 0;
}}

PromptDock #prompt-actions {{
    height: 3;
    width: 100%;
}}
"""
