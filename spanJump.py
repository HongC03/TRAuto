import time

import keyboard
import pydirectinput

SPAM_INTERVAL = 0.13  # seconds

pydirectinput.PAUSE = 0


def log(message, start_time):
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    print(f"[{elapsed_ms:8.2f} ms] {message}")


def main():
    start_time = time.perf_counter()
    next_press_time = 0.0
    was_holding_z = False

    print("Hold Z to spam Z every 0.25 seconds.")
    print("Press F11 to exit.")

    try:
        while not keyboard.is_pressed("f11"):
            now = time.perf_counter()
            holding_z = keyboard.is_pressed("z")

            if holding_z and not was_holding_z:
                log("Z hold detected", start_time)
                next_press_time = now  # Press immediately on first hold.

            if holding_z and now >= next_press_time:
                log("Send Z", start_time)
                pydirectinput.press("z")
                next_press_time = now + SPAM_INTERVAL

            if not holding_z and was_holding_z:
                log("Z released", start_time)

            was_holding_z = holding_z
            time.sleep(0.01)  # Prevent high CPU usage.

    finally:
        print("Program ended.")


if __name__ == "__main__":
    main()