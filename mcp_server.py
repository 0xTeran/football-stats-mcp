#!/usr/bin/env python3
"""
Football Stats MCP Server - ESPN API
Herramientas para analizar estadísticas de fútbol sin necesidad de Chrome.

Modos de uso:
  python3 mcp_server.py            -> stdio (Claude Code local)
  python3 mcp_server.py http       -> HTTP/SSE en 0.0.0.0:8000
  python3 mcp_server.py http 9000  -> HTTP/SSE en puerto personalizado
"""

import sys
from datetime import datetime, timezone, timedelta
from curl_cffi import requests as creq
from mcp.server.fastmcp import FastMCP

# Detectar modo HTTP desde args para configurar host/port en el constructor
_http_mode = len(sys.argv) > 1 and sys.argv[1] == "http"
_port = int(sys.argv[2]) if _http_mode and len(sys.argv) > 2 else 8000

mcp = FastMCP(
    "football-stats",
    host="0.0.0.0" if _http_mode else "127.0.0.1",
    port=_port,
)

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

LEAGUES = {
    "England Premier League":     "eng.1",
    "Spain La Liga":              "esp.1",
    "Germany Bundesliga":         "ger.1",
    "Italy Serie A":              "ita.1",
    "France Ligue 1":             "fra.1",
    "UEFA Champions League":      "uefa.champions",
    "UEFA Europa League":         "uefa.europa",
    "Argentina Liga Profesional": "arg.1",
    "USA MLS":                    "usa.1",
    "Portugal Primeira Liga":     "por.1",
    "Netherlands Eredivisie":     "ned.1",
    "Mexico Liga MX":             "mex.1",
    "Brazil Serie A":             "bra.1",
    "Colombia Liga BetPlay":      "col.1",
    "Chile Primera Division":     "chl.1",
}

_session = creq.Session(impersonate="chrome131")


def _get(url: str, **params) -> dict:
    r = _session.get(url, params=params)
    r.raise_for_status()
    return r.json()


def _resolve_league(league: str) -> tuple[str, str]:
    """Returns (league_name, slug). Accepts name or slug."""
    if league in LEAGUES:
        return league, LEAGUES[league]
    for name, slug in LEAGUES.items():
        if name.lower() == league.lower() or slug == league:
            return name, slug
    raise ValueError(f"Liga no reconocida: '{league}'. Opciones: {list(LEAGUES.keys())}")


def _get_match_stats(league_slug: str, event_id: str) -> dict:
    data = _get(f"{BASE}/{league_slug}/summary", event=event_id)
    teams_raw = data.get("boxscore", {}).get("teams", [])
    rosters_raw = data.get("rosters", [])

    teams = {}
    for t in teams_raw:
        name = t.get("team", {}).get("displayName", "?")
        stats = {s["name"]: s.get("value", 0) for s in t.get("statistics", []) if "name" in s}
        teams[name] = stats

    players = {}
    for roster in rosters_raw:
        team_name = roster.get("team", {}).get("displayName", "?")
        for p in roster.get("roster", []):
            p_name = p.get("athlete", {}).get("displayName", "?")
            p_stats = {s["name"]: s.get("value", 0) for s in p.get("stats", []) if "name" in s}
            if p_stats.get("totalShots", 0) > 0 or p_stats.get("shotsOnTarget", 0) > 0:
                players.setdefault(team_name, {})[p_name] = p_stats

    return {"teams": teams, "players": players}


@mcp.tool()
def list_leagues() -> str:
    """Lista todas las ligas disponibles."""
    lines = [f"- {name} (slug: {slug})" for name, slug in LEAGUES.items()]
    return "Ligas disponibles:\n" + "\n".join(lines)


@mcp.tool()
def get_upcoming_matches(league: str, days: int = 14) -> str:
    """
    Obtiene los próximos partidos de una liga.

    Args:
        league: Nombre de la liga o slug ESPN (ej: 'England Premier League' o 'eng.1')
        days: Días hacia adelante para buscar (default: 14)
    """
    league_name, slug = _resolve_league(league)
    date_from = datetime.now().strftime("%Y%m%d")
    date_to = (datetime.now() + timedelta(days=days)).strftime("%Y%m%d")
    data = _get(f"{BASE}/{slug}/scoreboard", dates=f"{date_from}-{date_to}", limit=50)
    events = data.get("events", [])

    if not events:
        return f"No hay partidos próximos en {league_name} para los próximos {days} días."

    lines = [f"Próximos partidos - {league_name}:\n"]
    for e in events:
        comps = e.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        h_name = home.get("team", {}).get("displayName", "?")
        a_name = away.get("team", {}).get("displayName", "?")
        status = e.get("status", {}).get("type", {}).get("description", "")
        date_str = e.get("date", "")
        if date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            dt_local = dt.astimezone(timezone(timedelta(hours=-5)))
            date_str = dt_local.strftime("%d/%m %H:%M")
        lines.append(f"  ID:{e['id']} | {h_name} vs {a_name} | {date_str} | {status}")

    return "\n".join(lines)


@mcp.tool()
def get_recent_results(league: str, days_back: int = 60) -> str:
    """
    Obtiene los resultados recientes de una liga.

    Args:
        league: Nombre de la liga o slug ESPN
        days_back: Días hacia atrás para buscar (default: 60)
    """
    league_name, slug = _resolve_league(league)
    date_to = datetime.now().strftime("%Y%m%d")
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
    data = _get(f"{BASE}/{slug}/scoreboard", dates=f"{date_from}-{date_to}", limit=200)
    events = [e for e in data.get("events", []) if e.get("status", {}).get("type", {}).get("completed")]

    if not events:
        return f"No hay resultados recientes en {league_name}."

    lines = [f"Resultados recientes - {league_name}:\n"]
    for e in sorted(events, key=lambda x: x.get("date", ""), reverse=True)[:20]:
        comps = e.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        h_name = home.get("team", {}).get("displayName", "?")
        a_name = away.get("team", {}).get("displayName", "?")
        h_score = home.get("score", "?")
        a_score = away.get("score", "?")
        date_str = e.get("date", "")[:10]
        lines.append(f"  ID:{e['id']} | {h_name} {h_score}-{a_score} {a_name} | {date_str}")

    return "\n".join(lines)


@mcp.tool()
def get_match_stats(league: str, event_id: str) -> str:
    """
    Obtiene estadísticas detalladas de un partido (corners, tiros, jugadores).

    Args:
        league: Nombre de la liga o slug ESPN
        event_id: ID del partido (obtenido de get_upcoming_matches o get_recent_results)
    """
    _, slug = _resolve_league(league)
    stats = _get_match_stats(slug, event_id)

    lines = [f"Estadísticas del partido (ID: {event_id})\n"]

    lines.append("=== ESTADÍSTICAS POR EQUIPO ===")
    for team, s in stats["teams"].items():
        lines.append(f"\n{team}:")
        lines.append(f"  Corners:       {int(s.get('wonCorners', 0))}")
        lines.append(f"  Tiros totales: {int(s.get('totalShots', 0))}")
        lines.append(f"  Tiros a puerta:{int(s.get('shotsOnTarget', 0))}")
        lines.append(f"  Posesión:      {s.get('possessionPct', 0):.1f}%")
        lines.append(f"  Faltas:        {int(s.get('foulsCommitted', 0))}")
        lines.append(f"  Amarillas:     {int(s.get('yellowCards', 0))}")

    lines.append("\n=== TIROS POR JUGADOR ===")
    for team, players in stats["players"].items():
        lines.append(f"\n{team}:")
        sorted_p = sorted(players.items(), key=lambda x: x[1].get("totalShots", 0), reverse=True)
        for name, ps in sorted_p[:10]:
            shots = int(ps.get("totalShots", 0))
            on_target = int(ps.get("shotsOnTarget", 0))
            goals = int(ps.get("totalGoals", 0))
            lines.append(f"  {name}: {shots} tiros ({on_target} a puerta, {goals} goles)")

    return "\n".join(lines)


@mcp.tool()
def analyze_team(league: str, team_name: str, num_matches: int = 5) -> str:
    """
    Analiza las estadísticas de un equipo en sus últimos N partidos.

    Args:
        league: Nombre de la liga o slug ESPN
        team_name: Nombre exacto del equipo (ej: 'Manchester City')
        num_matches: Número de partidos a analizar (default: 5)
    """
    _, slug = _resolve_league(league)

    date_to = datetime.now().strftime("%Y%m%d")
    date_from = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
    data = _get(f"{BASE}/{slug}/scoreboard", dates=f"{date_from}-{date_to}", limit=200)
    recent = [e for e in data.get("events", []) if e.get("status", {}).get("type", {}).get("completed")]

    team_matches = []
    for e in sorted(recent, key=lambda x: x.get("date", ""), reverse=True):
        comps = e.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        names = [c.get("team", {}).get("displayName", "") for c in competitors]
        if team_name in names:
            team_matches.append(e)
        if len(team_matches) >= num_matches:
            break

    if not team_matches:
        return f"No se encontraron partidos recientes para '{team_name}' en la liga especificada."

    results = []
    player_agg: dict[str, dict] = {}
    totals = {"corners": 0, "shots_on_target": 0, "total_shots": 0}

    for e in team_matches:
        eid = e["id"]
        try:
            stats = _get_match_stats(slug, str(eid))
        except Exception:
            continue

        comps = e.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})
        h_name = home_comp.get("team", {}).get("displayName", "?")
        a_name = away_comp.get("team", {}).get("displayName", "?")
        h_score = home_comp.get("score", "?")
        a_score = away_comp.get("score", "?")
        is_home = h_name == team_name
        date_str = e.get("date", "")[:10]

        ts = stats["teams"].get(team_name, {})
        corners = int(ts.get("wonCorners", 0))
        shots_on = int(ts.get("shotsOnTarget", 0))
        total_sh = int(ts.get("totalShots", 0))
        totals["corners"] += corners
        totals["shots_on_target"] += shots_on
        totals["total_shots"] += total_sh

        loc = "L" if is_home else "V"
        results.append(f"  {loc} {h_name} {h_score}-{a_score} {a_name} ({date_str}) | Corners:{corners} T.puerta:{shots_on} T.total:{total_sh}")

        for p_name, ps in stats["players"].get(team_name, {}).items():
            if p_name not in player_agg:
                player_agg[p_name] = {"shots": [], "on_target": [], "goals": []}
            player_agg[p_name]["shots"].append(ps.get("totalShots", 0))
            player_agg[p_name]["on_target"].append(ps.get("shotsOnTarget", 0))
            player_agg[p_name]["goals"].append(ps.get("totalGoals", 0))

    n = len(results)
    if n == 0:
        return f"No se pudieron obtener estadísticas para '{team_name}'."

    lines = [f"Análisis de {team_name} - últimos {n} partidos:\n"]
    lines.extend(results)

    lines.append(f"\nPROMEDIOS:")
    lines.append(f"  Corners:        {totals['corners']/n:.1f}")
    lines.append(f"  Tiros a puerta: {totals['shots_on_target']/n:.1f}")
    lines.append(f"  Tiros totales:  {totals['total_shots']/n:.1f}")

    lines.append("\nTOP TIRADORES:")
    sorted_p = sorted(
        player_agg.items(),
        key=lambda x: sum(x[1]["shots"]) / max(len(x[1]["shots"]), 1),
        reverse=True,
    )
    for p_name, data in sorted_p[:10]:
        pj = len(data["shots"])
        avg_s = sum(data["shots"]) / pj
        avg_o = sum(data["on_target"]) / pj
        goals = sum(data["goals"])
        if avg_s < 0.3:
            continue
        lines.append(f"  {p_name}: {avg_s:.1f} tiros/pj ({avg_o:.1f} a puerta, {goals} goles)")

    return "\n".join(lines)


@mcp.tool()
def analyze_match(league: str, home_team: str, away_team: str, num_matches: int = 5) -> str:
    """
    Analiza un partido próximo comparando estadísticas de ambos equipos.

    Args:
        league: Nombre de la liga o slug ESPN
        home_team: Nombre del equipo local
        away_team: Nombre del equipo visitante
        num_matches: Partidos históricos a analizar por equipo (default: 5)
    """
    home_stats = analyze_team(league, home_team, num_matches)
    away_stats = analyze_team(league, away_team, num_matches)

    return (
        f"{'='*60}\n"
        f"ANÁLISIS: {home_team} vs {away_team}\n"
        f"{'='*60}\n\n"
        f"{home_stats}\n\n"
        f"{'─'*60}\n\n"
        f"{away_stats}"
    )


if __name__ == "__main__":
    if _http_mode:
        print(f"Football Stats MCP corriendo en http://0.0.0.0:{_port}/sse")
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
