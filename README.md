# PwnPet CLI — User Guide

Command-line tool for interacting with the **PwnPet** badge via BLE (Bluetooth Low Energy) from a Linux, macOS, or Windows computer.

PwnPet badges are virtual Tamagotchi-style pets that live on real hardware. Beyond creature care (feeding, petting, playing), the firmware includes a set of built-in **CTF (Capture the Flag) challenges**: missions the player solves by interacting with the badge to obtain flags in the format `PWNPET{xxxxxxxxxxxx}`.

> **About the challenges:** this guide explains how to **use the CLI**, not how to solve the challenges. The firmware follows a *"no hints"* philosophy: official hints are delivered by the device itself (command `missions --hint`), and the characteristics that contain flags are not documented by name. Here we only describe the general mechanisms, just enough for you to know where to explore.

---

## Table of Contents

1. [Requirements & Installation](#requirements)
2. [Hardware variant: unknownSecurityConference-2026](#hardware-variant-unknownsecurityconference-2026)
3. [Command structure & quick start](#command-structure)
4. [Interactive session commands](#interactive-session-commands)
5. [Creature emotional states](#creature-emotional-states)
6. [Physical badge controls](#physical-badge-controls)
7. [CTF challenges (overview)](#ctf-challenges-overview)
8. [Relationship between firmware and CLI](#relationship-between-firmware-and-cli)
9. [CLI internal architecture (Python)](#cli-internal-architecture-python)
10. [References: exit codes, BLE characteristics, and debugging](#references)

---

## Requirements

- Python 3.10 or higher
- Bluetooth BLE 4.0+ adapter (built into most laptops since 2014)
- Physical PwnPet badge powered on and in range

### Installation

```sh
# From the repository root (PWNPet_CLI/):
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

pip install -r pwnpet_cli/requirements.txt
chmod +x pwnpet                  # Linux / macOS
```

The `pwnpet` script must be invoked **from the repository root** (`PWNPet_CLI/`). Running it directly by name (without a path) will fail unless you configure your shell first (see options below).

Verify the installation by running from the repository root:

```sh
./pwnpet --version
./pwnpet --help
```

### Reducing verbosity — running `pwnpet` from any directory

Choose one of the following options so you don't have to type `./pwnpet` every time:

```sh
# Option A — add to PATH (append this line to ~/.bashrc or ~/.zshrc):
export PATH="$PATH:/path/to/PWNPet_CLI"

# Option B — symbolic link in ~/.local/bin (run from the repository root):
ln -s "$(pwd)/pwnpet" ~/.local/bin/pwnpet

# Option C — shell alias (append to ~/.bashrc or ~/.zshrc):
alias pwnpet='/path/to/PWNPet_CLI/pwnpet'
```

### Solving BLE permission issues

**Linux:** add your user to the `bluetooth` group:
```sh
sudo usermod -aG bluetooth $USER
# log out and back in
```

**macOS:** the first run triggers a Bluetooth permission prompt. If you denied it, enable it in System Settings → Privacy & Security → Bluetooth.

**Windows:** make sure Bluetooth is enabled and apps are allowed to use it in Settings → Privacy → Bluetooth.

---

## Command Structure

```
pwnpet [-v] [-d | --debug] [--target <addr|name>] <subcommand>
```

If no subcommand is specified, an **interactive session** opens directly (default mode).

### Quick start flow

#### 1. Scan for nearby badges

```sh
pwnpet scan
```

Shows all visible PwnPet badges with their name, MAC address, species, and current emotional state:

```
Name            Address            Species            State
PwnPet_1A2B     AA:BB:CC:DD:EE:1A  0x0002 (Pwn Cat)   temeroso
PwnPet_3C4D     AA:BB:CC:DD:EE:2B  0x0003 (Pwn Llama) curioso
```

Useful options:

| Option | Description |
|--------|-------------|
| `--timeout <s>` | Scan duration in seconds (default: 5) |
| `--all` | Show all BLE devices, not just PwnPet |
| `--raw` | Include a column with manufacturer data in hex |

#### 2. Save the target (recommended)

```sh
pwnpet target set AA:BB:CC:DD:EE:1A
# or by local name:
pwnpet target set PwnPet_1A2B
```

Once saved, all subsequent commands use that badge without needing `--target`.

```sh
pwnpet target show    # view the saved target
pwnpet target clear   # forget the target
```

#### 3. Open an interactive session

```sh
pwnpet session
# or simply (default mode):
pwnpet
```

The session keeps the BLE connection open throughout the interaction, eliminating the reconnection latency (~5–10 s per command) that running subcommands one by one would incur. The connection is closed only when you type `exit`, `quit`, or press `Ctrl+D`.

Upon connecting, the current badge state is displayed automatically:

```
Connected to AA:BB:CC:DD:EE:1A.
Type 'help' for available commands, 'exit' or Ctrl+D to disconnect.

  species:           0x0002 (Pwn Cat)
  name:              Pwn Llama
  happiness:         450 / 1000
  hungry:            310 / 1000
  health:            800 / 1000
  state:             temeroso
  xp:                0
  sensor_value:      2920
  all_missions_done: false

(pwnpet)
```

You can override the saved target for a single session:

```sh
pwnpet session --target AA:BB:CC:DD:EE:FF
```

---

## Interactive Session Commands

All commands are typed at the `(pwnpet)` prompt. Type `help` at any time to see the full list.

### Creature care

| Command | Description |
|---------|-------------|
| `feed` | Feed the badge. Sends a fixed portion of 50 units. Raises `hungry` and `happiness`. Be careful not to overfeed. |
| `pet` | Pet the badge. Raises happiness and grants a small amount of XP. |
| `play <hex>` | Play with the badge by writing a 32-bit magic value and reading the response. Certain values produce special reactions and are part of the challenges. |
| `rename <name>` | Change the creature's name (maximum 16 UTF-8 bytes). |

Examples:
```
(pwnpet) feed
ok
(pwnpet) pet
ok
(pwnpet) rename MyLlama
name: MyLlama
```

### Status & information

| Command | Description |
|---------|-------------|
| `status` | Displays all public badge fields (species, name, happiness, hunger, health, state, XP, sensor, missions). |
| `read dream_log` | Reads the creature's dream log (UTF-8). |
| `missions` | Lists all available missions with their status (completed / pending). |
| `missions --hint <id>` | Displays the **official firmware hint** for the specified mission. |
| `flag <id>` | Retrieves the flag for an already-completed mission. |

Examples:
```
(pwnpet) missions
Missions (Pwn Llama):
  [ ] mission 1
  [X] mission 2
  [ ] mission 4

(pwnpet) missions --hint 1
Hint for mission 1: "<firmware hint>"

(pwnpet) flag 2
PWNPET{xxxxxxxxxxxx}
```

> Mission numbering is **not necessarily contiguous**: it depends on the `HAS_*` flags of your variant. Always list with `missions` to see which ones actually exist on your badge.

### Passkey — unlocking protected content

Under certain conditions, the creature displays a 3-digit numeric code on the OLED screen for a few seconds. That code is the *passkey*. Sending it with the `passkey` command unlocks certain protected memory content for the active connection.

```
(pwnpet) passkey 163
ok
```

The passkey is unique per badge (derived from the chip UID). If you miss it, trigger the condition again and watch the screen.

### Friendship system

The badge can discover and register nearby badges via BLE. Detection happens passively by listening to proximity advertisings; the firmware **requests consent via the physical buttons** before adding a new friend (which is why it requires `HAS_BUTTONS=1`).

| Command | Description |
|---------|-------------|
| `friendship count` | Number of registered friends. |
| `friendship list` | List of known badges with address, name, and whether they are blocked. |
| `friendship remove <AA:BB:CC:DD:EE:FF>` | Removes a badge from the friend list. |
| `friendship block <AA:BB:CC:DD:EE:FF>` | Blocks a badge to prevent future prompts. |
| `friendship proximity` | Shows whether proximity detection is active (`on` / `off`). |
| `friendship proximity on` / `off` | Enables or disables proximity detection. |

The CLI supports two versions of the internal protocol: the *legacy* 12-byte format and the extended 20-byte format (name of up to 11 UTF-8 characters + flags). Detection is automatic.

### Direct BLE characteristic access

For advanced users who want to read or write any characteristic by public name or by short UUID (format `0xNNNN`):

```
read <name|0xNNNN>
write <name|0xNNNN> <hex>
```

Examples:
```
(pwnpet) read happiness
450
(pwnpet) read name
Pwn Llama
(pwnpet) write 0xC001 32
ok
```

> The CLI **only names the public characteristics** (visible game state and interaction inputs). The characteristics that contain flags have no public name by design; they are reachable only by their raw UUID (`read 0xNNNN`) and return null data if their access conditions are not met. This is an intentional part of the challenges.

### Help and exit

| Command | Description |
|---------|-------------|
| `help` | Displays the full list of available commands. |
| `exit` / `quit` | Disconnects from the badge and ends the session. |
| `Ctrl+D` | Equivalent to `exit`. |
| `Ctrl+C` | Cancels the current command without closing the session. |

---

## Creature Emotional States

The creature has a **state** (byte read from the `state` characteristic, `0xFE05`) that changes based on its XP, hunger, and health. The CLI translates it to a name with color:

| Byte | State | Terminal color | Meaning |
|------|-------|----------------|---------|
| 0 | `temeroso` | Yellow | Initial state. The creature is scared and distrustful. |
| 1 | `curioso` | Green | Reached by accumulating enough XP. Starting to open up. |
| 2 | `leal` | Blue | Full trust. |
| 3 | `paranoia` | Bright red | Active distrust. |
| 4 | `muerto (salud)` | — | Died from lack of health. |
| 5 | `muerto (gordito)` | — | Died from overfeeding. |
| 6 | `hambriento` | Bright magenta | Critically low energy. |

States `4` and `5` are the two "death" states; the CLI detects them to enable the `arise` command (see below). As you gain XP by caring for and interacting with the creature, it progresses toward states of higher trust, which in turn may unlock additional content.

### Hunger indicator (`hungry`)

The `hungry` field ranges from 0 to 1000. **The extremes are dangerous**: both critical hunger and overfeeding can kill the creature.

| Range | Color | Meaning |
|-------|-------|---------|
| 0 – 299 | Red | Too hungry — risk of death |
| 300 – 599 | Green | Normal range |
| 600 – 749 | Yellow | Mild overfeeding |
| 750 – 899 | Bright yellow | Moderate overfeeding |
| 900 – 1000 | Bright red | Critical overfeeding — risk of death |

---

---

## Physical Badge Controls

The reference badge (DojoCon 2026 Panama) has the following physical controls:

| Control | PCB label | Function |
|---------|-----------|----------|
| **Slide switch** | SW2 | Main power switch. Move to ON to power on. |
| **Tact button** | SW1 (RST) | System reset. Restarts the device. |
| **Tact button** | SW3 (BOOT) | Bootloader. Hold while connecting USB to enter ISP mode for flashing firmware (developers only). |
| **Directional buttons** | UP/DOWN/LEFT/RIGHT | 4 active-low buttons. Used for creature care, statistics display, the friendship system, and pattern-based challenges. |

### Directional button interactions

#### Single presses

| Button | Action |
|--------|--------|
| `UP` | **Pets** the creature. Equivalent to the CLI `pet` command: raises happiness and grants XP. Shows the `"Petted! +5xp"` overlay on the OLED. |
| `DOWN` | **Feeds** the creature. Equivalent to the CLI `feed` command: sends a fixed portion, raises `hungry` and `happiness`. Shows `"Fed! +25food"`. Be careful not to overfeed. |
| `LEFT` | Shows the `HAP` (happiness) and `HUN` (hunger) stats on the OLED for 4 seconds. |
| `RIGHT` | Shows the `HP` (health) and `XP` stats on the OLED for 4 seconds. |

#### Button combinations

| Combination | Action |
|-------------|--------|
| `LEFT` + `RIGHT` held ≥ 500 ms | **Toggles** Friend Mode (*Friend Mode*): activates it if off, or deactivates it if on. The OLED shows `"Friend mode ON"` or `"Friend mode OFF"`. |

#### Friend Mode in detail

When Friend Mode is activated (by holding `LEFT` + `RIGHT` for ≥ 500 ms), the firmware activates the peer scanner:

1. **Active search** — the badge scans for nearby PwnPet badges with sufficient RSSI (> -80 dBm).
2. **Consent prompt** — upon detecting a compatible badge, the OLED shows its name and address and asks whether to add it as a friend.
3. **Confirmation** — press `UP` to **accept** the pairing. The new badge is registered in the friend list.
4. **Timeout rejection** — if `UP` is not pressed within 30 seconds, the firmware automatically discards the request. There is no explicit reject button.
5. **Deactivate** — hold `LEFT` + `RIGHT` ≥ 500 ms again to turn Friend Mode off.

> Note: while a request is pending, the `UP` button accepts the friendship instead of petting the creature.

---

## CTF Challenges (Overview)

The firmware includes a set of **built-in missions**. Each mission, when completed, grants XP and makes a flag (`PWNPET{...}`) available. This guide **does not solve them**; it explains the framework so you know how to approach them.

**How to explore them from the CLI:**

1. `missions` — discover which missions exist on *your* badge and which you have already completed.
2. `missions --hint <id>` — request the official firmware hint for a specific mission.
3. Interact (via the CLI or physically) until the mission is marked as completed.
4. `flag <id>` — collect the flag from a completed mission.

**Mission categories** (which ones exist depends on the `HAS_*` flags of your variant):

- **Time-based** — completed by letting a certain amount of time pass.
- **BLE interaction** — completed by sending a specific interaction through the CLI.
- **Sensor-based** — depend on the physical environment (chip temperature or ambient light).
- **Button pattern** — require a sequence of directional button presses (present because `HAS_BUTTONS=1`).

Some missions can be completed entirely from the CLI; others require **physical interaction** with the hardware (covering/illuminating a sensor, pressing buttons). This is intentional: the badge is both a physical device and a BLE target.

> Remember: the characteristics that contain flags are not named in the CLI and only return data when their conditions are met. Discover them using the firmware's own hints, not here.

### `arise` command — recovering a dead creature

If the creature dies (state `muerto (salud)` or `muerto (gordito)`), the `arise` command appears in the session:

```
(pwnpet) arise
WARNING: This will wipe all saved data and reboot the device.
Type yes to confirm: yes
Factory reset initiated. Device will reboot in ~1 s.
```

This performs a **complete factory reset**: clears XP, missions, name, and state, and reboots the badge. The creature is reborn in `fearful` with everything at zero.

> If `Arise blocked` appears, the firmware prevents the reset if the creature died too recently. Wait 3 minutes after the death and try again.

---

## Direct Subcommands (Without a Session)

For automation or scripting, each action is available as an independent subcommand:

```sh
pwnpet scan
pwnpet target set AA:BB:CC:DD:EE:FF   # save target
pwnpet target show                     # view saved target
pwnpet target clear                    # clear target
pwnpet status
pwnpet feed
pwnpet pet
pwnpet play 0x........
pwnpet passkey 163
pwnpet rename MyLlama
pwnpet missions
pwnpet flag 2
pwnpet read happiness
pwnpet write 0xC001 32                 # payload in hex (0x32 = 50 decimal)
```

Each subcommand accepts `--target <addr|name>` to override the saved target on a one-off basis. Keep in mind that each independent invocation pays the scan + connect + disconnect latency; for multiple actions in a row, the interactive session is much faster.

---

## Relationship Between Firmware and CLI

### How the firmware executes missions: `mission.cpp`

> **Note:** the firmware lives in a separate repository. The path below refers to its source tree.

The mission dispatcher (`firmware/pwnpet/src/framework/mission.cpp`) handles mission types in **two modes**, which explains why some missions are resolved from the CLI and others are not:

- **By tick (`mission_tick`)** — the firmware continuously evaluates **time** and **sensor** missions. Sensor missions use hysteresis (200 ms) or continuous duration to avoid false positives. These advance according to the clock or the physical world, **not** by CLI commands.
- **By event (`mission_notify_*`)** — **BLE write**, **touch**, and **button** missions are triggered when the corresponding event occurs:
  - `mission_notify_ble_write(uuid, value)` is called when you write to a characteristic from the CLI (e.g. using `play` or `write`). This means **a BLE_WRITE_SEQUENCE mission can be completed entirely from the CLI**.
  - `mission_notify_touch(channel)` and `mission_notify_button(btn)` are triggered by physical hardware. These **cannot** be simulated from the CLI: they require touching the badge.

In summary, the CLI is the path for BLE interaction missions and for *observing* the progress of all missions; sensor and button missions are completed in the physical plane. The CLI gives you the three tools to orchestrate this: `missions` (state), `missions --hint` (the firmware hint), and `flag` (the reward).

### The BLE bridge: from the C++ struct to text commands

The firmware exposes its state and actions as **GATT characteristics**. The CLI translates between human-readable names and those characteristics:

- Read game state → `status` groups several read-only characteristics (`0xFE0X`, `sensor_value`, `all_missions_done`).
- Act on the creature → `feed`/`pet`/`play`/`rename` write to interaction characteristics (`0xC00X`).
- Query missions → `missions` reads the list (`mission_list`, `0xFE08`), `--hint` reads `mission_hint` (`0xC006`), `flag` reads `mission_flag` (`0xC005`).
- The `state` byte (`0xFE05`) is translated to a name/color according to the state table.

---

## CLI Internal Architecture (Python)

The CLI is written in Python 3.10+ and organized as a package under `pwnpet_cli/` at the repository root. The main entry point is the `pwnpet` shim (also at the root), which delegates to `pwnpet_cli/__main__.py`; argument parsing and subcommand dispatch live in `pwnpet_cli/cli.py`.

### Main modules

| Module | Responsibility |
|--------|----------------|
| `pwnpet_cli/__main__.py` | Package entry point; called by the `pwnpet` shim via `from pwnpet_cli.__main__ import main` |
| `pwnpet_cli/cli.py` | `argparse` setup and top-level subcommand dispatch; custom asyncio exception handler that silences harmless `BrokenPipeError` on BLE teardown |
| `pwnpet_cli/target.py` | Persists the saved badge target in `~/.config/pwnpet/last_target.json` |
| `pwnpet_cli/transport.py` | BLE abstraction over `bleak`: scan, connection with retry logic, GATT read/write, and the composite `play_read_flag()` operation (write `0xC003`, settle, read `0xC0FF`) |
| `pwnpet_cli/chars.py` | Table of public names → 128-bit UUIDs, per-characteristic decoders (`DECODERS`), `SPECIES_TABLE`, and `resolve(name_or_0xNNNN)` |
| `pwnpet_cli/encoders.py` | User input parsers: `parse_play_hex`, `parse_passkey`, `parse_write_payload` |
| `pwnpet_cli/format.py` | Raw-bytes-to-text rendering: LE integers, UTF-8, states, `render_bytes_smart` |
| `pwnpet_cli/ui.py` | Terminal output with [Rich](https://github.com/Textualize/rich): `print_status`, `print_missions`, `print_help`, `ok`, `print_error` |
| `pwnpet_cli/errors.py` | Typed exceptions with stable exit codes: `CliError` (base), `UsageError` (1), `TargetNotFoundError` (2), `ConnectionFailedError` (3), `GattError` (4), `NotifyTimeoutError` (5) |
| `pwnpet_cli/commands/` | One module per CLI subcommand (`scan_cmd`, `target_cmd`, `status_cmd`, `read_cmd`, `write_cmd`, `feed_cmd`, `pet_cmd`, `play_cmd`, `passkey_cmd`, `rename_cmd`, `missions_cmd`, `flag_cmd`); each exposes `add_parser(subparsers)` and `run(args)` |
| `pwnpet_cli/commands/session_cmd.py` | Interactive REPL with an internal dispatch table (see below); also contains `_dispatch_friendship` — the `friendship` command is **not** a separate module |
| `pwnpet_cli/commands/_ops.py` | Reusable async operations: `fetch_status`, `fetch_missions`, `fetch_flag`, `fetch_mission_hint` |
| `pwnpet_cli/commands/_shared.py` | Shared GATT response decoding helpers: `decode(name_or_uuid, raw)` and `print_decoded(value)` (highlights `PWNPET{...}` flags in yellow) |

### The `session_cmd.py` module in detail

`session_cmd.py` implements the **interactive REPL**, the default CLI mode and its most-used piece. Its responsibilities:

**1. Persistent connection and clean shutdown.** `run()` resolves the target and opens a single `transport.Connection` instance inside an `async with` block. This ensures the BLE connection is closed cleanly on exit by any path (the `exit` command, `Ctrl+D`, a fatal error, or an exception).

**2. Initial state and death detection.** On connect, `_repl()` calls `fetch_status()` to print the state and then checks whether the creature is dead with `_creature_is_dead()`, which reads the `state` byte and checks whether it belongs to `_DEAD_STATES = {4, 5}`. That boolean (`creature_dead`) enables or disables the `arise` command.

**3. Read loop and tokenization.** The main loop reads lines with `ui.console.input("(pwnpet) ")` and tokenizes them with `shlex.split()`, which respects quotes (`rename "My Llama"` works). The first token is normalized to lowercase and used as the command name.

**4. Dispatch-table routing.** The command is looked up in `_DISPATCH_TABLE`, a `str → async handler` dictionary:

```python
_DISPATCH_TABLE = {
    "feed":       _cmd_feed,
    "pet":        _cmd_pet,
    "play":       _cmd_play,
    "status":     _cmd_status,
    "rename":     _cmd_rename,
    "passkey":    _cmd_passkey,
    "read":       _cmd_read,
    "write":      _cmd_write,
    "missions":   _cmd_missions,
    "flag":       _cmd_flag,
    "friendship": _dispatch_friendship,
}
```

**5. Commands with special semantics.** `help` and `arise` are handled **directly in the loop**, before consulting the table:
- `help` requires no active connection and displays `print_help(creature_dead)` (the `arise` row only appears if the creature is dead).
- `arise` re-checks the death state live, asks for explicit confirmation (`yes`), and only then writes to `factory_reset` (`0xC007`). If the firmware rejects the reset (death too recent), it translates the `GattError` into a clear `Arise blocked` message.

**6. Robust error handling.** Each dispatch is wrapped to distinguish:
- `KeyboardInterrupt` (`Ctrl+C`) **inside a running command**: prints `^C` and **continues** without closing the session. `Ctrl+C` or `Ctrl+D` at the prompt itself exits immediately.
- `UsageError`: incorrect arguments; shows the message and continues.
- `GattError`: BLE response rejected; shows the error and, if the connection was lost (`conn.is_connected == False`), ends the session with a notice.
- `Ctrl+D` / `EOFError` at the prompt: breaks the loop and closes cleanly.

### Friendship protocol (characteristic `0xC008`)

The `friendship` subcommand (handled by `_dispatch_friendship`) communicates with the firmware via an **opcode protocol** over a single read/write BLE characteristic, `friendship_cmd` (`0xC008`):

| Opcode | Firmware constant | Operation |
|--------|-------------------|-----------|
| `0x01` | `FRIENDSHIP_BLE_COUNT` | Number of friends |
| `0x02` | `FRIENDSHIP_BLE_GET` | Get entry by index |
| `0x03` | `FRIENDSHIP_BLE_REMOVE` | Remove by MAC address |
| `0x04` | `FRIENDSHIP_BLE_BLOCK` | Block by MAC address |
| `0x05` | `FRIENDSHIP_BLE_PROX_GET` | Read proximity state |
| `0x06` | `FRIENDSHIP_BLE_PROX_SET` | Enable/disable proximity |

For each operation the CLI does `write(0xC008, opcode + args)` followed by `read(0xC008)` and decodes the response. When listing, it supports both the *legacy* 12-byte format and the extended 20-byte format, detecting it by length.

---

## References

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | OK |
| 1 | Usage error (incorrect arguments) |
| 2 | Target not found (scan timeout) |
| 3 | Connection failure (BLE adapter or timeout) |
| 4 | GATT error (read/write rejected by firmware) |
| 5 | Notification timeout / incorrect magic value |

### Public BLE characteristics

Only the **public** characteristics (visible game state and interaction inputs) are named in the CLI. They are resolved by name or by short UUID `0xNNNN`.

| Name | UUID | Access | Description |
|------|------|--------|-------------|
| `species_id` | `0xFE01` | R | Species identifier (u16 LE) |
| `name` | `0xFE02` | R | Creature name (UTF-8, max 16 B) |
| `happiness` | `0xFE03` | R | Happiness (0–1000) |
| `hungry` | `0xFE04` | R | Hunger/energy level (0–1000) |
| `state` | `0xFE05` | R | Emotional state (u8) |
| `xp` | `0xFE06` | R | Experience points |
| `health` | `0xFE07` | R | Health (0–1000) |
| `mission_list` | `0xFE08` | R | Mission status |
| `all_missions_done` | `0xDE02` | R | Bool — all missions completed |
| `sensor_value` | `0xFA01` | R | Primary sensor (u32 LE) — chip temperature in this variant |
| `dream_log` | `0x5E01` | R | Dream text (UTF-8) |
| `feed` | `0xC001` | W | Feed (u8 amount) |
| `pet` | `0xC002` | W | Pet (0 bytes) |
| `play` | `0xC003` | W | Play (u32 LE magic) |
| `rename` | `0xC004` | W | Rename (UTF-8) |
| `mission_flag` | `0xC005` | R/W | Retrieve mission flag |
| `mission_hint` | `0xC006` | R/W | Mission hint |
| `factory_reset` | `0xC007` | W | Factory reset (used by `arise`) |
| `friendship_cmd` | `0xC008` | R+W | Friendship protocol (opcodes) |
| `passkey_input` | `0x5E02` | W | Send passkey (3 digits) |

> There are also **protected characteristics that contain flags**. By design they are *not* named in the CLI: they are reachable only by their raw UUID (`read 0xNNNN`) and return zero bytes until their access conditions are met. Discovering them is part of the challenges.

### Debugging

Add `-d` / `--debug` to any command to see the full traceback in case of an error:

```sh
pwnpet --debug session
pwnpet -d read happiness
```
