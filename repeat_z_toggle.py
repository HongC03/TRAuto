"""Control repeated Z key presses with global keyboard hotkeys.

Press A to start, X to stop, or F8 to toggle sending Z every 0.06 seconds.
Press Ctrl+C in the terminal to exit.
"""

import time

import keyboard
import pydirectinput

START_KEY = "a"
STOP_KEY = "x"
TRIGGER_KEY = "f8"
PRESS_INTERVAL = 0.06
POLL_INTERVAL = 0.005

pydirectinput.PAUSE = 0


def main() -> None:
    repeating = False
    next_press_time = 0.0
    start_was_pressed = False
    stop_was_pressed = False
    trigger_was_pressed = False

    print(
        f"Press {START_KEY.upper()} to start pressing Z "
        f"every {PRESS_INTERVAL}s."
    )
    print(f"Press {STOP_KEY.upper()} to stop, or {TRIGGER_KEY.upper()} to toggle.")
    print("Press Ctrl+C in the terminal to exit.")

    try:
        while True:
            stop_is_pressed = keyboard.is_pressed(STOP_KEY)
            start_is_pressed = keyboard.is_pressed(START_KEY)
            trigger_is_pressed = keyboard.is_pressed(TRIGGER_KEY)

            # React once per physical key press. Stop takes priority, then start.
            if stop_is_pressed and not stop_was_pressed:
                if repeating:
                    print("Stopped pressing Z.")
                repeating = False
            elif start_is_pressed and not start_was_pressed:
                if not repeating:
                    print("Started pressing Z.")
                repeating = True
                next_press_time = time.perf_counter()
            elif trigger_is_pressed and not trigger_was_pressed:
                repeating = not repeating
                if repeating:
                    print("Started pressing Z.")
                    next_press_time = time.perf_counter()
                else:
                    print("Stopped pressing Z.")

            start_was_pressed = start_is_pressed
            stop_was_pressed = stop_is_pressed
            trigger_was_pressed = trigger_is_pressed

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
