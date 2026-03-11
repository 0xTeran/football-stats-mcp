# Football Stats MCP 🎯

MCP server para análisis de estadísticas de fútbol orientado a apuestas deportivas. Obtiene datos en tiempo real de **ESPN API** sin necesidad de Chrome ni Selenium.

## ¿Qué datos entrega?

- **Corners** (tiros de esquina) por equipo
- **Tiros totales** y **tiros a puerta** por equipo
- **Tiros por jugador** (total, a puerta, goles)
- Partidos en curso y próximos de 15 ligas
- Resultados recientes con historial de hasta 90 días

## Herramientas MCP disponibles

| Tool | Descripción |
|------|-------------|
| `list_leagues` | Lista las 15 ligas disponibles |
| `get_upcoming_matches` | Próximos partidos de una liga |
| `get_recent_results` | Resultados recientes |
| `get_match_stats` | Stats detalladas de un partido por ID |
| `analyze_team` | Historial de un equipo (corners, tiros, jugadores) |
| `analyze_match` | Comparativa completa de dos equipos |

## Ligas soportadas

- England Premier League · Spain La Liga · Germany Bundesliga
- Italy Serie A · France Ligue 1
- UEFA Champions League · UEFA Europa League
- Argentina Liga Profesional · USA MLS · Brazil Serie A
- Portugal Primeira Liga · Netherlands Eredivisie
- Mexico Liga MX · Colombia Liga BetPlay · Chile Primera Division

---

## Opción A — Conectar al servidor remoto (sin instalar nada)

Agrega esto a `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "football-stats": {
      "type": "sse",
      "url": "http://TU_SERVIDOR_IP:8000/sse"
    }
  }
}
```

---

## Opción B — Instalar local (stdio)

### Requisitos

```bash
pip install curl-cffi mcp rich
```

### Configurar en Claude Code

```json
{
  "mcpServers": {
    "football-stats": {
      "command": "python3",
      "args": ["/ruta/al/mcp_server.py"]
    }
  }
}
```

---

## Correr el servidor HTTP/SSE propio

```bash
# Puerto 8000 (default)
python3 mcp_server.py http

# Puerto personalizado
python3 mcp_server.py http 9000
```

El servidor quedará escuchando en `http://0.0.0.0:8000/sse`.

---

## Bot interactivo en terminal

```bash
python3 bot.py
# Opcional: número de partidos históricos
python3 bot.py 7
```

---

## Uso como MCP en Claude

```
Analiza el partido Manchester City vs Arsenal en la Premier League
```

```
Dame los próximos partidos de Champions League
```

```
¿Cuántos corners promedia el Real Madrid en los últimos 5 partidos?
```

```
Muestra los tiros del partido ID:401862583 de Champions League
```

---

## Ejemplo de salida

```
Análisis de Manchester City - últimos 5 partidos:

  L Man City 3-1 Ipswich (2026-02-15) | Corners:7 T.puerta:8 T.total:18
  V Arsenal 1-2 Man City (2026-02-08) | Corners:4 T.puerta:6 T.total:14
  L Man City 2-0 Chelsea (2026-02-01) | Corners:6 T.puerta:5 T.total:16

PROMEDIOS:
  Corners:        5.7
  Tiros a puerta: 6.3
  Tiros totales:  16.1

TOP TIRADORES:
  Erling Haaland: 4.2 tiros/pj (2.8 a puerta, 3 goles)
  Phil Foden: 2.1 tiros/pj (1.2 a puerta, 1 goles)
```

---

## Fuente de datos

API pública de **ESPN** (`site.api.espn.com`). No requiere API key ni Chrome.

> xG (expected goals) no está disponible en ESPN.

## Archivos

```
football-stats-mcp/
├── mcp_server.py   # Servidor MCP (stdio + HTTP/SSE)
├── bot.py          # Bot interactivo en terminal
└── requirements.txt
```
