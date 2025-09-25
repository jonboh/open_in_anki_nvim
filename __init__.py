import os
import shutil
import subprocess

import aqt
from anki.hooks import addHook
from aqt import gui_hooks, mw, qt
from aqt.utils import tooltip


def figure_out_terminal():
    terminal = os.path.expandvars("$TERM")

    if terminal is not None and len(terminal) != 0:
        return terminal

    terminals = [
        "kitty",
        "alacritty",
        "hyper",
        "wezterm",
        "st",
        "x-terminal-emulator",
        "mate-terminal",
        "gnome-terminal",
        "terminator",
        "xfce4-terminal",
        "urxvt",
        "rxvt",
        "termit",
        "Eterm",
        "aterm",
        "uxterm",
        "xterm",
        "roxterm",
        "termite",
        "lxterminal",
        "terminology",
        "qterminal",
        "lilyterm",
        "tilix",
        "terminix",
        "konsole",
        "guake",
        "tilda",
        "rio",
    ]

    for it in terminals:
        if shutil.which(it) is not None:
            return it

    return None


def open_link(note_id, open_type, query, card_id):
    config = mw.addonManager.getConfig(__name__)
    terminal = config["terminal"]
    editor = config["editor"]
    run_last_tooltip = True

    if terminal is None or len(terminal) == 0:
        terminal = figure_out_terminal()
        if terminal is None:
            tooltip(
                "Terminal not specified in config and could not find any sensible terminal to run. Please specify a terminal in config"
            )
            return
        tooltip(
            f"Terminal not specified in config. Found a sensible terminal '{terminal}' to use"
        )
        run_last_tooltip = False
    if editor is None:
        tooltip(f"Editor not specified in config. Using nvim as default")
        run_last_tooltip = False

    if len(terminal) == 0 or str.find(terminal, " ") > 0:
        tooltip("Space in terminal")
        return

    subprocess.Popen(
        [
            terminal,
            editor,
            f"+lua require([[anki]])._open_note([[{note_id}]], [[{card_id}]], [[{open_type}]], [[{query}]])",
        ],
        stdin=None,
        stdout=None,
        stderr=None,
    )
    run_last_tooltip and tooltip("Opened note in Neovim")


def open_link_browser():
    browser = aqt.dialogs._dialogs["Browser"][1]
    query = browser.form.searchEdit.lineEdit().text()
    note_id = None
    card_id = None
    if browser is not None:
        note_id = browser.card.nid
        card_id = browser.card.id
    if note_id:
        open_link(note_id, "browser", query, card_id)
    else:
        tooltip("No note is selected.")


def open_link_reviewer():
    if mw.state == "review" and mw.reviewer.card:
        open_link(mw.reviewer.card.nid, "reviewer", "", 0)
    else:
        tooltip("No note is being reviewed.")


def addEmacsLinkActionToMenu(menu, f):
    menu.addSeparator()
    a = menu.addAction("Open Note in Neovim")
    a.setShortcut(qt.QKeySequence("Ctrl+O"))
    a.triggered.connect(f)


def insert_reviewer_more_action(self, m):
    if mw.state != "review":
        return
    a = m.addAction("Browse Creation of This Card")
    a.setShortcut(aqt.qt.QKeySequence("c"))
    a.triggered.connect(lambda _, s=mw.reviewer: qt.browse_this_card(s))
    a = m.addAction("Browse Creation of Last Card")
    a.triggered.connect(lambda _, s=mw.reviewer: qt.browse_last_card(s))


def setupMenuBrowser(self):
    menu = self.form.menu_Notes
    addEmacsLinkActionToMenu(menu, open_link_browser)


def setupMenuReviewer(self, menu):
    if mw.state != "review":
        return
    addEmacsLinkActionToMenu(menu, open_link_reviewer)


def fix_reviewer_shortcut(state, shortcuts):
    if state == "review":
        shortcuts.append(("Ctrl+O", open_link_reviewer))


addHook("browser.setupMenus", setupMenuBrowser)
addHook("Reviewer.contextMenuEvent", setupMenuReviewer)
gui_hooks.state_shortcuts_will_change.append(fix_reviewer_shortcut)
