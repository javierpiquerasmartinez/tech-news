---
name: perfil
description: Revisión semanal del Perfil editorial de tech-news. Lee las correcciones de la persona editora (descartes, destacados, puntuaciones corregidas, fusiones) y, si muestran un patrón claro, propone cambios a perfil-editorial.md sin aplicarlos. Úsala cuando haya que "revisar el perfil" o "afinar el criterio del Editor".
---

# Revisión del Perfil editorial

El Editor puntúa contra `perfil-editorial.md`. Cada vez que la persona editora le corrige (descarta, destaca, cambia una puntuación), queda una **decisión**. Tu trabajo es encontrar patrones en esas decisiones y **proponer** cómo ajustar el perfil para que el Editor acierte más.

**Nunca cambias `perfil-editorial.md`.** Solo dejas una propuesta que la persona editora acepta o rechaza.

Ejecutas los comandos **exactamente como aparecen aquí**: sin opciones extra, sin redirecciones, sin tuberías y sin encadenar comandos.

## Pasos

1. Lee `perfil-editorial.md` entero.
2. `uv run tn perfil decisiones`: JSON con las decisiones desde la última revisión. Cada una trae la acción, el detalle (motivo del descarte, puntuaciones antes y después), y el título, el área y las puntuaciones de la Historia.
3. Busca **patrones**, no casos sueltos. Un cambio necesita al menos **3 decisiones** que apunten en la misma dirección. Ejemplos:
   - varios descartes "no me interesa el tema" del mismo tipo → añadirlo a "Lo que puntúa bajo";
   - Valor didáctico subido a mano en el mismo tipo de Historia → reflejarlo en la definición de esa puntuación;
   - Historias destacadas de un área → subir esa área;
   - una corrección clara sobre una noticia concreta → añadirla a la tabla de "Calibración", con la fecha de hoy.
4. Si **no hay patrones suficientes**, no escribas nada. Responde explicando por qué y termina.
5. Si los hay, escribe con **Write** el perfil completo con los cambios en `data/borradores/perfil-editorial.propuesto.md`. Cambia solo lo necesario y respeta la estructura y el tono del documento; el resto queda idéntico.

## Al terminar

Responde en español con la lista de cambios propuestos. Para cada uno: qué cambia, en qué sección y en qué decisiones se basa (ids de Historia). Añade al final:

> Para ver el diff: `uv run tn perfil diff` · aceptar: `uv run tn perfil aceptar` · rechazar: `uv run tn perfil rechazar`
