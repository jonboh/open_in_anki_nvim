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


def _config():
    return mw.addonManager.getConfig(__name__) or {}


def _editor():
    return _config().get("editor") or "nvim"


def _addon_socket():
    s = _config().get("nvim_socket", "")
    if s:
        return os.path.expanduser(s)
    state_dir = os.path.expanduser("~/.local/share/anki-nvim")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, "nvim.sock")


def _try_remote_open(note_id, card_id, open_type, query, socket):
    """
    Ask an already-running Neovim (listening on *socket*) to open the note
    in a new tab via the anki Lua plugin. Returns True on success.
    """
    lua_cmd = (
        f"require([[anki]])._open_note([[{note_id}]], [[{card_id}]], "
        f"[[{open_type}]], [[{query}]])"
    )
    try:
        result = subprocess.run(
            [_editor(), "--server", socket, "--remote-send",
             f"<C-\\><C-n>:tabnew<CR>:lua {lua_cmd}<CR>"],
            timeout=3,
            capture_output=True,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _spawn_nvim_window(note_id, card_id, open_type, query, socket):
    """
    Spawn a new terminal window running Neovim with --listen so future
    open requests are sent to the same session.
    """
    config = _config()
    terminal = config.get("terminal") or None

    if not terminal:
        terminal = figure_out_terminal()
        if terminal is None:
            tooltip(
                "Terminal not specified in config and could not find any "
                "sensible terminal to run. Please specify a terminal in config"
            )
            return False
        tooltip(f"Terminal not specified in config. Found '{terminal}' to use")

    if str.find(terminal, " ") > 0:
        tooltip("Space in terminal name — please quote or fix the config")
        return False

    editor = _editor()
    nvim_args = [
        editor,
        "--listen", socket,
        f"+lua require([[anki]])._open_note([[{note_id}]], [[{card_id}]], [[{open_type}]], [[{query}]])",
    ]

    terminal_bin = terminal.split()[0]

    if terminal_bin in ("kitty", "alacritty", "foot", "st", "urxvt", "rxvt",
                        "xterm", "uxterm", "termite", "terminology", "rio"):
        cmd = [terminal, "--"] + nvim_args
    elif terminal_bin == "wezterm":
        cmd = [terminal, "start", "--"] + nvim_args
    elif terminal_bin in ("gnome-terminal", "xfce4-terminal", "mate-terminal",
                          "terminator", "tilix", "terminix", "lxterminal",
                          "qterminal", "lilyterm"):
        cmd = [terminal, "--"] + nvim_args
    elif terminal_bin in ("konsole", "guake", "tilda"):
        cmd = [terminal, "-e"] + nvim_args
    else:
        cmd = [terminal, "-e"] + nvim_args

    try:
        subprocess.Popen(
            cmd,
            stdin=None,
            stdout=None,
            stderr=None,
            start_new_session=True,
        )
        return True
    except (FileNotFoundError, OSError):
        return False


def open_link(note_id, open_type, query, card_id):
    socket = _addon_socket()

    # 1. Try to reuse an existing Neovim session.
    if os.path.exists(socket) and _try_remote_open(note_id, card_id, open_type, query, socket):
        tooltip("Opened note in Neovim")
        return

    # Stale socket — remove so the editor can bind cleanly.
    if os.path.exists(socket):
        try:
            os.remove(socket)
        except OSError:
            pass

    # 2. Spawn a new dedicated window.
    if _spawn_nvim_window(note_id, card_id, open_type, query, socket):
        tooltip("Opened note in Neovim")


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
