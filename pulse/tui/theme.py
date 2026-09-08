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
    background: {BG};
    color: {TEXT_MUTED};
    padding: 0 1;
}}

#cockpit-body {{
    height: 1fr;
    width: 100%;
}}

AppHeader .brand {{
    color: {TEXT_MUTED};
}}

AppHeader .run-status {{
    color: {LIME};
    text-align: right;
    width: 1fr;
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

LogStream .stream-title {{
    color: {LIME};
    text-style: bold;
}}

LogStream .stream-meta {{
    color: {TEXT_MUTED};
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

PromptModal {{
    align: center middle;
}}

PromptModal > Vertical {{
    width: 70;
    max-width: 90%;
    height: auto;
    max-height: 80%;
    background: {BG_PANEL};
    border: solid {LIME};
    padding: 1 2;
}}

PromptModal .modal-title {{
    color: {LIME};
    text-style: bold;
    margin-bottom: 1;
}}

PromptModal .modal-prompt {{
    color: {TEXT};
    margin-bottom: 1;
}}

PromptModal OptionList {{
    height: auto;
    max-height: 14;
    background: {BG};
    border: solid {BORDER};
}}

PromptModal Input {{
    margin-top: 1;
}}
"""
