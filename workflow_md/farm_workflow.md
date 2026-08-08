# Farm Workflow Test Plan

User ID: 503

This document divides the farm automation into three sections so each part can
be tested independently. The sections are ordered, but a test may start at the
first image of any section when the game is manually placed in that state.

## Common Test Rules

- Each image step is checked immediately, then polled every `0.5` seconds.
- Each image step has a `15`-second timeout and up to two total attempts.
- Normal farm steps do not call `clearPrompt()`.
- If a required farm step times out after its retries, call `clearPrompt()`
  repeatedly until no blocker is handled. Then run the recovery sequence:
  `waiting_room.png` -> `yes.png` -> `special_event.png`, and resume the Conan
  loop.
- The explicit waits between farm actions are five seconds after each normal
  crop collection click, three seconds after `farm/field.png` before
  `farm/target_field.png`, and one second between each consecutive purchase
  sequence action. Recorded Shift-click positions use the configured click
  interval.
- `farm_cross.png` may be replaced by the general `cross.png` wherever a farm
  cross is required.

## Section 1: Enter Farm and Manage Crops

### Normal flow

```text
farm/farm.png
-> yes.png
-> farm/enter_my_farm.png
-> farm/crops_management.png
```

After crop management opens:

1. Check `farm/crops_management_failure.png` before each collection attempt.
2. Make up to two normal collection attempts. Each attempt is:
   `farm/crops_management_button_1.png` -> wait five seconds -> wait for either
   `farm/crops_management_okButton.png` or
   `farm/crops_management_failure.png`.
3. If the failure image appears after collection starts, click the general
   `okButton.png` directly. If either image in a normal attempt cannot be found after its retry, stop
   crop collection and close crop management with `farm_cross.png` or
   `cross.png`, then continue to field placement.
4. If `farm/crops_management_failure.png` appears before an attempt, stop the
   normal collection loop and click the general `okButton.png` directly; do
   not use the five-second normal-branch wait.
5. Close crop management with `farm_cross.png` or `cross.png` when it opened.

### Crop-management failure cases

- If `farm/crops_management.png` cannot be found after retries, treat crop
  management as skipped. Do not click the first farm cross; continue directly
  to `farm/farm_shop.png` in Section 2.
- If a collection action or crop confirmation fails after retries, skip crop
  collection and continue to field placement. Because crop management opened,
  still attempt its closing cross before entering the shop.
- A crop failure-image branch uses the general `okButton.png`; a normal branch
  uses `farm/crops_management_okButton.png`.

### Section 1 success condition

The game is ready at `farm/farm_shop.png`, or crop management was skipped and
`farm/farm_shop.png` is the next detectable image.

## Section 2: Place Fields and Execute Recorded Positions

### Required flow

```text
farm/farm_shop.png
-> farm/field.png
-> wait 3 seconds
-> farm/target_field.png
-> load farm_click_positions.json
-> hold Shift and click every recorded position once
```

The `farm/target_field.png` image must be detected and clicked before
`farm_click_positions.json` is loaded or any recorded position is clicked. If
the target-field step fails, do not execute the JSON positions; retry the
step, then enter the timeout recovery described in Common Test Rules.

### Section 2 success condition

The target field has been clicked and every valid recorded coordinate has been
clicked once while Shift is held. The game should then expose
`farm/farm_cart.png` for Section 3.

## Section 3: Confirm Purchase and Return to Conan

### Required flow

```text
farm/farm_cart.png
-> farm/farm_cart_okButton.png
-> buy.png
-> okButton.png
-> okButton.png
-> farm_cross.png or cross.png
-> waiting_room.png
-> yes.png
-> special_event.png
-> continue Conan loop
```

`farm/farm_cart_okButton.png` is a farm-cart-specific confirmation image and
must be added at:

```text
scr/farm/farm_cart_okButton.png
```

Do not replace this step with the general `okButton.png`. The general
`okButton.png` is used for the two purchase confirmations after `buy.png`.

### Section 3 success condition

The purchase is confirmed, the farm is closed, `special_event.png` is
confirmed, and normal Conan automation resumes.

If any required Section 3 image is missing or blocked after its retries, use
the post-timeout blocker cleanup and return sequence from Common Test Rules.
