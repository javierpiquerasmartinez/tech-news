---
name: montador-graficos
description: Paso de Gráficos del Montador de tech-news. Decide qué rótulos de dato, infografías (tabla, pasos) y capturas de fuente van en cada bloque del Resumen semanal y en qué segundo, siguiendo estilo-edicion.md. Úsala cuando haya que "planificar los gráficos" de un Montaje.
---

# Montador · Gráficos

Los Gráficos de cada bloque **ya vienen decididos en el guion** (el Redactor los escribe y la persona editora los aprueba), cada uno con un `ancla`: las palabras en las que entra. El código los coloca solo buscando el ancla en la transcripción. **Tú entras solo para lo que no cuadra:**

- Gráficos previstos cuyo ancla no se encontró (se dijo de otra forma o se saltó).
- Bloques sin Gráficos previstos (guiones antiguos).
- Notas de feedback de la persona editora sobre la versión anterior.

Las **cabeceras de bloque, el sello y la pantalla final los pone el código**. Vocabulario en `GLOSSARY.md`.

Ejecutas los comandos **exactamente como aparecen aquí**: sin opciones extra, sin redirecciones, sin tuberías y sin encadenar comandos.

## Pasos

1. Lee `estilo-edicion.md` entero: densidad, posiciones, texto en pantalla, cuándo usar cada Gráfico.
2. `uv run tn montaje frases --semana <semana>` devuelve un JSON con:
   - `bloques`: por bloque, su `inicio` y `fin` en segundos del Corte, sus `fuentes`, `puntos_clave` y las `frases` que se dicen, cada una con su tiempo `t`;
   - `previstos_anclados`: los Gráficos del guion ya colocados. **No los repitas** en tu plan;
   - `previstos_sin_ancla`: Gráficos del guion que hay que colocar. Busca en las `frases` de su bloque el momento en que se dice lo que muestran;
   - `estructurales`: cabeceras, sello y final, ya puestos;
   - `feedback` y `plan_anterior`: notas de la persona editora y el plan de la versión anterior.
3. Decide según el caso:
   - **Sin feedback:** tu plan contiene **solo** los `previstos_sin_ancla` colocados, con sus mismos datos, y, para los bloques sin Gráficos previstos (sin `dudoso: true`), 2–4 Gráficos nuevos. Si un previsto no se dijo en absoluto, déjalo fuera y dilo en tu resumen.
   - **Con feedback:** reescribe el plan **completo**, partiendo de `plan_anterior` y aplicando las notas (mover, quitar, acortar, cambiar el texto o el tipo). Si una nota pide algo que no se arregla con Gráficos (una frase del Corte, el color de la guía…), dilo en tu resumen.
4. Que nada se pise entre sí ni con la cabecera del bloque (≈2,6 s desde su inicio), ni con los `previstos_anclados` si no estás en modo feedback.
5. Escribe el plan con **Write** en `data/borradores/graficos-<semana>.json` y guárdalo:
   - sin feedback: `uv run tn montaje graficos-plan data/borradores/graficos-<semana>.json --semana <semana>`
   - con feedback: `uv run tn montaje graficos-plan data/borradores/graficos-<semana>.json --semana <semana> --completo`

   Si la CLI lo rechaza o avisa de solapes, corrige y repite.

## Tipos y datos

```json
{"graficos": [
  {"tipo": "rotulo", "inicio": 41.2, "datos": {"etiqueta": "Versiones corregidas", "valor": "1.30.7 · 1.31.9", "detalle": "stable · mainline", "tono": "alerta"}},
  {"tipo": "tabla", "inicio": 95.0, "duracion": 9, "datos": {"titulo": "Precio por millón de tokens", "columnas": ["Modelo", "Entrada", "Salida"], "filas": [["GPT-6.2 Astra", "8 $", "40 $"], ["Gemini 4 Neon", "3 $", "15 $"]], "destacar": 1, "tiempos": [0.8, 2.4]}},
  {"tipo": "pasos", "inicio": 60.5, "duracion": 8, "datos": {"titulo": "Qué hacer hoy", "pasos": ["Comprueba tu versión con `nginx -V`", "Actualiza a 1.30.7"], "tono": "alerta"}},
  {"tipo": "captura", "inicio": 30.1, "datos": {"url": "https://…", "fuente": "wiz.io", "cita": "Frase clave de la fuente, ≤ 10 palabras"}}
]}
```

- **rotulo** (≈4 s): una cifra, versión, precio o CVE. `valor` corto (≤ 16 caracteres) y `etiqueta` que diga qué es. `tono: "alerta"` solo en seguridad.
- **tabla** (≈8 s, pantalla completa): comparativas de 2–5 filas. `tiempos`: segundo, **desde el inicio del Gráfico**, en el que se nombra cada fila.
- **pasos** (≈8 s, pantalla completa): 2–4 acciones concretas. El código entre comillas invertidas.
- **captura** (≈6 s, pantalla completa): la `url` sale de las `fuentes` del bloque. `cita` es opcional, solo si la frase está en la fuente.
- `duracion` es opcional; si la pones, que no se coma el siguiente Gráfico.

## Reglas

- **Datos solo del guion y las frases.** Nada inventado.
- **Texto corto:** ≤ 8 palabras por línea, sin repetir palabra por palabra lo que se dice.
- Como mucho **un Gráfico de pantalla completa por bloque**, salvo bloques de más de 2 minutos.
- Si un bloque no tiene nada que mostrar, mejor un rótulo que nada; si no hay ni dato, ninguno.

## Al terminar

Responde con un resumen breve: cuántos Gráficos por bloque y de qué tipo, y lo que no pudiste representar.
