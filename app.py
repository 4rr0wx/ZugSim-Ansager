"""Ansagen-Simulator fuer den Zugsimulator mit globalen Hotkeys."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import keyboard  # type: ignore[import]
import pyttsx3  # type: ignore[import]
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


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


class AnnouncementApp(tk.Tk):
    """Tkinter-Frontend fuer den Ansagen-Simulator."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Zug Ansagen Simulator")
        self.geometry("640x480")

        self._announcement_manager = AnnouncementManager()
        self._audio = AudioEngine()
        self._hotkeys = HotkeyController()

        self._create_widgets()
        self._register_default_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self) -> None:
        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        load_frame = ttk.Frame(main)
        load_frame.pack(fill=tk.X, pady=(0, 10))

        self.route_label = ttk.Label(load_frame, text="Keine Strecke geladen")
        self.route_label.pack(side=tk.LEFT, expand=True, fill=tk.X)

        ttk.Button(load_frame, text="Strecke laden...", command=self._load_route).pack(
            side=tk.RIGHT
        )

        columns_frame = ttk.Frame(main)
        columns_frame.pack(fill=tk.BOTH, expand=True)

        self.station_list = tk.Listbox(columns_frame, height=15)
        self.station_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(columns_frame, orient=tk.VERTICAL, command=self.station_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.station_list.configure(yscrollcommand=scrollbar.set)

        status_frame = ttk.Frame(main)
        status_frame.pack(fill=tk.X, pady=(10, 0))

        self.status_var = tk.StringVar(value="Keine Ansage aktiv.")
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W)

        self.next_station_var = tk.StringVar(value="Naechster Halt: -")
        ttk.Label(status_frame, textvariable=self.next_station_var).pack(anchor=tk.W)

        controls = ttk.Frame(main)
        controls.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(controls, text="Naechste Ansage", command=self._trigger_next).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(controls, text="Letzte wiederholen", command=self._repeat_last).pack(
            side=tk.LEFT, padx=5
        )

        hotkey_frame = ttk.LabelFrame(main, text="Hotkeys (global)")
        hotkey_frame.pack(fill=tk.X, pady=(12, 0))

        self.next_hotkey_var = tk.StringVar(value="ctrl+alt+n")
        self.repeat_hotkey_var = tk.StringVar(value="ctrl+alt+r")

        ttk.Label(hotkey_frame, text="Naechste Ansage:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(hotkey_frame, textvariable=self.next_hotkey_var).grid(
            row=0, column=1, sticky="ew", padx=5, pady=5
        )

        ttk.Label(hotkey_frame, text="Letzte wiederholen:").grid(
            row=1, column=0, sticky="w", padx=5, pady=5
        )
        ttk.Entry(hotkey_frame, textvariable=self.repeat_hotkey_var).grid(
            row=1, column=1, sticky="ew", padx=5, pady=5
        )

        hotkey_frame.columnconfigure(1, weight=1)

        ttk.Button(hotkey_frame, text="Hotkeys uebernehmen", command=self._register_user_hotkeys).grid(
            row=2, column=0, columnspan=2, pady=5
        )

        info_text = (
            "Hinweis: Globale Hotkeys benoetigen auf Windows moeglicherweise Administratorrechte. "
            "Die App muss im Hintergrund weiterlaufen, damit die Ansagen verfuegbar sind."
        )
        ttk.Label(main, text=info_text, wraplength=600, foreground="#555555").pack(
            fill=tk.X, pady=(10, 0)
        )

    def _register_default_hotkeys(self) -> None:
        self._hotkeys.register("next", self.next_hotkey_var.get(), self._on_next_hotkey)
        self._hotkeys.register("repeat", self.repeat_hotkey_var.get(), self._on_repeat_hotkey)

    def _register_user_hotkeys(self) -> None:
        try:
            self._hotkeys.register("next", self.next_hotkey_var.get(), self._on_next_hotkey)
            self._hotkeys.register("repeat", self.repeat_hotkey_var.get(), self._on_repeat_hotkey)
            messagebox.showinfo("Hotkeys aktualisiert", "Die Hotkey-Belegungen wurden gesetzt.")
        except ValueError as exc:
            messagebox.showerror("Fehler", f"Hotkey konnte nicht gesetzt werden: {exc}")

    def _on_next_hotkey(self) -> None:
        self.after(0, self._trigger_next)

    def _on_repeat_hotkey(self) -> None:
        self.after(0, self._repeat_last)

    def _load_route(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Strecke laden",
            filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")],
        )
        if not file_path:
            return

        try:
            route = self._read_route(Path(file_path))
        except ValueError as exc:
            messagebox.showerror("Fehler beim Laden", str(exc))
            return

        self._announcement_manager.load_route(route)
        self._populate_station_list(route.stations)
        self.route_label.config(text=f"Strecke: {route.name} ({len(route.stations)} Stationen)")
        self.status_var.set("Strecke geladen. Druecke den Hotkey oder Button fuer die Ansagen.")
        self._update_next_station_label()
        self._highlight_current_position()

    def _read_route(self, file_path: Path) -> Route:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")

        stations = [line.strip() for line in content.splitlines() if line.strip()]
        if not stations:
            raise ValueError("Die Datei enthaelt keine Stationen.")
        return Route(name=file_path.stem, stations=stations)

    def _populate_station_list(self, stations: List[str]) -> None:
        self.station_list.delete(0, tk.END)
        for index, name in enumerate(stations, start=1):
            self.station_list.insert(tk.END, f"{index:02d}. {name}")
        if stations:
            self.station_list.selection_clear(0, tk.END)
            self.station_list.activate(0)
            self.station_list.selection_set(0)

    def _trigger_next(self) -> None:
        if not self._announcement_manager.has_route():
            messagebox.showwarning("Keine Strecke", "Bitte zuerst eine Strecke laden.")
            return

        message = self._announcement_manager.next_message()
        if not message:
            self.status_var.set("Alle Ansagen wurden bereits abgespielt.")
            return

        self.status_var.set(f"Aktive Ansage: {message}")
        self._audio.speak(message)
        self._update_next_station_label()
        self._highlight_current_position()

    def _repeat_last(self) -> None:
        message = self._announcement_manager.repeat_last()
        if not message:
            messagebox.showinfo("Keine Ansage", "Es wurde noch keine Ansage abgespielt.")
            return
        self.status_var.set(f"Wiederhole: {message}")
        self._audio.speak(message)

    def _update_next_station_label(self) -> None:
        next_station = self._announcement_manager.next_station_name()
        if next_station:
            self.next_station_var.set(f"Naechster Halt: {next_station}")
        else:
            self.next_station_var.set("Naechster Halt: -")

    def _highlight_current_position(self) -> None:
        route = self._announcement_manager.current_route()
        if not route:
            return
        next_station = self._announcement_manager.next_station_name()
        self.station_list.selection_clear(0, tk.END)
        if next_station and next_station in route.stations:
            index = route.stations.index(next_station)
            self.station_list.selection_set(index)
            self.station_list.activate(index)
            self.station_list.see(index)

    def _on_close(self) -> None:
        self._hotkeys.clear()
        self._audio.stop()
        self.destroy()


def main() -> None:
    app = AnnouncementApp()
    app.mainloop()


if __name__ == "__main__":
    main()
