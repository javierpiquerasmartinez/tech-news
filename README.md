# tech-news

Sistema editorial de **JP Dev** («Noticias DEV cada semana»): vigila a diario las novedades de la industria del software (IA, desarrollo, seguridad, DevOps), las agrupa y puntúa, propone guiones y posts en español y monta el vídeo semanal en CapCut. **El sistema propone; nada se publica sin aprobación humana.**

```
Fuentes ─► Recolector + Explorador ─► Items ─► Editor ─► Historias puntuadas
                                                             │
           Tú apruebas ◄─ Propuestas (guion, posts, ideas) ◄─ Redactor
               │
           Grabación ─► Montador ─► proyecto de CapCut + vista previa ─► tú retocas y publicas
```

## Qué hace

- **Cada día (16:00):** recoge de ~30 Fuentes (TLDR, Hacker News, blogs oficiales, avisos de seguridad…), agrupa los Items en Historias y las puntúa (Urgencia, Valor didáctico, Peso semanal) según [`perfil-editorial.md`](perfil-editorial.md). Si detecta una Historia bomba, avisa por Telegram con un Short preparado.
- **Lunes a miércoles (16:30):** un post de LinkedIn sobre lo más fuerte de las últimas 48 h.
- **Jueves (22:00):** el guion del Resumen semanal, con sus Gráficos previstos, e ideas de Vídeo didáctico.
- **Montaje (a mano):** de la grabación al proyecto de CapCut: audio limpio, transcripción local, mejor toma de cada frase, Gráficos animados con la identidad del canal, círculo de la persona editora, música y efectos.
- **Domingos:** propone mejoras al Perfil editorial y a la [Guía de estilo de edición](estilo-edicion.md) a partir de tus correcciones.

**Todo dato publicado se contrasta** con la fuente oficial o con dos fuentes independientes; cada guion y post lleva una tabla de verificación que se audita antes de aprobar.

## Documentación

| Qué | Dónde |
|---|---|
| Cómo funciona todo: flujos, horarios, comandos, ficheros | [`docs/arnes.md`](docs/arnes.md) |
| Vocabulario (Item, Historia, Propuesta, Montaje…) | [`GLOSSARY.md`](GLOSSARY.md) |
| Decisiones de arquitectura | [`docs/adr/`](docs/adr/) |
| Criterio editorial · voz · estilo de edición | [`perfil-editorial.md`](perfil-editorial.md) · [`voz.md`](voz.md) · [`estilo-edicion.md`](estilo-edicion.md) |
| Catálogo de Fuentes | [`fuentes.yaml`](fuentes.yaml) · investigación en [`docs/research/fuentes.md`](docs/research/fuentes.md) |
| Para agentes de código | [`AGENTS.md`](AGENTS.md) |

## Requisitos

- **macOS** (Apple Silicon recomendado: la transcripción usa MLX). Todo corre en local, sin servidor ([ADR-0002](docs/adr/0002-ejecucion-local-sin-despliegue.md)).
- [`uv`](https://docs.astral.sh/uv/), `ffmpeg`, `node`/`npx`.
- [Claude Code](https://claude.com/claude-code) con sesión iniciada: los roles Editor, Explorador, Redactor y Montador son skills que se lanzan con `claude -p`.
- Para el Montador: **CapCut** de escritorio y [capcut-kit](https://github.com/matt-j-penny/capcut-kit) clonado fuera de este repo ([ADR-0005](docs/adr/0005-montaje-en-capcut-con-capcut-kit-externo.md)).
- Opcional: un bot de Telegram para los avisos.

## Puesta en marcha

```bash
uv sync                                   # dependencias de Python
(cd graficos && npm install)              # GSAP para las plantillas de Gráficos
cp .env.example .env                      # y rellena lo que uses (Telegram, Gemini…)
uv run tn diagnostico                     # qué falta
```

Avisos por Telegram: crea un bot con @BotFather, pon su token en `.env` (`TN_TELEGRAM_TOKEN`), escríbele algo y:

```bash
uv run tn avisos vincular && uv run tn avisos prueba
```

Tareas programadas (LaunchAgents de macOS):

```bash
uv run tn horarios instalar
uv run tn horarios estado
```

Montador (una vez):

```bash
git clone https://github.com/matt-j-penny/capcut-kit ~/git/jpdev/capcut-kit
uv run tn montaje plantillas --desde "<un proyecto de CapCut con un texto>"
uv run tn montaje requisitos
```

## Uso diario

```bash
uv run tn ui                                    # web local: Historias, Propuestas, Fuentes, Ejecuciones
uv run tn diario                                # lanzar el día ahora
uv run tn historias --dias 1                    # qué hay hoy
uv run tn redactar --post                       # el post de LinkedIn de hoy
uv run tn redactar --resumen                    # el guion del vídeo semanal
uv run tn montar --semana 2026-11-13 --hasta revisar   # montar el vídeo tras grabarlo
uv run tn montaje feedback --semana 2026-11-13 "02:15 el rótulo tapa la barbilla"
```

`uv run tn --help` lista todos los comandos. La referencia completa, con qué se puede hacer desde la CLI, desde la web o hablando con Claude Code, está en [`docs/arnes.md` §7](docs/arnes.md).

## Datos y privacidad

El repo es público, así que lo que es contenido o datos **no se versiona**:

- `data/`: base de datos SQLite (Items, Historias, Ejecuciones), borradores y registros.
- `semanas/`: Propuestas (guiones y posts) antes de publicarse.
- `.env`: secretos (token de Telegram, clave de Gemini).

Una copia diaria comprimida de todo ello va a `~/Documents/tech-news-respaldos` (`uv run tn respaldar`). Los montajes viven en `~/Movies/jpdev/`.

## Desarrollo

```bash
uv run pytest
```

Los tests no usan la red: los parsers se prueban con fixtures en `tests/fixtures/`. Código en `src/tn/`, skills de los agentes en `.claude/skills/`, plantillas de Gráficos en `graficos/`.
