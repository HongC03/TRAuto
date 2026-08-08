"""Find a unique container by anchor image, then act on a button inside it.

  The script performs:

  1. Uses GameSupervisor to ensure the game is ready and handle OCR.
  2. Finds image 1 globally as the unique container anchor.
  3. Expands the anchor coordinates into a larger container region.
  4. Searches for image 2 only inside that container.
  5. Clicks image 2 or presses a configured keyboard key.

  Configure these values:

  ANCHOR_IMAGE_NAME = "unique_container_part.png"
  TARGET_IMAGE_NAME = "confirm_button.png"

Run from the project root with:
    python -m event_script.anchored_container_action

Image 1 (ANCHOR_IMAGE_NAME) should be the part that distinguishes the desired
container. CONTAINER_PADDING expands its detected box to cover the complete
container. Image 2 (TARGET_IMAGE_NAME) is searched only inside that region.
"""

import time

import pyautogui as gui
import pydirectinput as key

from game_supervisor import BASE_DIR, GameSupervisor
from utils import pressButton, waitForImage


# Put both images in scr/ and replace these names.
ANCHOR_IMAGE_NAME = "replace_with_unique_anchor.png"  # Image 1
TARGET_IMAGE_NAME = "replace_with_confirm_button.png"  # Image 2

ANCHOR_CONFIDENCE = 0.89
TARGET_CONFIDENCE = 0.89
ANCHOR_TIMEOUT = 0.5
POLL_INTERVAL = 0.1
LOOP_INTERVAL = 0.5
ACTION_COOLDOWN = 1

# Pixels by which the container extends beyond the anchor image:
# (left, top, right, bottom)
#
# Example: if the anchor is a label near the container's left side and the
# confirm button is 250 px to its right, increase the right padding.
CONTAINER_PADDING = (20, 30, 300, 30)

ACTION = "click"  # "click" or "key"
KEYBOARD_KEY = None  # Example: "enter" when ACTION == "key"


def image_path(image_name):
    return BASE_DIR / "scr" / image_name


def validate_configuration():
    for name in (ANCHOR_IMAGE_NAME, TARGET_IMAGE_NAME):
        path = image_path(name)
        if not path.is_file():
            raise FileNotFoundError(
                f"Required image does not exist: {path}. "
                "Add it to scr/ and update the configured image name."
            )

    if len(CONTAINER_PADDING) != 4 or any(
        value < 0 for value in CONTAINER_PADDING
    ):
        raise ValueError(
            "CONTAINER_PADDING must contain four non-negative values"
        )
    if ACTION not in {"click", "key"}:
        raise ValueError("ACTION must be 'click' or 'key'")
    if ACTION == "key" and not KEYBOARD_KEY:
        raise ValueError("KEYBOARD_KEY is required when ACTION is 'key'")


def container_region(anchor_position):
    """Expand an anchor box into a clipped screen region for its container."""
    anchor_left, anchor_top, anchor_width, anchor_height = anchor_position
    pad_left, pad_top, pad_right, pad_bottom = CONTAINER_PADDING

    raw_left = anchor_left - pad_left
    raw_top = anchor_top - pad_top
    raw_right = anchor_left + anchor_width + pad_right
    raw_bottom = anchor_top + anchor_height + pad_bottom

    screen_width, screen_height = gui.size()
    left = max(0, int(raw_left))
    top = max(0, int(raw_top))
    right = min(screen_width, int(raw_right))
    bottom = min(screen_height, int(raw_bottom))

    if right <= left or bottom <= top:
        raise ValueError("Calculated container region is outside the screen")
    return left, top, right - left, bottom - top


def trigger_target_in_container(region):
    """Find image 2 only in the selected container and trigger its action."""
    target_position = gui.locateOnScreen(
        str(image_path(TARGET_IMAGE_NAME)),
        confidence=TARGET_CONFIDENCE,
        region=region,
    )
    if target_position is None:
        return False

    if ACTION == "click":
        pressButton(target_position)
    else:
        key.press(KEYBOARD_KEY)

    print(
        f"* Triggered {TARGET_IMAGE_NAME} inside container region {region} *"
    )
    return True


def run_task_step():
    """Find image 1, derive its container, then look for image 2 inside it."""
    anchor_position = waitForImage(
        image_path(ANCHOR_IMAGE_NAME),
        timeout=ANCHOR_TIMEOUT,
        interval=POLL_INTERVAL,
        confidence=ANCHOR_CONFIDENCE,
    )
    if anchor_position is None:
        return False

    region = container_region(anchor_position)
    return trigger_target_in_container(region)


def main():
    validate_configuration()
    supervisor = GameSupervisor.from_config()

    while True:
        game_state = supervisor.ensure_ready()
        if game_state != "ready":
            print(f"* Container task paused while game state is: {game_state} *")
            time.sleep(LOOP_INTERVAL)
            continue

        if run_task_step():
            time.sleep(ACTION_COOLDOWN)
        else:
            time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(f"** {error} **")
    except KeyboardInterrupt:
        print("\n* Container task stopped *")
