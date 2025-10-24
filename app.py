from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

PRESET_ANNOUNCEMENTS = [
    {
        "id": "doors-closing",
        "title": "Bitte Türen schließen",
        "description": "Hinweis zum Schließen der Türen vor der Abfahrt.",
        "message": (
            "Bitte schließen Sie die Türen. "
            "Der Zug fährt in wenigen Augenblicken weiter. Vielen Dank."
        ),
    },
    {
        "id": "delay-info",
        "title": "Verspätungsinformation",
        "description": "Allgemeine Verzögerung durchgeben.",
        "message": (
            "Liebe Fahrgäste, aufgrund einer vor uns fahrenden Bahn "
            "verzögert sich unsere Weiterfahrt um wenige Minuten. "
            "Wir bitten um Ihr Verständnis."
        ),
    },
    {
        "id": "service-info",
        "title": "Servicehinweis",
        "description": "Service- oder Bordgastronomie ankündigen.",
        "message": (
            "Liebe Fahrgäste, der mobile Bordservice kommt gleich durch den Zug. "
            "Wir bieten Ihnen Getränke, Snacks und kleine Speisen an."
        ),
    },
    {
        "id": "connection-info",
        "title": "Anschlusszüge",
        "description": "Anschlussmöglichkeiten ankündigen.",
        "message": (
            "Sehr geehrte Fahrgäste, am nächsten Bahnhof bestehen "
            "Anschlüsse an regionale und überregionale Züge. "
            "Bitte beachten Sie die aktuellen Anzeigen am Bahnsteig."
        ),
    },
    {
        "id": "security-note",
        "title": "Sicherheitsdurchsage",
        "description": "Allgemeiner Sicherheitshinweis.",
        "message": (
            "Bitte achten Sie auf Ihr Gepäck und melden Sie Unregelmäßigkeiten "
            "unserem Zugpersonal. Wir wünschen weiterhin eine angenehme Fahrt."
        ),
    },
]


@dataclass
class Route:
    """Repräsentiert eine Streckenliste."""

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

    def reset(self) -> None:
        self._route = None
        self._welcome_played = False
        self._finished = False
        self._last_message = None
        self._next_index = 1

    def has_route(self) -> bool:
        return self._route is not None

    def current_route(self) -> Optional[Route]:
        return self._route

    def _ensure_route(self) -> Route:
        if not self._route:
            raise RuntimeError("Keine Strecke geladen.")
        return self._route

    def next_message(self) -> str:
        route = self._ensure_route()
        if self._finished:
            raise RuntimeError("Alle Ansagen wurden bereits abgespielt.")

        if not self._welcome_played:
            self._welcome_played = True
            start = route.stations[0]
            end = route.stations[-1]
            text = (
                f"Willkommen im Zug nach {end}."
                "Bitte achten Sie auf Ihre Gepäckstücke und wir wünschen Ihnen eine angenehme Fahrt."
            )
            self._last_message = text
            return text

        if len(route.stations) == 1:
            text = (
                f"Wir erreichen in wenigen Augenblicken die Endstation {route.stations[0]}. "
                "Bitte steigen Sie aus. Vielen Dank, dass Sie mit uns gefahren sind."
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
                "Bitte nehmen Sie alle persönlichen Gegenstände mit. Vielen Dank, dass Sie mit uns gefahren sind."
            )
            self._finished = True
        else:
            text = f"Nächster Halt: {station}."

        self._next_index += 1
        self._last_message = text
        return text

    def repeat_last(self) -> str:
        if not self._last_message:
            raise RuntimeError("Es wurde noch keine Ansage abgespielt.")
        return self._last_message

    def next_station_name(self) -> Optional[str]:
        if not self._route or self._finished:
            return None
        if len(self._route.stations) == 1:
            return self._route.stations[0]
        if self._next_index >= len(self._route.stations):
            return None
        return self._route.stations[self._next_index]

    def is_finished(self) -> bool:
        return self._finished


def read_route_file(raw_bytes: bytes, filename: str) -> Route:
    path = Path(filename)
    name = path.stem or "Unbenannte Strecke"
    for encoding in ("utf-8", "latin-1"):
        try:
            content = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - defensive fallback
        raise ValueError("Die Datei konnte nicht gelesen werden.")

    stations = [line.strip() for line in content.splitlines() if line.strip()]
    if not stations:
        raise ValueError("Die Datei enthält keine gültigen Stationen.")
    return Route(name=name, stations=stations)


announcement_manager = AnnouncementManager()
state_lock = asyncio.Lock()

app = FastAPI(title="Zug Ansagen Web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def serialize_state() -> dict:
    route = announcement_manager.current_route()
    return {
        "routeLoaded": bool(route),
        "routeName": route.name if route else None,
        "stations": route.stations if route else [],
        "nextStation": announcement_manager.next_station_name(),
        "finished": announcement_manager.is_finished(),
    }


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/state")
async def get_state() -> dict:
    async with state_lock:
        return serialize_state()


@app.get("/api/presets")
async def get_presets() -> dict:
    return {"presets": PRESET_ANNOUNCEMENTS}


@app.post("/api/route")
async def upload_route(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        route = read_route_file(data, file.filename or "strecke.txt")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async with state_lock:
        announcement_manager.load_route(route)
        return serialize_state()


@app.post("/api/next")
async def next_message() -> dict:
    async with state_lock:
        try:
            message = announcement_manager.next_message()
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state = serialize_state()
        return {"message": message, "state": state}


@app.post("/api/repeat")
async def repeat_message() -> dict:
    async with state_lock:
        try:
            message = announcement_manager.repeat_last()
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"message": message}


@app.post("/api/preset")
async def trigger_preset(preset_id: str = Body(..., embed=True, alias="presetId")) -> dict:
    preset = next((item for item in PRESET_ANNOUNCEMENTS if item["id"] == preset_id), None)
    if not preset:
        raise HTTPException(status_code=404, detail="Unbekannte Sonderansage.")
    return {"message": preset["message"], "preset": preset}


@app.post("/api/reset")
async def reset() -> dict:
    async with state_lock:
        announcement_manager.reset()
        return serialize_state()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
