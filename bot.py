#!/usr/bin/env python3
"""
Football Stats Bot - Análisis de estadísticas vía ESPN API (sin Chrome)
Analiza partidos próximos con datos históricos de:
- Tiros de esquina (corners)
- Tiros a puerta (shots on target)
- Tiros totales por equipo
- Tiros por jugador
"""

import sys
from datetime import datetime, timezone, timedelta
from curl_cffi import requests as creq
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

LEAGUES = {
    "1":  ("England Premier League",     "eng.1"),
    "2":  ("Spain La Liga",              "esp.1"),
    "3":  ("Germany Bundesliga",         "ger.1"),
    "4":  ("Italy Serie A",              "ita.1"),
    "5":  ("France Ligue 1",             "fra.1"),
    "6":  ("UEFA Champions League",      "uefa.champions"),
    "7":  ("UEFA Europa League",         "uefa.europa"),
    "8":  ("Argentina Liga Profesional", "arg.1"),
    "9":  ("USA MLS",                    "usa.1"),
    "10": ("Portugal Primeira Liga",     "por.1"),
    "11": ("Netherlands Eredivisie",     "ned.1"),
    "12": ("Mexico Liga MX",             "mex.1"),
    "13": ("Brazil Serie A",             "bra.1"),
    "14": ("Colombia Liga BetPlay",      "col.1"),
    "15": ("Chile Primera Division",     "chl.1"),
}

_session = creq.Session(impersonate="chrome131")


def api_get(url: str, **params) -> dict:
    r = _session.get(url, params=params)
    r.raise_for_status()
    return r.json()


def get_upcoming_matches(league_slug: str, days: int = 14) -> list[dict]:
    date_from = datetime.now().strftime("%Y%m%d")
    date_to = (datetime.now() + timedelta(days=days)).strftime("%Y%m%d")
    data = api_get(
        f"{BASE}/{league_slug}/scoreboard",
        dates=f"{date_from}-{date_to}",
        limit=50,
    )
    return data.get("events", [])


def get_recent_matches(league_slug: str, days_back: int = 60) -> list[dict]:
    date_to = datetime.now().strftime("%Y%m%d")
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
    data = api_get(
        f"{BASE}/{league_slug}/scoreboard",
        dates=f"{date_from}-{date_to}",
        limit=200,
    )
    events = data.get("events", [])
    return [e for e in events if e.get("status", {}).get("type", {}).get("completed")]


def get_match_stats(league_slug: str, event_id: str) -> dict:
    data = api_get(f"{BASE}/{league_slug}/summary", event=event_id)
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


def get_team_recent_stats(league_slug, team_name, all_finished, num=5):
    team_matches = []
    for e in sorted(all_finished, key=lambda x: x.get("date", ""), reverse=True):
        comps = e.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        names = [c.get("team", {}).get("displayName", "") for c in competitors]
        if team_name in names:
            team_matches.append(e)
        if len(team_matches) >= num:
            break

    results = []
    for e in team_matches:
        eid = e["id"]
        try:
            stats = get_match_stats(league_slug, eid)
        except Exception:
            continue

        comps = e.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})
        home_name = home_comp.get("team", {}).get("displayName", "?")
        away_name = away_comp.get("team", {}).get("displayName", "?")
        home_score = home_comp.get("score", "?")
        away_score = away_comp.get("score", "?")
        is_home = home_name == team_name

        team_stats = stats["teams"].get(team_name, {})
        results.append({
            "match_id": eid,
            "home": home_name,
            "away": away_name,
            "score": f"{home_score}-{away_score}",
            "is_home": is_home,
            "corners": team_stats.get("wonCorners", 0),
            "shots_on_target": team_stats.get("shotsOnTarget", 0),
            "total_shots": team_stats.get("totalShots", 0),
            "date": e.get("date", ""),
            "players": stats["players"].get(team_name, {}),
        })

    return {"team": team_name, "matches": results}


def print_team_analysis(analysis):
    team = analysis["team"]
    matches = analysis["matches"]
    if not matches:
        console.print(f"[yellow]Sin datos para {team}[/yellow]")
        return

    table = Table(title=f"Últimos {len(matches)} partidos - {team}", box=box.ROUNDED, show_lines=True)
    table.add_column("Partido", style="bold", max_width=42)
    table.add_column("Res.", justify="center")
    table.add_column("Corners", justify="center", style="cyan")
    table.add_column("T. puerta", justify="center", style="green")
    table.add_column("T. total", justify="center")

    totals = {"c": 0, "so": 0, "st": 0}
    for m in matches:
        totals["c"] += m["corners"]
        totals["so"] += m["shots_on_target"]
        totals["st"] += m["total_shots"]
        dt = m["date"][:10] if m["date"] else "?"
        loc = "[green]L[/green]" if m["is_home"] else "[blue]V[/blue]"
        table.add_row(
            f"{loc} {m['home']} vs {m['away']} ({dt})",
            m["score"],
            str(int(m["corners"])),
            str(int(m["shots_on_target"])),
            str(int(m["total_shots"])),
        )

    n = len(matches)
    table.add_row(
        "[bold]PROMEDIO[/bold]", "",
        f"[bold cyan]{totals['c']/n:.1f}[/bold cyan]",
        f"[bold green]{totals['so']/n:.1f}[/bold green]",
        f"[bold]{totals['st']/n:.1f}[/bold]",
    )
    console.print(table)


def print_player_shots(analysis):
    team = analysis["team"]
    matches = analysis["matches"]
    player_agg = {}
    for m in matches:
        for name, stats in m.get("players", {}).items():
            if name not in player_agg:
                player_agg[name] = {"shots": [], "on_target": [], "goals": []}
            player_agg[name]["shots"].append(stats.get("totalShots", 0))
            player_agg[name]["on_target"].append(stats.get("shotsOnTarget", 0))
            player_agg[name]["goals"].append(stats.get("totalGoals", 0))

    if not player_agg:
        console.print(f"[yellow]Sin datos de jugadores para {team}[/yellow]")
        return

    table = Table(title=f"Tiros por jugador - {team}", box=box.ROUNDED, show_lines=True)
    table.add_column("Jugador", style="bold")
    table.add_column("PJ", justify="center")
    table.add_column("Tiros", justify="center")
    table.add_column("Prom", justify="center", style="cyan")
    table.add_column("A puerta", justify="center")
    table.add_column("Prom", justify="center", style="green")
    table.add_column("Goles", justify="center", style="bold yellow")

    sorted_p = sorted(
        player_agg.items(),
        key=lambda x: sum(x[1]["shots"]) / max(len(x[1]["shots"]), 1),
        reverse=True,
    )
    for name, data in sorted_p[:12]:
        n = len(data["shots"])
        ts = sum(data["shots"])
        to = sum(data["on_target"])
        tg = sum(data["goals"])
        avg_s = ts / n if n else 0
        avg_o = to / n if n else 0
        if avg_s < 0.3:
            continue
        table.add_row(name, str(n), str(int(ts)), f"{avg_s:.1f}", str(int(to)), f"{avg_o:.1f}", str(int(tg)))
    console.print(table)


def print_summary(home_a, away_a):
    def avg(analysis, key):
        ms = analysis.get("matches", [])
        return sum(m[key] for m in ms) / len(ms) if ms else 0

    h, a = home_a["team"], away_a["team"]
    hc, ac = avg(home_a, "corners"), avg(away_a, "corners")
    hso, aso = avg(home_a, "shots_on_target"), avg(away_a, "shots_on_target")
    hs, as_ = avg(home_a, "total_shots"), avg(away_a, "total_shots")

    t = Table(title="RESUMEN ESTADÍSTICO", box=box.HEAVY, show_lines=True)
    t.add_column("Estadística", style="bold")
    t.add_column(h, justify="center", style="green")
    t.add_column(a, justify="center", style="blue")
    t.add_column("Combinado", justify="center", style="bold yellow")
    t.add_row("Prom. Corners",        f"{hc:.1f}",  f"{ac:.1f}",  f"{hc+ac:.1f}")
    t.add_row("Prom. Tiros a puerta", f"{hso:.1f}", f"{aso:.1f}", f"{hso+aso:.1f}")
    t.add_row("Prom. Tiros totales",  f"{hs:.1f}",  f"{as_:.1f}", f"{hs+as_:.1f}")
    console.print(t)

    all_players = []
    for analysis in (home_a, away_a):
        team = analysis["team"]
        player_agg = {}
        for m in analysis["matches"]:
            for name, stats in m.get("players", {}).items():
                if name not in player_agg:
                    player_agg[name] = {"shots": [], "on_target": []}
                player_agg[name]["shots"].append(stats.get("totalShots", 0))
                player_agg[name]["on_target"].append(stats.get("shotsOnTarget", 0))
        for name, data in player_agg.items():
            n = len(data["shots"])
            avg_s = sum(data["shots"]) / n if n else 0
            avg_o = sum(data["on_target"]) / n if n else 0
            if avg_s >= 1.0:
                all_players.append((name, team, avg_s, avg_o))

    all_players.sort(key=lambda x: x[2], reverse=True)
    if all_players:
        console.print()
        tp = Table(title="TOP TIRADORES (ambos equipos)", box=box.ROUNDED)
        tp.add_column("Jugador", style="bold")
        tp.add_column("Equipo")
        tp.add_column("Prom. tiros", justify="center", style="cyan")
        tp.add_column("Prom. a puerta", justify="center", style="green")
        for name, team, av, avo in all_players[:10]:
            tp.add_row(name, team, f"{av:.1f}", f"{avo:.1f}")
        console.print(tp)


def main():
    num_matches = 5
    if len(sys.argv) > 1:
        try:
            num_matches = int(sys.argv[1])
        except ValueError:
            pass

    console.print(Panel(
        "[bold]Football Stats Bot[/bold] - ESPN API (sin Chrome)\n"
        f"Analizando últimos [cyan]{num_matches}[/cyan] partidos por equipo\n"
        "Datos: corners, tiros a puerta, tiros totales, tiros por jugador",
        box=box.DOUBLE_EDGE,
    ))

    console.print("\n[bold]Ligas disponibles:[/bold]")
    for k, (name, _) in LEAGUES.items():
        console.print(f"  {k}. {name}")

    console.print("\n[bold]Selecciona liga (número):[/bold]")
    league_choice = input("> ").strip()

    if league_choice not in LEAGUES:
        console.print("[red]Opción inválida[/red]")
        return

    league_name, league_slug = LEAGUES[league_choice]
    console.print(f"\n[dim]Cargando partidos de {league_name}...[/dim]")

    upcoming = get_upcoming_matches(league_slug)
    recent = get_recent_matches(league_slug)

    if not upcoming:
        console.print("[yellow]No hay partidos próximos. Mostrando últimos terminados...[/yellow]")
        show_matches = list(reversed(recent[:20]))
    else:
        show_matches = upcoming[:30]

    console.print(f"\n[green]{len(show_matches)} partidos encontrados[/green]\n")

    for i, e in enumerate(show_matches, 1):
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
        h_score = home.get("score", "")
        a_score = away.get("score", "")
        score_str = f" [dim]({h_score}-{a_score})[/dim]" if h_score else ""
        console.print(f"  {i}. {h_name} vs {a_name} - {date_str} [{status}]{score_str}")

    console.print("\n[bold]Número del partido a analizar (q=salir):[/bold]")
    choice = input("> ").strip()

    if choice.lower() == "q":
        return

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(show_matches)):
            console.print("[red]Número inválido[/red]")
            return
    except ValueError:
        console.print("[red]Entrada inválida[/red]")
        return

    sel = show_matches[idx]
    comps = sel.get("competitions", [{}])[0]
    competitors = comps.get("competitors", [])
    home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})
    h_name = home_comp.get("team", {}).get("displayName", "?")
    a_name = away_comp.get("team", {}).get("displayName", "?")

    console.print(f"\n[bold green]>>> Analizando: {h_name} vs {a_name} <<<[/bold green]\n")

    console.print(f"[dim]Buscando últimos {num_matches} partidos de {h_name}...[/dim]")
    home_analysis = get_team_recent_stats(league_slug, h_name, recent, num_matches)
    print_team_analysis(home_analysis)
    print_player_shots(home_analysis)

    console.print(f"\n[dim]Buscando últimos {num_matches} partidos de {a_name}...[/dim]")
    away_analysis = get_team_recent_stats(league_slug, a_name, recent, num_matches)
    print_team_analysis(away_analysis)
    print_player_shots(away_analysis)

    console.print()
    print_summary(home_analysis, away_analysis)


if __name__ == "__main__":
    main()
