# Montaje en CapCut con capcut-kit como dependencia externa

El Montador deja un proyecto de CapCut (no un MP4 cerrado) para que la persona editora pueda retocarlo a mano mientras construimos la Guía de estilo de edición. Para escribir y manejar proyectos de CapCut, que no tiene API, usamos [capcut-kit](https://github.com/matt-j-penny/capcut-kit) **clonado fuera de este repo** (`~/git/jpdev/capcut-kit`, fijado a un commit) y llamado como programa externo (`uv run capcut-bridge.py …`) desde un único módulo de `tn`. No lo copiamos ni lo reescribimos: no tiene licencia (este repo es público) y concentra arreglos frágiles ya resueltos (caché `Timelines/`, sandbox de `~/Movies`, `source_timerange` nulo, pantalla modal de compartir). Los Gráficos se crean aparte con HyperFrames (HTML → vídeo), así que pasar a render directo sin CapCut no exigiría rehacerlos.

## Consequences

- El Montador necesita CapCut instalado en este Mac y las plantillas `capcut-templates/` que el kit no incluye.
- La vía "live" del kit depende de identificadores internos de CapCut que pueden cambiar con una actualización: tras actualizar CapCut, `capcut-bridge.py doctor` antes de montar.
- Una vez retocado a mano un Montaje, el Montador solo puede **añadir** (Gráficos, textos), nunca reconstruirlo.
