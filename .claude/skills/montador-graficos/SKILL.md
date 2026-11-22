---
name: montador-graficos
description: Paso de Gráficos del Montador de tech-news. Decide qué rótulos de dato, infografías (tabla, pasos) y capturas de fuente van en cada bloque del Resumen semanal y en qué segundo, siguiendo estilo-edicion.md. Úsala cuando haya que "planificar los gráficos" de un Montaje.
---

# Montador · Gráficos

Decides los Gráficos que acompañan a la persona editora mientras habla. Las **cabeceras de bloque, el sello y la pantalla final ya los pone el código**: tú solo decides **rótulos, tablas, pasos y capturas**. Vocabulario en `GLOSSARY.md`.

Ejecutas los comandos **exactamente como aparecen aquí**: sin opciones extra, sin redirecciones, sin tuberías y sin encadenar comandos.

## Pasos

1. Lee `estilo-edicion.md` entero: densidad, posiciones, texto en pantalla, cuándo usar cada Gráfico.
2. `uv run tn montaje frases --semana <semana>` devuelve un JSON con:
   - `bloques`: por bloque, su `inicio` y `fin` en segundos del Corte, la línea `visual` y las `fuentes` del guion, sus `puntos_clave` y las `frases` que se dicen, cada una con su tiempo `t`;
   - `estructurales`: lo que ya está puesto (cabeceras, sello y final). No lo pises.
3. Para cada bloque (los que tienen `dudoso: true` déjalos sin Gráficos), elige **2–4 Gráficos** y su segundo exacto: el `t` de la frase en la que se dice lo que muestran. Que no se pisen entre sí ni con la cabecera del bloque (que ocupa ≈2,6 s desde el inicio del bloque).
4. Escribe el plan con **Write** en `data/borradores/graficos-<semana>.json` y guárdalo con `uv run tn montaje graficos-plan data/borradores/graficos-<semana>.json --semana <semana>`. Si la CLI lo rechaza, corrige y repite. Los avisos de solape también se corrigen.

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
