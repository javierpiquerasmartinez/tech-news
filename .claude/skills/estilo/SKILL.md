---
name: estilo
description: Revisión de la Guía de estilo de edición de tech-news. Lee las Fichas de feedback de los Montajes y, si las notas se repiten, propone cambios a estilo-edicion.md sin aplicarlos. Úsala cuando haya que "revisar la guía de estilo" o "afinar la edición".
---

# Revisión de la Guía de estilo de edición

El Montador trabaja con `estilo-edicion.md`. La persona editora deja notas sobre cada Montaje en su Ficha de feedback. Tu trabajo es encontrar **patrones** en esas notas y **proponer** cómo ajustar la guía para que los próximos Montajes salgan mejor a la primera.

**Nunca cambias `estilo-edicion.md`.** Solo dejas una propuesta que la persona editora acepta o rechaza.

Ejecutas los comandos **exactamente como aparecen aquí**: sin opciones extra, sin redirecciones, sin tuberías y sin encadenar comandos.

## Pasos

1. Lee `estilo-edicion.md` entero, incluida la sección «Lo que aún no sabemos».
2. `uv run tn estilo notas` devuelve un JSON con las notas desde la última revisión (semana, versión, minuto y texto).
3. Busca **patrones**: un cambio necesita al menos **3 notas** que apunten en la misma dirección, mejor si son de semanas distintas. Por ejemplo:
   - varias notas de "el rótulo tapa la cara" → mover o reducir los rótulos;
   - "demasiados Gráficos" o "se me ve poco" → bajar la densidad;
   - "la tipografía no me convence" con una alternativa concreta → cambiarla.

   Las notas que **resuelven una incógnita** de «Lo que aún no sabemos» se pasan a la sección que corresponde.
4. Si **no hay patrones suficientes**, no escribas nada: explica por qué y termina.
5. Si los hay, escribe con **Write** la guía completa con los cambios en `data/borradores/estilo-edicion.propuesto.md`. Cambia solo lo necesario y respeta la estructura; el resto queda idéntico.

Si un cambio afecta a colores, tipografía o medidas, dilo en tu resumen: las plantillas (`graficos/comun.css`) también tendrán que cambiar al aceptarlo.

## Al terminar

Responde en español con la lista de cambios propuestos: qué cambia, en qué sección y en qué notas se basa (semana y minuto). Añade al final:

> Para ver el diff: `uv run tn estilo diff` · aceptar: `uv run tn estilo aceptar` · rechazar: `uv run tn estilo rechazar`
