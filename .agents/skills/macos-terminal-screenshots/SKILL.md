---
name: macos-terminal-screenshots
description: Capture real native macOS screenshots of terminal applications and TUIs. Use when Codex needs pixel-faithful visual review of a CLI/TUI on macOS, especially for design, UX, layout, typography, spacing, color, or usability work where ANSI-to-HTML approximations are not good enough. Prefer kitty when the user works in kitty, launch emulated sessions full-screen by default, use tmux as the control plane, diagnose screenshot permission blockers, and build repeatable native screenshot harnesses around terminal apps.
---

# macOS Terminal Screenshots

## Goal

Produce real screenshots of a terminal window as macOS renders it.

Prefer this path when the user cares about visual fidelity. Do not treat ANSI capture plus HTML re-rendering as authoritative for design review.

Default to full-screen emulated sessions. Full-screen capture reduces layout ambiguity, makes screenshots easier to compare, and matches how users actually judge a polished terminal UI.

## Choose the capture path

Use the native path for truth.

Prefer kitty if the user uses kitty:

1. Launch a dedicated kitty window in full-screen mode.
2. Give that kitty instance an explicit remote-control socket.
3. Run the app inside `tmux`.
4. Capture the entire display with `/usr/sbin/screencapture`.

Use this because kitty multi-instance window targeting is brittle under macOS accessibility, while a full-screen kitty window plus whole-screen capture is reliable and still fully native. Use the explicit socket when you need reliable automation.

Use the per-window path when working with Terminal.app:

1. Launch the app in a real terminal emulator.
2. Drive it from the outside, usually with `tmux`.
3. Query the real window bounds with AppleScript.
4. Call `/usr/sbin/screencapture` on that rectangle.

Use the HTML path only as a fallback for rough inspection:

1. Capture pane text with `tmux capture-pane -e`.
2. Convert ANSI to HTML.
3. Screenshot the browser rendering.

Treat that fallback as an approximation. It preserves content and many colors, but not font rasterization, exact spacing, terminal chrome, overlays, or emulator-specific rendering.

## Use tmux as the control plane

Use `tmux` to make the terminal app externally controllable without depending on the current shell session.

Why this works well:

- Reproduce sessions deterministically.
- Send keys and commands without fragile GUI automation.
- Keep the app alive while capturing.
- Support both Rich-style CLIs and full-screen TUIs.

Treat this as more than a launch primitive. After the app is visible, you can continue controlling it by sending keystrokes into the same `tmux` pane. This is useful when `ccc` opens in a pager and you need to scroll down to inspect how a later block looks, confirm spacing deeper in the transcript, or compare the UI before and after a pager movement.

Minimal pattern:

```sh
SESSION='app-shot'
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -x 120 -y 40 \
  "cd /path/to/project && your-command-here; exec zsh -i"
```

Generalized post-launch control pattern:

```sh
# Wait until the app is on screen, then drive it through tmux.
tmux send-keys -t "$SESSION":0.0 d
tmux send-keys -t "$SESSION":0.0 C-d
tmux send-keys -t "$SESSION":0.0 j
tmux send-keys -t "$SESSION":0.0 q
```

For `ccc` specifically, this makes it possible to launch a session, let the pager come up naturally, then send one or more navigation keys only if needed. For example, sending `d` can move the pager down so you can inspect a specific later section before capturing the screenshot.

Attach it in `Terminal.app`:

```applescript
tell application "Terminal"
  activate
  do script "tmux attach -t app-shot"
  delay 1
end tell
```

Launch it in full-screen kitty:

```sh
SESSION='app-shot'
SOCKET='unix:/tmp/app-shot-kitty.sock'
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -x 180 -y 55 \
  "cd /path/to/project && your-command-here; exec zsh -i"

open -na /Applications/kitty.app --args \
  --listen-on "$SOCKET" \
  -o allow_remote_control=yes \
  --start-as=fullscreen \
  --title "App Shot" \
  sh -lc "tmux attach -t $SESSION"
```

Then capture the whole display:

```sh
/usr/sbin/screencapture -x /tmp/app-shot.png
```

Example with conditional pager movement:

```sh
SESSION='app-shot'
tmux new-session -d -s "$SESSION" -x 180 -y 55 \
  "cd /path/to/project && uv run ccc -1 --color always"

sleep 6
tmux send-keys -t "$SESSION":0.0 d
sleep 1
/usr/sbin/screencapture -x /tmp/app-shot-after-scroll.png
```

Prefer `tmux send-keys` over GUI-level key injection when possible. It is simpler, more deterministic, and targets the actual pane running the app.

If you need to control that kitty instance programmatically, prefer the explicit socket:

```sh
kitty @ --to "$SOCKET" ls
kitty @ --to "$SOCKET" send-text --match title:'App Shot' 'q'
```

## Probe permissions before building a harness

Fail fast with tiny checks before attempting the full workflow.

Test Apple Events:

```sh
osascript -e 'tell application "Terminal" to activate'
```

Test window introspection:

```sh
osascript -e 'tell application "Terminal" to get bounds of front window'
```

Test whole-screen capture:

```sh
rm -f /tmp/test-fullscreen.png
/usr/sbin/screencapture -x /tmp/test-fullscreen.png
ls -l /tmp/test-fullscreen.png
```

Test region capture:

```sh
rm -f /tmp/test-rect.png
/usr/sbin/screencapture -x -R0,0,300,300 /tmp/test-rect.png
ls -l /tmp/test-rect.png
```

Only proceed to the full flow after both screenshot probes succeed.

If using kitty, also confirm that launching a new kitty window works before building the full harness:

```sh
open -na /Applications/kitty.app --args --start-as=fullscreen --title "Kitty Probe" sh -lc 'printf probe\n; exec zsh -i'
```

If you need kitty remote control from automation, test the socket path directly:

```sh
rm -f /tmp/codex-kitty-rc.sock
open -na /Applications/kitty.app --args \
  --listen-on unix:/tmp/codex-kitty-rc.sock \
  -o allow_remote_control=yes \
  --title "Kitty RC Probe" \
  sh -lc 'printf rc-probe-started\n; exec zsh -i'
sleep 5
kitty @ --to unix:/tmp/codex-kitty-rc.sock ls
```

## Diagnose errors by their exact strings

Interpret these native errors literally:

- `could not create image from display`
  Meaning: screen capture is blocked, usually by macOS Screen Recording permissions.
- `could not create image from rect`
  Meaning: screen capture is blocked or the requested rectangle is unusable. Test full-screen capture first to separate permission issues from geometry issues.

In practice on macOS, Screen Recording permissions are app-specific. The app invoking `screencapture` may need access, and the target terminal app may also need it.

Common required approvals:

- The current terminal emulator running the agent, such as `kitty`
- `Terminal.app` if it is the window being launched and captured

Treat Automation and Screen Recording as separate concerns:

- AppleScript succeeding does not prove screenshot permission is granted.
- Screenshot permission being granted does not prove AppleScript/UI scripting is granted.

Interpret this kitty-specific error literally:

- `Error: open /dev/tty: device not configured`
  Meaning: `kitty @ ...` was run without a usable TTY. Stop trying to control kitty from a plain non-interactive shell.
- `Error: i/o timeout`
  Meaning: kitty saw a terminal but not the right control path. Do not spend time on shell-mode tweaks here; switch to `kitty @ --to unix:/path/to/socket ...`.

## Capture the real terminal window

For Terminal.app, query the actual window bounds, then capture that exact rectangle.

```sh
BOUNDS=$(osascript <<'APPLESCRIPT'
tell application "Terminal"
  activate
  set b to bounds of front window
  return (item 1 of b as text) & "," & (item 2 of b as text) & "," & (item 3 of b as text) & "," & (item 4 of b as text)
end tell
APPLESCRIPT
)

IFS=',' read -r X1 Y1 X2 Y2 <<< "$BOUNDS"
W=$((X2 - X1))
H=$((Y2 - Y1))
/usr/sbin/screencapture -x -R"${X1},${Y1},${W},${H}" /tmp/terminal-shot.png
```

If you need stable composition, set the window bounds first:

```applescript
tell application "Terminal"
  activate
  set bounds of front window to {40, 60, 1500, 1050}
end tell
```

For kitty, prefer full-screen launch plus full-screen capture instead of per-window geometry. Kitty window discovery through `System Events` can be unreliable when multiple kitty instances or spaces are involved, even though the screenshot itself is still native and correct.

For kitty automation, keep the rule simple: if direct `kitty @ ...` control fails with TTY or timeout errors, stop escalating shell tweaks and use an explicit socket via `--listen-on` and `kitty @ --to ...`.

## Expect real-world contamination

A native screenshot captures what a human would see, including distractions.

Watch for:

- Floating overlays such as TeamViewer panels
- Notification banners
- Wrong frontmost window
- Unexpected prompt output after the app finished
- macOS moving a full-screen kitty window into a different space than the one you expected

If the screenshot contains visual noise, that is not a pipeline bug. It is part of the real rendered environment. Clean the environment and capture again.

## Keep the mindset

Teach the agent to reason about fidelity, not just produce files:

- Prefer native screenshots for design and UX decisions.
- Use `tmux` for control, not for visual truth.
- Prefer kitty plus full-screen whole-display capture when the user uses kitty.
- Prefer explicit kitty remote-control sockets over shell-mode tweaks.
- Prefer Terminal.app plus rectangle capture when you need precise per-window geometry.
- Start with the smallest failing probe.
- Read native error strings exactly.
- Separate permission failures from geometry failures.
- Separate real screenshot truth from HTML approximation.
