"""Rich console and output helpers — all terminal I/O goes through here."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from . import bitmaps, chars, format as fmt

console = Console()
err_console = Console(stderr=True)

# State name → Rich style, shared with scan_cmd.
STATE_STYLE: dict[str, str] = {
    "temeroso": "yellow",
    "curioso": "green",
    "leal": "blue",
    "paranoia": "bold red",
    "muerto (salud)": "dim red",
    "muerto (gordito)": "dim red",
    "hambriento": "bold magenta",
}


def _fmt_value(key: str, val: object) -> str:
    s = str(val)
    if key == "owner_name":
        # Distinguish "no owner assigned" from a blank cell.
        return s if s else "[dim](unset)[/]"
    if key == "state":
        return f"[{STATE_STYLE.get(s, 'white')}]{s}[/]"
    if key == "all_missions_done":
        return "[green]true[/]" if s == "true" else "[dim]false[/]"
    if key == "hungry":
        try:
            n = int(s)
            if n >= 900:
                color = "bold red"  # gordito2 — very overfed
            elif n >= 750:
                color = "bold yellow"  # gordito1 — moderately overfed
            elif n >= 600:
                color = "yellow"  # gordito0 — lightly overfed
            elif n >= 300:
                color = "green"  # normal hunger range
            else:
                color = "red"  # too hungry
            return f"[{color}]{n} / 1000[/]"
        except ValueError:
            pass
    if key in fmt.RANGED_FIELDS:
        try:
            n = int(s)
            color = "green" if n >= 700 else "yellow" if n >= 300 else "red"
            return f"[{color}]{n} / 1000[/]"
        except ValueError:
            pass
    if key == "species_id":
        return f"[cyan]{s}[/]"
    return s


def print_status(values: dict[str, object]) -> None:
    st = str(values.get("state", "temeroso")).lower()
    species = values.get("species_id", "cloud")
    addon_conn = bool(values.get("addon_connected", True))
    sprite = bitmaps.get_sprite(st, species=species, addon_connected=addon_conn)
    if sprite:
        console.print(f"[cyan]{sprite}[/]")
    t = Table(box=None, show_header=False, padding=(0, 1, 0, 0))
    t.add_column(style="dim", no_wrap=True)
    t.add_column()
    for key, label in fmt.STATUS_FIELDS:
        if key in values:
            t.add_row(f"{label}:", _fmt_value(key, values[key]))
    console.print(t)


def print_help(creature_dead: bool = False, addon_connected: bool = True) -> None:
    t = Table(box=None, show_header=False, padding=(0, 2, 0, 0))
    t.add_column(style="cyan", no_wrap=True)
    t.add_column(style="dim")
    t.add_row("feed [amount]", "Feed the badge (default: 50, range 1-255)")
    t.add_row("pet", "Pet the badge")
    t.add_row("play <hex>", "Write u32 magic, read flag")
    t.add_row("rename <name>", "Change the pet's name (max 16 bytes)")
    t.add_row("owner [<name>]", "Read or set the badge holder's name (max 20 bytes)")
    t.add_row("status", "Read all public state")
    t.add_row("passkey <digits>", "Submit 3-digit passkey (e.g. 163)")
    t.add_row("missions", "List missions and completion status")
    t.add_row("missions [--hint] <id>", "Show hint for a specific mission")
    t.add_row("flag <id>", "Read the flag for a completed mission")
    t.add_row("friendship list", "Show friend list")
    t.add_row("friendship count", "Show number of friends")
    t.add_row("friendship remove <addr>", "Remove a friend (AA:BB:CC:DD:EE:FF)")
    t.add_row("friendship block <addr>", "Block a badge from future prompts")
    t.add_row("friendship proximity [on|off]", "Query or toggle proximity detection")
    t.add_row("read <name|0xNNNN>", "Read a characteristic by name or short UUID")
    t.add_row("write <name|0xNNNN> <hex>", "Write hex bytes to a characteristic")
    if addon_connected:
        t.add_row("addon ping|status|anim|set|blink|off", "Control Add-On via I2C")
        t.add_row(
            "clock countdown|reverse|spin|hour|off", "Control countdown ring / Neopixel"
        )
        t.add_row(
            "reflex start|hit|status|secret", "Play Reflex Wheel minigame & Supernova"
        )
        t.add_row("led on|off|blink|alloff|ping ...", "Control Add-On LEDs via I2C")
    if creature_dead:
        t.add_row(
            "arise",
            "Your pet is dead. Delete everything and pretend it never happened.",
        )
    t.add_row("help", "Show this help")
    t.add_row("exit / quit", "Disconnect and exit")
    console.print(t)


def print_missions(creature_name: str, missions: list[tuple[int, bool]]) -> None:
    console.print(f"Missions ({creature_name}):")
    if not missions:
        console.print("  [dim](no missions)[/]")
        return
    for mid, done in missions:
        mark = "[bold green]X[/]" if done else " "
        console.print(f"  [{mark}] mission [cyan]{mid}[/]")


def decode(name_or_uuid: str, raw: bytes) -> str:
    if name_or_uuid in chars.DECODERS:
        return str(chars.DECODERS[name_or_uuid](raw))  # type: ignore[operator]
    return fmt.render_bytes_smart(raw)


def print_decoded(value: str) -> None:
    if value.startswith("PWNPET{"):
        console.print(f"[bold bright_yellow]{value}[/]")
    else:
        console.print(value)


def ok(msg: str = "ok") -> None:
    console.print(f"[green]{msg}[/]")


def warn(msg: str) -> None:
    err_console.print(f"[yellow]WARN:[/] {msg}")


def print_error(category: str, message: str) -> None:
    err_console.print(f"[bold red]ERR[/]: [yellow]{category}[/]: {message}")


def print_scan_results(hits: list, raw: bool = False) -> None:
    t = Table(box=None, show_header=True, header_style="bold dim", padding=(0, 2, 0, 0))
    t.add_column("Name", style="bold")
    t.add_column("Address", style="dim")
    t.add_column("Species")
    t.add_column("State")
    if raw:
        t.add_column("Manuf", style="dim")

    for hit in hits:
        species_str = (
            chars.render_species_id(hit.species_id)
            if hit.species_id is not None
            else "?"
        )
        state_str = fmt.render_state(hit.state) if hit.state is not None else "?"
        state_cell = f"[{STATE_STYLE.get(state_str, 'white')}]{state_str}[/]"

        row: list[str] = [
            hit.name or "?",
            hit.addr,
            f"[cyan]{species_str}[/]",
            state_cell,
        ]
        if raw:
            row.append(hit.manuf_data.hex())
        t.add_row(*row)

    console.print(t)
