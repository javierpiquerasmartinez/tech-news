# Guía de estilo de edición · JP Dev

Criterio visual con el que el Montador monta los vídeos. La mantiene la persona editora; el Montador la lee en cada Montaje y solo **propone** cambios a partir de las Fichas de feedback (`tn estilo revisar`), nunca la reescribe. Versión 1 (2026-11-22): punto de partida, se afina vídeo a vídeo.

## Identidad

- **Canal:** JP Dev · **lema:** «Noticias DEV cada semana».
- **Logo:** la J (rectángulo con la esquina inferior izquierda redondeada) y el círculo, en blanco roto sobre azul noche (`assets/youtube/`).
- **Paleta:**

| Uso | Color |
|---|---|
| Fondo de Gráficos a pantalla completa | `#070D1A` (azul noche) |
| Texto principal | `#F8F6F3` (blanco roto) |
| Texto secundario, fuentes, fechas | `#9AA3B2` (gris) |
| Acento: cifras, versiones, lo que hay que recordar | `#C6FF3D` (lima) |
| Alerta (solo seguridad: CVE, "parchea ya") | `#FF5A4E` (rojo) |

- **Tipografía (provisional, por confirmar):** Inter. Black para cifras grandes, Bold para titulares, Regular para texto. Código y comandos en monoespaciada (JetBrains Mono).

## Formato

- Horizontal **1920×1080, 30 fps**. Sin subtítulos quemados: YouTube genera los suyos.
- **Zona segura:** nada importante a menos de 80 px del borde.

## Estructura de un Resumen semanal

1. **Gancho** (≈30 s): solo la persona editora, sin Gráficos.
2. **Sello de marca** (≈3 s): el logo se construye (la J y el círculo encajan) y aparece «Noticias DEV cada semana». Whoosh suave.
3. **Bloques**, uno por Historia, cada uno con su **cabecera de bloque**.
4. **Cierre** (≈30 s): solo la persona editora.
5. **Pantalla final** (≈15 s): fondo azul noche con hueco para los dos elementos de pantalla final de YouTube (vídeo siguiente y suscribirse) y el logo.

## Los cuatro Gráficos

| Gráfico | Cuándo | Dónde | Persona editora |
|---|---|---|---|
| **Cabecera de bloque** | Al empezar cada bloque, ≈2,5 s | Tercio inferior izquierdo: número en lima + título del bloque | A pantalla completa |
| **Rótulo de dato** | Cuando se dice una cifra, versión, precio o CVE | Tercio inferior o lateral derecho; la cifra en lima (rojo si es de seguridad) | A pantalla completa |
| **Infografía animada** | Comparativas (precios de modelos), pasos ("qué hacer hoy"), antes/después | Pantalla completa sobre azul noche | En un **círculo** abajo a la derecha (eco del círculo del logo) |
| **Captura de fuente** | Al citar el anuncio, el aviso o el post original | Pantalla completa, con zoom lento hacia la frase clave resaltada en lima | En el círculo |

- Máximo **un Gráfico a la vez**. Ningún Gráfico tapa la cara de la persona editora a pantalla completa.
- **Densidad:** entre 2 y 4 Gráficos por bloque. Un plano sin nada encima no debería durar más de ≈20 s.
- **Texto en pantalla:** frases cortas (≤ 8 palabras); nunca leer en pantalla lo que se está diciendo palabra por palabra.

## Movimiento

- Entradas y salidas de 0,3–0,4 s con aceleración suave (ease-out al entrar, ease-in al salir). Nada de rebotes ni giros.
- Las infografías se construyen por partes al ritmo de la voz (cada fila o paso aparece cuando se menciona).
- Transición entre bloques: corte limpio con whoosh, o barrido azul noche de 0,4 s.

## Ritmo y corte

- Se queda la **última Toma buena** de cada frase; fuera repeticiones, muletillas largas y silencios de más de 0,4 s.
- Respiraciones naturales cortas se mantienen: el vídeo no debe sonar acelerado.
- Un "salto" en el plano de cámara por un corte se tapa, si se puede, con un Gráfico o con un zoom leve (105 %) alternando entre cortes.

## Sonido

- Voz limpia y normalizada a −14 LUFS.
- **Música de fondo** muy baja (unos −28 dB por debajo de la voz), de la Biblioteca de audio de YouTube; se apaga en el gancho y vuelve con el sello de marca.
- **Efectos:** whoosh en transiciones y en la entrada de infografías, click o pop suave en la entrada de rótulos. Discretos: si se notan más que la voz, sobran.

## Lo que aún no sabemos

Se rellena con las Fichas de feedback: tipografía definitiva, si el acento lima funciona, densidad real de Gráficos, ritmo.
