
"""Fantasy Golf Tracker - CQRS with Relay pattern + DaisyUI + Optimistic UI."""

import asyncio
import sys
from dataclasses import dataclass

import httpx
from stario import Context, JsonTracer, Relay, RichTracer, Stario, Writer, at, data
from stario.html import (
    Body, Button, Div, H1, Head, Html, Input, Meta, Script, Link, Span, Table, Td, Th, Title, Tr, Thead, Tbody
)

# =============================================================================
# State
# =============================================================================

tracked_users: set[str] = {"deufel"}
relay: Relay[str] = Relay()

# =============================================================================
# Data Fetching
# =============================================================================

def search_entry(username: str) -> dict | None:
    """Search for a user's fantasy golf entry."""
    url = "https://fantasygolfchampionships.shgn.com/api/graphql"
    query = """query contestEntrySearch($id: ID!, $prefix: String!) {
      entrySearch(contestId: $id, usernamePrefix: $prefix) {
        id fantasyPoints currentPlace winnings
        user { username }
        entryStats { wins top5s top20s cutsMade }
      }
    }"""
    try:
        resp = httpx.post(url, json={
            "operationName": "contestEntrySearch",
            "query": query,
            "variables": {"id": "qqf89w", "prefix": username}
        }, timeout=5.0)
    except (httpx.TimeoutException, httpx.RequestError):
        return None
    results = resp.json().get('data', {}).get('entrySearch', [])
    for entry in results:
        if entry['user']['username'].lower() == username.lower():
            return entry
    return results[0] if results else None

# =============================================================================
# Views
# =============================================================================

def page(*children):
    """Base HTML page with Datastar and DaisyUI."""
    return Html(
        {"lang": "en", "data-theme": "forest"},
        Head(
            Meta({"charset": "UTF-8"}),
            Meta({"name": "viewport", "content": "width=device-width, initial-scale=1"}),
            Title("Tracker"),
            Link({"rel": "stylesheet", "href": "https://cdn.jsdelivr.net/npm/daisyui@4.12.14/dist/full.min.css"}),
            Script({"src": "https://cdn.tailwindcss.com"}),
            Script({"type": "module", "src": "https://cdn.jsdelivr.net/gh/starfederation/datastar@1.0.0-RC.7/bundles/datastar.js"}),
        ),
        Body({"class": "min-h-screen bg-base-200"}, *children),
    )

def loading_row(username: str):
    """A row that shows loading state and fetches user data on init."""
    username_lower = username.lower()
    return Tr(
        {"id": f"row-{username_lower}"},
        data.indicator(f"loading_{username_lower}"),
        data.init(at.get(f"/fetch-user?user={username_lower}")),
        # Rank
        Td(Div({"class": "badge badge-ghost"}, "—")),
        # Name - compact
        Td({"class": "font-medium"}, username[:5], data.show("$compact")),
        # Name - full
        Td({"class": "font-medium"}, username, data.show("!$compact")),
        # Compact: loading in winnings column
        Td(Span({"class": "loading loading-spinner loading-sm"}), data.show("$compact")),
        # Full: loading spans across all columns
        Td(Span({"class": "loading loading-spinner loading-sm"}), data.show("!$compact")),
        Td(Span({"class": "loading loading-spinner loading-sm"}), " Loading...", data.show("!$compact")),
        Td(data.show("!$compact")),
        Td(data.show("!$compact")),
        # Remove button 
        Td(Button({"class": "btn btn-error btn-xs btn-circle"}, data.on("click", at.post(f"/remove?user={username_lower}")), "✕"), data.show("$edit")),
    )

def get_all_entries() -> list[dict]:
    """Fetch all tracked users and return sorted by points (descending)."""
    entries = []
    for username in tracked_users:
        entry = search_entry(username)
        if entry:
            entries.append(entry)
        else:
            entries.append({'user': {'username': username}, 'not_found': True})
    entries.sort(key=lambda e: float(e.get('fantasyPoints', 0)) if not e.get('not_found') else -1, reverse=True)
    return entries

def leaderboard_table():
    """Render the full leaderboard table with compact/full views."""
    entries = get_all_entries()
    rows = []
    
    for local_rank, entry in enumerate(entries, 1):
        username = entry['user']['username']
        username_lower = username.lower()
        
        if entry.get('not_found'):
            rows.append(Tr(
                {"id": f"row-{username_lower}"},
                Td(Div({"class": "badge badge-primary"}, str(local_rank))),
                Td({"class": "font-medium"}, username[:5], data.show("$compact")),
                Td({"class": "font-medium"}, username, data.show("!$compact")),
                Td({"class": "text-base-content/50"}, "—", data.show("$compact")),
                Td({"class": "text-base-content/50", "colspan": "4"}, "Not found", data.show("!$compact")),
                Td(Button({"class": "btn btn-error btn-xs btn-circle"}, data.on("click", at.post(f"/remove?user={username_lower}")), "✕"), data.show("$edit")),
            ))
        else:
            stats = entry['entryStats']
            rows.append(Tr(
                {"id": f"row-{username_lower}", "class": "hover"},
                Td(Div({"class": "badge badge-primary"}, str(local_rank))),
                Td({"class": "font-medium"}, username[:5], data.show("$compact")),
                Td({"class": "font-medium"}, entry['user']['username'], data.show("!$compact")),
                Td({"class": "font-mono text-success"}, f"${int(float(entry['winnings'])):,}", data.show("$compact")),
                Td(Div({"class": "badge badge-ghost badge-sm"}, f"#{entry['currentPlace']}"), data.show("!$compact")),
                Td({"class": "font-mono"}, f"${int(float(entry['fantasyPoints'])):,}", data.show("!$compact")),
                Td({"class": "font-mono text-success"}, f"${int(float(entry['winnings'])):,}", data.show("!$compact")),
                Td(
                    Div({"class": "flex flex-wrap gap-1"},
                        Div({"class": "badge badge-sm"}, f"W:{stats['wins']}"),
                        Div({"class": "badge badge-sm"}, f"T5:{stats['top5s']}"),
                        Div({"class": "badge badge-sm"}, f"T20:{stats['top20s']}"),
                        Div({"class": "badge badge-sm"}, f"Cuts:{stats['cutsMade']}"),
                    ),
                    data.show("!$compact")
                ),
                Td(Button({"class": "btn btn-error btn-xs btn-circle"}, data.on("click", at.post(f"/remove?user={username_lower}")), "✕"), data.show("$edit")),
            ))
    
    return Div(
        {"class": "overflow-x-auto"},
        Table(
            {"class": "table table-zebra table-xs sm:table-sm"},
            Thead(
                Tr(
                    data.show("$compact"),
                    Th({"class": "px-2"}, "#"),
                    Th({"class": "px-2"}, "Name"),
                    Th({"class": "px-2"}, "Won"),
                    Th({"class": "px-1"}, "", data.show("$edit")),
                ),
                Tr(
                    data.show("!$compact"),
                    Th({"class": "px-2"}, "#"),
                    Th({"class": "px-2"}, "Player"),
                    Th({"class": "px-2"}, "Place"),
                    Th({"class": "px-2"}, "Points"),
                    Th({"class": "px-2"}, "Winnings"),
                    Th({"class": "px-2"}, "Stats"),
                    Th({"class": "px-1"}, "", data.show("$edit")),
                ),
            ),
            Tbody({"id": "leaderboard-body"}, *rows),
        )
    )

def tracker_view():
    """Main tracker view - form and leaderboard."""
    return Div(
        {"id": "tracker", "class": "container mx-auto p-4 max-w-4xl"},
        Div(
            {"class": "card bg-base-100 shadow-xl"},
            Div(
                {"class": "card-body"},
                # Header row with title left, toggles right
                Div(
                    {"class": "flex justify-between items-center mb-4"},
                    H1({"class": "card-title text-xl"}, "Golf Tracker"),
                    Div(
                        {"class": "flex gap-2"},
                        data.signals({"compact": False, "edit": False}, ifmissing=True),
                        Div(
                            {"class": "flex items-center gap-1"},
                            Input({"type": "checkbox", "class": "toggle toggle-sm toggel-primary"}, data.bind("compact")),
                            Span({"class": "label-text"}, "Compact"),
                        ),
                        Div(
                            {"class": "flex items-center gap-1"},
                            Input({"type": "checkbox", "class": "toggle toggle-sm toggle-primary"}, data.bind("edit")),
                            Span({"class": "label-text"}, "Edit"),
                        ),
                    ),
                ),
                # Add player form - only visible in edit mode
                Div(
                    {"class": "flex gap-1 mb-3"},
                    data.show("$edit"),
                    data.signals({"newUser": ""}, ifmissing=True),
                    Input({
                        "type": "text",
                        "placeholder": "Enter username to track...",
                        "class": "input input-bordered input-primary flex-1"
                    }, data.bind("newUser")),
                    Button({"class": "btn btn-primary"}, data.on("click", at.post("/add")), "Add Player"),
                ),
                leaderboard_table(),
            )
        )
    )

def home_view():
    """Full home page with SSE subscription."""
    return page(
        Div(
            {"id": "home", "class": "py-8"},
            data.init(at.get("/subscribe", retry="always")),
            tracker_view(),
        ),
    )

# =============================================================================
# Handlers
# =============================================================================

@dataclass
class AddSignals:
    newUser: str = ""

async def home(c: Context, w: Writer) -> None:
    """Serve the home page."""
    w.html(home_view())

async def subscribe(c: Context, w: Writer) -> None:
    """SSE endpoint - subscribe to real-time updates."""
    w.patch(tracker_view())
    async for event, payload in w.alive(relay.subscribe("*")):
        c("on_event", {"event": event, "payload": payload})
        if event == "add":
            # Optimistic: show loading row immediately
            w.patch(loading_row(payload), selector="#leaderboard-body", mode="append")
        else:
            # Everything else: full refresh
            w.patch(tracker_view())

async def add_user(c: Context, w: Writer) -> None:
    """Add a user to tracking - optimistic, no API fetch."""
    signals = await c.signals(AddSignals)
    username = signals.newUser.strip()
    if username and username.lower() not in tracked_users:
        tracked_users.add(username.lower())
        c("user_added", {"username": username})
        relay.publish("add", username)
    w.empty(204)

async def remove_user(c: Context, w: Writer) -> None:
    """Remove a user from tracking - immediate removal."""
    username = c.req.query.get("user", "")
    tracked_users.discard(username.lower())
    c("user_removed", {"username": username})
    # Remove the row immediately for this client
    w.patch("", selector=f"#row-{username.lower()}", mode="remove")
    # Notify others
    relay.publish("remove", username)

async def fetch_user(c: Context, w: Writer) -> None:
    """Fetch triggers a full refresh."""
    username = c.req.query.get("user", "")
    if username.lower() not in tracked_users:
        w.empty(204)
        return
    c("fetching_user", {"username": username})
    w.empty(204)
    relay.publish("refresh", username)

# =============================================================================
# App
# =============================================================================

async def main():
    if "--local" in sys.argv or sys.stdout.isatty():
        tracer = RichTracer()
        host = "127.0.0.1"
        port = 8000
    else:
        tracer = JsonTracer()
        host = "0.0.0.0"
        port = 8000
    
    with tracer:
        app = Stario(tracer)
        app.get("/", home)
        app.get("/subscribe", subscribe)
        app.get("/fetch-user", fetch_user)
        app.post("/add", add_user)
        app.post("/remove", remove_user)
        await app.serve(host=host, port=port)

if __name__ == "__main__":
    asyncio.run(main())
