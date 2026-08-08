# TRautoRace

An open-source Windows automation tool for Tales Runner. It uses screen-image
recognition and simulated keyboard/mouse input for racing, Conan tasks, farm
workflows, CAPTCHA recognition, and optional automatic restart.

## Features

- Speed Puzzle and Super Tunnel automation.
- Lobby and room management.
- CAPTCHA preprocessing with `ddddocr`.
- Configurable key bindings and automatic restart.
- Scheduled farm workflows with recorded Shift-click positions.
- Telegram status, control, screenshots, and alarm-window commands.

## Telegram Conan automation

Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`. The script loads these values automatically; explicitly set
environment variables take precedence.

Start the automation with:

```text
python event_script/afk_conan.py
```

Commands from the configured chat:

```text
/conanHelp
/conanStats
/conanScreenshot
/conanPause
/conanResume
/conanStop
/alarmWindow [interval_seconds] [HH:MM] [message]
/alarmWindow status
/alarmWindow stop
```

`/conanScreenshot` sends the current screen. `/conanStats` reports session and
all-time statistics. `/conanPause`, `/conanResume`, and `/conanStop` control the
automation process.

`/alarmWindow` starts a recurring alarm. The interval is in seconds, the
optional start time is HKT (`HH:MM`), and the remaining text is the alarm
message. For example:

```text
/alarmWindow 600 09:00 "Take a break"
```

Use `/alarmWindow status` to check it, or `/alarmWindow stop` to stop it.
`off` and `cancel` are also accepted as stop aliases. Commands are
case-insensitive and may include a bot mention, such as `/conanStats@YourBot`.

Only the configured `TELEGRAM_CHAT_ID` is accepted. Telegram polling is
disabled when credentials are missing. Statistics and the next scheduled farm
time are persisted in `conan_stats.json`.

## Farm workflow

Farm automation is enabled by default and runs on the configured schedule. When
the schedule is due, the workflow waits for the current Conan match to finish,
then enters the farm, collects crops, places fields using recorded Shift-click
positions, buys items, confirms the room, and returns to Conan.

The next farm timestamp is persisted before waiting. If the process restarts
after that time, the overdue farm workflow runs first after the game is ready.
Set `FARM_WORKFLOW_ENABLED = False` in `event_script/afk_conan.py` to disable
scheduled farming.

To run a live farm-only test:

```text
python event_script/afk_conan.py --test-farm-workflow
```

This performs real image clicks, so Tales Runner must already be open in the
expected state. To record farm positions, run:

```text
python event_script/record_farm_positions.py
```

Move the pointer and press `F8` to record positions; press `F9` to save or
`Esc` to cancel. To record a diagnostic video, run
`event_script/record_farm_video.py` and press `F9` to save or `F4` to cancel.

## Important notes

- Windows is required.
- The program may bring the Tales Runner window to the foreground and switch
  keyboard/mouse focus. Keep this in mind when using the computer interactively.
- Run as administrator so keyboard and mouse input can reach the game.
- Do not use unsupported `1024x768` resolution, and disable Windows display
  scaling for the game if image recognition is inaccurate.
- Automatic restart requires the Tales Runner directory in the Windows `Path`
  environment variable and may require changing the User Account Control
  setting.
- Automation can lead to account enforcement. Use it at your own risk.

## Development

The project targets Python 3.10. Install the dependencies used by the scripts,
including `pyautogui`, `pydirectinput`, `pygetwindow`, `pillow`, `opencv-python`,
`numpy`, `ddddocr`, `keyboard`, and `global-hotkeys`.

The project is licensed under GNU GPL v3.0.
