# Tuya Lock Diagnostics & Behavior

This document tracks the behavior and diagnostics for battery-powered Tuya Smart Locks (specifically `cerraduraCalle`) to avoid making incorrect assumptions about connectivity or hardware failures.

## 1. Zombie / Sleep Mode Behavior

- **Battery-powered Tuya Locks aggressively disconnect from Wi-Fi** to save power. They are NOT offline due to router issues or bad batteries.
- **Wake Trigger:** The lock ONLY connects to Wi-Fi when physically interacted with (doorbell press, keypad touch, fingerprint).
- **Vigilia (Awake Window):** Once connected, the lock stays awake for a very short window (e.g., exactly 9 seconds as seen in syslog).
- **Remote Unlock Constraint:** Remote unlock commands MUST be sent while the lock is awake. Sending an unlock command while it is asleep will result in Tuya Cloud silently dropping it or returning an offline error.

## 2. Doorbell Event Distinguishability

Events from `event.cerradura_calle_doorbell` can be easily distinguished between a **Real Press** and a **Reload/Restart Artifact**:

- **Real Doorbell Press:**
  - Fires multiple events in extremely quick succession (bouncing). For example, 5 to 6 events within 1 second.
  - The `state` value (which is a timestamp) and the `changed_time` attribute **exactly match** the actual current time (`last_changed`).
- **Integration Reload / HA Restart:**
  - Fires only one event upon boot.
  - The `state` value and `changed_time` reflect a timestamp in the **PAST** (the last time the Tuya cloud registered a press), whereas `last_changed` is the current time of the reload.

## 3. Remote Unlock Configuration (Force API)

- The Tuya consumer app can successfully open the lock when awake.
- If `door_open API` configuration fails in Home Assistant, it is highly likely the specific lock model requires the `door_operate API` or a specific DPCode command.
- **Action Plan:** Testing different `Force unlock mechanism` configurations natively supported by `xtend_tuya` (like `door_operate API`) is the correct, intended way to resolve this.
- **Rule:** Do NOT hack the source code to bypass legitimate capability checks unless it is confirmed that the device falsely reports its capabilities (e.g., claiming it doesn't support remote unlock when it actually does). Any such fix should be treated as a formal patch/PR to the repository.

## 4. Active Debugging Hooks

- `xt_tuya_iot_manager.py` currently contains injected `LOGGER.error` statements inside `call_door_open` and `call_door_operate` to explicitly print the raw JSON response from the Tuya Developer API to the main Home Assistant logs (`Settings -> System -> Logs`).
- This allows seeing exactly why Tuya Cloud rejects the unlock command (e.g., wrong ticket, offline, or unsupported API) during future tests.
