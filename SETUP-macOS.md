# macOS setup (preview)

Fruity Commander's Mac support is a **preview**: it has not yet run on a real Mac.
These steps install it, check it, and collect the results the developer needs.
The [Windows guide](SETUP.md) remains the reference for the fully qualified setup.

## What to expect on a Mac

Works through MCP in this preview:

- Reading and controlling the project, channels, patterns, mixer, tempo and
  playback, and changing plugin parameters.
- Creating editable note patterns, reading them back and revising note ranges.
  This needs **one click in FL per FL launch** (see [Notes](#first-note-edit)).
- Adding named instruments and mixer effects from FL's **Add** menu.

Not available on Mac yet (these tools report "no macOS route"):

- Native Automation Clips, placing patterns or audio in the Playlist, importing
  samples, loading `.fst` presets or instrument state, and owned Splice downloads.
- Saving through Fruity Commander. Save in FL yourself with **Cmd+S**.

Those Windows features call FL Studio internals that were mapped for one
Windows FL build. A Mac version needs the results described in
[Send the results](#send-the-results) before it can be built.

## Requirements

- **FL Studio 2026**, version **26.1.3 build 5336 or newer**. Older versions are
  refused by the connection check.
- **Claude** desktop app (Code tab) or **Codex**, signed in.
- Command Line Tools for `git`: run `xcode-select --install` once if `git` is missing.
- **uv** to install Python: `curl -LsSf https://astral.sh/uv/install.sh | sh`,
  then open a new Terminal window.

## 1. Get the code

The GitHub repository is private; the owner must invite your GitHub account first.

```bash
git clone https://github.com/ossianravn/fruity-commander-2000.git ~/fruity-commander-2000
```

Keep this folder in place. The plugin runs Python from it.

## 2. Install the runtime

Use Python 3.12: the MIDI library ships a ready-built macOS version for it, so no
compiler is needed. (Python 3.13 would try to compile it.)

```bash
cd ~/fruity-commander-2000
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip check --python .venv/bin/python
```

## 3. Create the MIDI connection (IAC bus)

1. Open **Audio MIDI Setup** (Applications › Utilities).
2. Choose **Window › Show MIDI Studio**, then double-click **IAC Driver**.
3. Tick **Device is online**.
4. Under **Ports**, click **+**, rename the new port to `Fruity Commander`, then **Apply**.

One port is enough. FL uses it both for input and output.

## 4. Connect FL Studio

Start FL Studio once, so it creates its settings folder, then install the controller:

```bash
cd ~/fruity-commander-2000
.venv/bin/python -B -m scripts.controller_deployment
```

It uses `~/Documents/Image-Line/FL Studio`. If you moved FL's user-data folder,
add `--user-data-dir "/full/path/to/that/folder"`.

In FL Studio, open **Options › MIDI settings**:

1. In the **Input** list, select `IAC Driver Fruity Commander`, enable it, set
   **Controller type** to **Universal Bridge**, and note its **Port** number.
2. In the **Output** list, select the same IAC port and give it the **same Port number**.
3. Open **View › Script output**, choose the Fruity Commander tab and click
   **Reload script**.

Quit FL normally once (FL › Quit) so it remembers these settings, then reopen it.

## 5. Allow automation

Fruity Commander presses FL's run-script shortcut and uses FL's Add menu. macOS
must allow that for the app that runs it:

1. Open **System Settings › Privacy & Security › Accessibility**.
2. Turn on **Claude** (or **Codex**), and **Terminal** for the setup check.
3. When macOS asks whether the app may control **System Events**, click **Allow**.
4. Quit and reopen Claude/Codex after changing these settings.

## 6. Check the setup

With FL running:

```bash
cd ~/fruity-commander-2000
.venv/bin/python -B -m scripts.check_setup --midi-port 'Fruity Commander' --output ~/Desktop/fruity-commander-check.json
```

`Ready` means the connection, controller and owned tools are in place. It also lists the
features that are Windows-only for now. Fix any listed issue and run it again.

## 7. Install the plugin in Claude

```bash
cd ~/fruity-commander-2000
.venv/bin/python -B -m scripts.package_plugin --archive --midi-port 'Fruity Commander'
```

In Claude, open **Customize › Plugins › Upload local plugin** and select
`~/fruity-commander-2000/.local/plugins/fruity-commander-2000.zip`. In Finder,
press **Cmd+Shift+.** to show the hidden `.local` folder. Then open the **Code**
tab and start a new **Local** session. `/mcp` shows the Fruity Commander connection.

For Codex, use the same bundle folder (`.local/plugins/fruity-commander-2000`) as
described in [the Windows guide](SETUP.md#activate-or-update-the-codex-plugin),
replacing Windows paths with this Mac checkout.

## First note edit

Ask, for example: *"Use Fruity Commander to make a 4-bar editable melody on the
first instrument."* The first time after FL starts, the assistant asks you to do
one thing in FL:

> In the open Piano Roll, choose **Scripts › Postfader › Postfader Apply**.

This changes no notes. Tell the assistant you did it; it then continues. Later
edits run it automatically until FL is restarted. If you run a different Piano
Roll script in between, choose Postfader Apply again before the next edit.

Good things to try: load an instrument (*"add FLEX"*), write notes, revise a
bar, change a plugin knob, play the pattern, then save with **Cmd+S** yourself.

## Send the results

With FL open, run the read-only probe. It changes nothing and presses no keys:

```bash
cd ~/fruity-commander-2000
.venv/bin/python -B -m scripts.mac_probe --output ~/Desktop/fruity-commander-mac-probe.json
```

It records macOS/FL versions, chip type, FL's code-signing settings, menu names,
whether FL's window exposes the project file, MIDI ports, and script and Splice
folders. Your home folder is shown as `~`. Window titles can contain your project
name. Read it, then send both JSON files from the Desktop to the developer with
notes about what worked, what failed, and any error text.

## Troubleshooting

- **"Could not reach the Universal Bridge"**: FL is running; the IAC port is
  online; FL's input and output use the same port number and Universal Bridge;
  then **Reload script** in Script output.
- **Permission or "not allowed to send keystrokes" errors**: repeat step 5 for the
  app named in the error, then quit and reopen it.
- **The Postfader Apply request repeats** after you ran it: FL's script could not
  report back. Send the probe file and the exact message.
- **"no macOS route is implemented yet"**: that feature is Windows-only for now.
- After `git pull`, rerun step 4's controller command, reload the script in FL,
  rerun step 7, and upload the new ZIP.
