"""Ansagen-Simulator fuer den Zugsimulator mit globalen Hotkeys.

Modernes UI mit Flet.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import keyboard  # type: ignore[import]
import pyttsx3  # type: ignore[import]
import flet as ft  # type: ignore[import]
from flet import Icons  # type: ignore[import]


@dataclass
class Route:
    """Repraesentiert eine Streckenliste."""

    name: str
    stations: List[str]


class AnnouncementManager:
    """Verwaltet die Abfolge der abzuspielenden Ansagen."""

    def __init__(self) -> None:
        self._route: Optional[Route] = None
        self._welcome_played = False
        self._next_index = 1
        self._finished = False
        self._last_message: Optional[str] = None

    def load_route(self, route: Route) -> None:
        self._route = route
        self._welcome_played = False
        self._finished = False
        self._last_message = None
        self._next_index = 1 if len(route.stations) > 1 else 0

    def has_route(self) -> bool:
        return self._route is not None

    def current_route(self) -> Optional[Route]:
        return self._route

    def _ensure_route(self) -> Route:
        if not self._route:
            raise RuntimeError("Keine Strecke geladen.")
        return self._route

    def next_message(self) -> Optional[str]:
        route = self._ensure_route()
        if self._finished:
            return None

        if not self._welcome_played:
            self._welcome_played = True
            start = route.stations[0]
            end = route.stations[-1]
            text = (
                f"Willkommen im Zug. Heute fahren wir von {start} nach {end}. "
                "Bitte achten Sie auf Ihre Gepaeckstuecke und eine angenehme Fahrt."
            )
            self._last_message = text
            return text

        if len(route.stations) == 1:
            text = (
                f"Wir erreichen in wenigen Augenblicken die Endstation {route.stations[0]}. "
                "Bitte steigen Sie vorsichtig aus."
            )
            self._finished = True
            self._last_message = text
            return text

        if self._next_index >= len(route.stations):
            self._finished = True
            farewell = (
                "Wir haben bereits alle Stationen erreicht. "
                "Vielen Dank, dass Sie mit uns gefahren sind."
            )
            self._last_message = farewell
            return farewell

        station = route.stations[self._next_index]
        if self._next_index == len(route.stations) - 1:
            text = (
                f"Wir erreichen in wenigen Augenblicken die Endstation {station}. "
                "Bitte nehmen Sie alle persoenlichen Gegenstaende mit."
            )
            self._finished = True
        else:
            text = f"Naechster Halt: {station}."

        self._next_index += 1
        self._last_message = text
        return text

    def repeat_last(self) -> Optional[str]:
        return self._last_message

    def next_station_name(self) -> Optional[str]:
        if not self._route or self._finished:
            return None
        if len(self._route.stations) == 1:
            return self._route.stations[0]
        if self._next_index >= len(self._route.stations):
            return None
        return self._route.stations[self._next_index]

    def reset(self) -> None:
        self._route = None
        self._welcome_played = False
        self._finished = False
        self._last_message = None
        self._next_index = 1


class AudioEngine:
    """Serialisiert TTS-Ausgaben ueber einen Hintergrund-Thread."""

    def __init__(self) -> None:
        self._engine = pyttsx3.init()
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._worker = threading.Thread(target=self._run_loop, daemon=True)
        self._worker.start()

    def speak(self, text: str) -> None:
        self._queue.put(text)

    def stop(self) -> None:
        self._queue.put(None)
        self._worker.join(timeout=2)

    def _run_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            self._engine.stop()
            self._engine.say(item)
            self._engine.runAndWait()


class HotkeyController:
    """Verwaltet globale Hotkeys ueber das keyboard-Modul."""

    def __init__(self) -> None:
        self._handles: Dict[str, int] = {}

    def register(self, name: str, combination: str, callback: Callable[[], None]) -> None:
        self.unregister(name)
        if not combination.strip():
            return
        try:
            handle = keyboard.add_hotkey(combination, callback, suppress=False)
        except Exception as exc:  # pragma: no cover - keyboard module specific
            raise ValueError(f"ungueltige Hotkey-Kombination: {combination}") from exc
        self._handles[name] = handle

    def unregister(self, name: str) -> None:
        handle = self._handles.pop(name, None)
        if handle is not None:
            keyboard.remove_hotkey(handle)

    def clear(self) -> None:
        for handle in self._handles.values():
            keyboard.remove_hotkey(handle)
        self._handles.clear()


def _read_route_file(file_path: Path) -> Route:
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = file_path.read_text(encoding="latin-1")
    stations = [line.strip() for line in content.splitlines() if line.strip()]
    if not stations:
        raise ValueError("Die Datei enthaelt keine Stationen.")
    return Route(name=file_path.stem, stations=stations)


def main(page: ft.Page) -> None:
    page.title = "Zug Ansagen Simulator"
    page.window_width = 900
    page.window_height = 640
    # Verwende einfache Theme-Vorgaben ohne neuere Flet-APIs
    try:
        page.theme = ft.Theme(color_scheme_seed="#3b82f6")
    except Exception:
        pass
    try:
        page.theme_mode = "light"  # aeltere Flet-Versionen akzeptieren String
    except Exception:
        pass

    announcement_manager = AnnouncementManager()
    audio = AudioEngine()
    hotkeys = HotkeyController()

    route_label = ft.Text("Keine Strecke geladen", weight=ft.FontWeight.W_600)
    status_text = ft.Text("Keine Ansage aktiv.", color="#666666")
    next_station_text = ft.Text("Naechster Halt: -", weight=ft.FontWeight.W_500)

    stations_column = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO)

    next_hotkey_field = ft.TextField(label="Naechste Ansage", value="ctrl+alt+n", dense=True)
    repeat_hotkey_field = ft.TextField(label="Letzte wiederholen", value="ctrl+alt+r", dense=True)

    snack = ft.SnackBar(content=ft.Text(""))
    page.snack_bar = snack

    def show_snack(text: str, color: str | None = None) -> None:
        page.snack_bar = ft.SnackBar(content=ft.Text(text, color=color or "#ffffff"))
        page.snack_bar.open = True
        page.update()

    def update_next_station_label() -> None:
        ns = announcement_manager.next_station_name()
        next_station_text.value = f"Naechster Halt: {ns}" if ns else "Naechster Halt: -"

    def rebuild_stations_view() -> None:
        stations_column.controls.clear()
        route = announcement_manager.current_route()
        if not route:
            page.update()
            return
        next_station = announcement_manager.next_station_name()
        for index, name in enumerate(route.stations, start=1):
            is_next = name == next_station
            bg = "#e3f2fd" if is_next else None
            fg = "#0d47a1" if is_next else None
            stations_column.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(f"{index:02d}.", width=40, color=fg),
                        ft.Text(name, expand=True, color=fg, weight=ft.FontWeight.W_500 if is_next else None),
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=bg,
                    padding=10,
                    border_radius=8,
                )
            )
        page.update()

    def trigger_next() -> None:
        if not announcement_manager.has_route():
            show_snack("Bitte zuerst eine Strecke laden.")
            return
        message = announcement_manager.next_message()
        if not message:
            status_text.value = "Alle Ansagen wurden bereits abgespielt."
            page.update()
            return
        status_text.value = f"Aktive Ansage: {message}"
        audio.speak(message)
        update_next_station_label()
        rebuild_stations_view()

    def repeat_last() -> None:
        message = announcement_manager.repeat_last()
        if not message:
            show_snack("Es wurde noch keine Ansage abgespielt.")
            return
        status_text.value = f"Wiederhole: {message}"
        audio.speak(message)
        page.update()

    def register_default_hotkeys() -> None:
        # Register initial hotkeys and wire callbacks into UI thread
        hotkeys.register("next", next_hotkey_field.value, lambda: page.call_from_thread(trigger_next))
        hotkeys.register("repeat", repeat_hotkey_field.value, lambda: page.call_from_thread(repeat_last))

    def register_user_hotkeys(e: ft.ControlEvent | None = None) -> None:
        try:
            hotkeys.register("next", next_hotkey_field.value, lambda: page.call_from_thread(trigger_next))
            hotkeys.register("repeat", repeat_hotkey_field.value, lambda: page.call_from_thread(repeat_last))
            show_snack("Hotkeys wurden gesetzt.")
        except ValueError as exc:
            show_snack(f"Hotkey-Fehler: {exc}", color="#ef9a9a")

    file_picker = ft.FilePicker()

    def on_file_result(e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        path_str = e.files[0].path or ""
        if not path_str:
            return
        try:
            route = _read_route_file(Path(path_str))
        except ValueError as exc:
            show_snack(f"Fehler beim Laden: {exc}")
            return
        announcement_manager.load_route(route)
        route_label.value = f"Strecke: {route.name} ({len(route.stations)} Stationen)"
        status_text.value = "Strecke geladen. Druecke Hotkey oder Button."
        update_next_station_label()
        rebuild_stations_view()

    file_picker.on_result = on_file_result
    page.overlay.append(file_picker)

    def choose_file(e: ft.ControlEvent | None = None) -> None:
        file_picker.pick_files(allow_multiple=False, allowed_extensions=["txt"]) 

    info_text = (
        "Hinweis: Globale Hotkeys benoetigen auf Windows moeglicherweise Administratorrechte. "
        "Die App muss im Hintergrund weiterlaufen, damit die Ansagen verfuegbar sind."
    )

    page.appbar = ft.AppBar(title=ft.Text("Zug Ansagen Simulator"), center_title=False)

    content = ft.Column(
        controls=[
            ft.Row([
                route_label,
                ft.ElevatedButton("Strecke laden...", icon=Icons.FOLDER_OPEN, on_click=choose_file),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.ElevatedButton("Naechste Ansage", icon=Icons.PLAY_ARROW, on_click=lambda e: trigger_next()),
                        ft.OutlinedButton("Letzte wiederholen", icon=Icons.REPLAY, on_click=lambda e: repeat_last()),
                    ], spacing=10),
                    ft.Text(info_text, color="#666666", size=12),
                ]),
                padding=10,
                border_radius=12,
                bgcolor="#efefef",
            ),

            ft.Container(
                content=ft.Column([
                    ft.Text("Strecken-Stationen", weight=ft.FontWeight.W_600),
                    ft.Container(stations_column, height=360, padding=10, border_radius=12),
                ]),
            ),

            ft.Divider(),

            ft.Row([
                ft.Icon(Icons.KEYBOARD),
                ft.Text("Hotkeys (global)", weight=ft.FontWeight.W_600),
            ]),
            ft.Row([
                next_hotkey_field,
                repeat_hotkey_field,
                ft.ElevatedButton("Hotkeys uebernehmen", icon=Icons.CHECK, on_click=register_user_hotkeys),
            ], alignment=ft.MainAxisAlignment.START),

            ft.Divider(),

            ft.Row([
                ft.Icon(Icons.INFO_OUTLINED, size=18),
                status_text,
                ft.Container(ft.Text(""), expand=True),
                next_station_text,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ],
        spacing=16,
    )

    page.add(content)
    register_default_hotkeys()
    page.update()

    def on_disconnect(e: ft.Event) -> None:
        hotkeys.clear()
        audio.stop()
    try:
        page.on_disconnect = on_disconnect
    except Exception:
        pass


if __name__ == "__main__":
    ft.app(target=main)
