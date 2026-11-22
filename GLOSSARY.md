# tech-news

Sistema editorial que vigila las novedades de la industria del software (IA, desarrollo, seguridad, DevOps…) y propone contenido en español para YouTube y LinkedIn. El sistema propone; la persona editora decide qué se publica.

## Language

### Entrada

**Fuente**:
Un origen de información que vigilamos: una newsletter, un blog oficial, un agregador, un changelog.
_Avoid_: Feed, canal, origen

**Item**:
Una entrada concreta publicada por una Fuente (un enlace de una newsletter, un post de un blog). Es lo que se recoge, sin interpretar.
_Avoid_: Noticia, artículo, entrada

**Historia**:
Un acontecimiento real del mundo, deduplicado, que agrupa todos los Items que hablan de él. La relevancia se mide siempre sobre Historias, nunca sobre Items.
_Avoid_: Noticia, evento, tema

**Historia bomba**:
Una Historia tan impactante que merece contenido el mismo día, antes que la competencia.
_Avoid_: Breaking news, noticia boom, urgente

### Criterio editorial

**Urgencia**:
Puntuación de una Historia que mide si hay que hablar de ella hoy. Una Urgencia muy alta convierte la Historia en Historia bomba.
_Avoid_: Prioridad, relevancia

**Valor didáctico**:
Puntuación de una Historia que mide si da para un Vídeo didáctico.
_Avoid_: Interés, profundidad

**Peso semanal**:
Puntuación de una Historia que mide si tiene que aparecer en el Resumen semanal.
_Avoid_: Importancia, relevancia

**Perfil editorial**:
Los criterios de la persona editora (temas que pesan, temas que aburren, enfoque) contra los que se puntúan las Historias.
_Avoid_: Preferencias, configuración

**Semana editorial**:
El periodo de viernes a jueves que cubre un Resumen semanal.
_Avoid_: Semana natural

### Roles

**Recolector**:
El rol que recoge Items de Fuentes con formato estable de forma mecánica. Solo añade Items, nunca interpreta.
_Avoid_: Scraper, crawler, ingestor

**Explorador**:
El rol que busca Items que el Recolector no alcanza: navega, sigue enlaces y detecta huecos de cobertura. Solo añade Items, nunca interpreta.
_Avoid_: Investigador, buscador

**Editor**:
El rol que agrupa Items en Historias, las puntúa contra el Perfil editorial y detecta Historias bomba.
_Avoid_: Curador, clasificador

**Redactor**:
El rol que convierte Historias en Propuestas de cada Formato.
_Avoid_: Generador, escritor

**Montador**:
El rol que convierte un guion aprobado y la grabación de la persona editora en un vídeo editado. Pertenece a la fase 2.
_Avoid_: Editor de vídeo (choca con Editor)

**Ejecución**:
Una pasada registrada de uno o varios roles, lanzada por horario, a mano o desde una conversación.
_Avoid_: Job, run, tarea

### Revisión

**Historia destacada**:
Una Historia que la persona editora fuerza a usar aunque su puntuación no lo justifique.
_Avoid_: Favorita, fijada

**Historia descartada**:
Una Historia que la persona editora retira, con un motivo opcional que alimenta el Perfil editorial.
_Avoid_: Borrada, archivada

**Historia usada**:
Una Historia en la que se basa al menos una Propuesta aprobada. Que el Redactor la use en un borrador no basta.
_Avoid_: Publicada (eso es estado de Propuesta)

**Paquete semanal**:
El conjunto de Propuestas que el Redactor entrega para una Semana editorial.
_Avoid_: Entrega, batch

### Salida

**Propuesta**:
Una idea de contenido concreta, de un Formato concreto, construida sobre una o varias Historias. Nunca se publica sin aprobación humana.
_Avoid_: Idea, borrador, pieza

**Formato**:
El tipo de pieza que se propone: Resumen semanal (vídeo), Vídeo didáctico, Vídeo bomba o Post de LinkedIn.
_Avoid_: Tipo de contenido, plantilla

### Montaje

**Grabación**:
El vídeo en bruto que graba la persona editora leyendo un guion aprobado, de un tirón, con sus repeticiones y silencios.
_Avoid_: Raw, metraje, footage

**Toma**:
Cada intento de decir una misma frase del guion dentro de una Grabación. El Montador se queda con la mejor y descarta el resto.
_Avoid_: Repetición, retake

**Corte**:
La lista de tramos de la Grabación que sobreviven al montaje, en orden.
_Avoid_: EDL, rough cut

**Gráfico**:
Una pieza visual que se superpone a la Grabación: cabecera de bloque, rótulo de dato, infografía animada o captura de fuente.
_Avoid_: Overlay, motion graphic, visual

**Montaje**:
El resultado del Montador para un guion: un proyecto de CapCut con el Corte y los Gráficos colocados, listo para retocar y exportar.
_Avoid_: Edición, draft, proyecto

**Guía de estilo de edición**:
El criterio visual del canal (paleta, tipografía, ritmo, cuándo usar cada Gráfico) con el que trabaja el Montador. La mantiene la persona editora; el Montador solo propone cambios.
_Avoid_: Brand kit, preset

**Ficha de feedback**:
Las notas de la persona editora sobre un Montaje concreto, con el minuto al que se refiere cada una.
_Avoid_: Comentarios, review

