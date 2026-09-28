"""Submit FL's standard Save As dialog using observed Windows controls."""

import time
from pathlib import Path

from fl_studio_mcp.bridge_client import TIMEOUT
from scripts.windows_dialog import DialogControls
from scripts.windows_shortcut import trigger_fl_shortcut


def save_controls(children):
    names = [c for c in children if c["class"] == "Edit" and c["id"] == 1001]
    saves = [c for c in children if c["class"] == "Button" and c["id"] == 1]
    formats = [c for c in children if c["class"] == "ComboBox" and "*.flp" in c["text"].lower()]
    if len(names) != 1 or len(saves) != 1 or len(formats) != 1:
        raise ValueError("FL's dialog does not expose the qualified FLP save controls")
    return names[0]["handle"], saves[0]["handle"]


class SaveAsDialog:
    def __init__(self, reader):
        self.ui = DialogControls(reader.pid)
        self.owner = reader.window
        self.handle = None
        self.submitted = False
        self.confirmed = None

    def open(self, validate):
        before = self.ui.windows()
        if any(w["class"] == "#32770" for w in before):
            raise ValueError("FL already has a dialog open; Save As was not dispatched")
        previous = {w["handle"] for w in before}
        trigger = trigger_fl_shortcut((0x11, 0x10, 0x53), "Ctrl+Shift+S", validate)
        if not trigger.hotkey_dispatched:
            raise ValueError(trigger.error)
        deadline = time.monotonic() + TIMEOUT
        while True:
            candidates = [w for w in self.ui.windows() if w["class"] == "#32770"
                          and w["parent"] == self.owner and w["handle"] not in previous]
            if len(candidates) == 1:
                self.handle = candidates[0]["handle"]
                save_controls(self.ui.windows(self.handle))
                return
            if time.monotonic() >= deadline:
                raise ValueError("FL did not expose its Save As dialog after dispatch")
            time.sleep(0.1)

    def submit(self, destination, validate):
        name, button = save_controls(self.ui.windows(self.handle))
        self.ui.set_text(name, str(destination))
        validate()
        self.ui.click(button)
        self.submitted = True

    def handle_confirmation(self, destination, existed_before):
        dialogs = [w for w in self.ui.windows() if w["class"] == "#32770"
                   and w["handle"] != self.handle and w["enabled"]]
        if not dialogs:
            return
        if len(dialogs) != 1 or not existed_before:
            raise ValueError("FL opened an unexpected dialog after Save As; inspect before continuing")
        dialog = dialogs[0]
        if self.confirmed == dialog["handle"]:
            return  # The acknowledged modal can remain visible while FL saves.
        children = self.ui.accessibility(dialog["handle"], "read")
        yes = [c for c in children if c["id"] == "CommandButton_6" and c["handle"]]
        messages = "\n".join(c["name"] for c in children if c["id"] == "ContentText")
        if (dialog["parent"] != self.handle or len(yes) != 1 or self.confirmed or not messages
                or messages.splitlines()[0].casefold()
                != (Path(destination).name + " already exists.").casefold()):
            raise ValueError("FL's confirmation does not identify the requested Save As file")
        self.ui.click(yes[0]["handle"])
        self.confirmed = dialog["handle"]

    def cancel_unsubmitted(self):
        if not self.handle or self.submitted or not self.ui.owns(self.handle):
            return
        buttons = [c for c in self.ui.windows(self.handle)
                   if c["class"] == "Button" and c["id"] == 2]
        if len(buttons) != 1:
            raise ValueError("Could not close the unsubmitted Save As dialog")
        self.ui.click(buttons[0]["handle"])
