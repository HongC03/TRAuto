"""Toggle repeated Z key presses with global keyboard hotkeys.

Pr
ess F8 to start sending Z every 0.1 seconds, X to stop, and Esc to exit.
Change START_KEY below if a different start key is preferred.
"""

import time


import keyboard
import pydirectinput

START_KEY = "a"
STOP_KEY = "x"

EXIT_KEY = "f8"
PRESS_INTERVAL = 0.06
POLL_INTERVAL = 0.005

pydirectinput.PAUSE = 0


def main() -> None:
    repeating = False
    next_press_time = 0.0

    start_was_pressed = False
    stop_was_pressed = False

    print(f"Press {START_KEY.upper()} to start pressing Z every {PRESS_INTERVAL}s.")
    print(f"Press {STOP_KEY.upper()} to stop, or {EXIT_KEY.upper()} to exit.")

    try:
        while True:
            if keyboard.is_pressed(EXIT_KEY):
                break

            stop_is_pressed = keyboard.is_pressed(STOP_KEY)
            start_is_pressed = keyboard.is_pressed(START_KEY)

            # Only react once per physical key press. Stopping takes priority if
            # the start and stop keys happen to be held at the same time.
            if stop_is_pressed and not stop_was_pressed:
                if repeating:
                    print("Stopped pressing Z.")
                repeating = False
            elif start_is_pressed and not start_was_pressed:
                if not repeating:
                    print("Started pressing Z.")
                repeating = True
                next_press_time = time.perf_counter()

            start_was_pressed = start_is_pressed
            stop_was_pressed = stop_is_pressed

            now = time.perf_counter()
            if repeating and now >= next_press_time:
                pydirectinput.press("z")
                next_press_time = now + PRESS_INTERVAL

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        print("Z key repeater exited.")


if __name__ == "__main__":
    main()
