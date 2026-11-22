# Perfil editorial

Criterio con el que el Editor puntúa las Historias. Lo mantiene la persona editora; el Editor lo lee en cada Ejecución y solo **propone** cambios (`tn perfil revisar`), nunca lo reescribe.

## El canal

- Contenido **en español** para ingenieros de software en activo, de nivel mid a senior, de España y Latinoamérica.
- Perfil **full stack generalista**. La persona editora trabaja sobre todo con MERN (MongoDB, Express, React, Node), pero el canal no se encasilla en un stack: cubre lo que importa a cualquier dev full stack.

## Peso de cada área

De más a menos peso:

1. **IA aplicada al desarrollo**: modelos, agentes, herramientas de código con IA, evals, cómo cambia el trabajo de programar.
2. **Desarrollo y herramientas**: lenguajes, frameworks (front y back), runtimes, bases de datos, open source relevante, herramientas de developer experience.
3. **Seguridad**: vulnerabilidades críticas, incidentes, cadena de suministro (npm, PyPI…), sobre todo lo que obliga a actuar.
4. **Cloud / DevOps / plataforma**: Kubernetes, CI/CD, proveedores cloud, observabilidad, contenedores.
5. **Industria tech**: movimientos de grandes empresas y regulación de IA, **solo cuando afecta a quien desarrolla**.

IA y desarrollo son el núcleo. Seguridad y DevOps entran con fuerza cuando hay algo gordo.

## Lo que puntúa bajo por defecto

- Gadgets y electrónica de consumo, videojuegos.
- Espacio y ciencia sin relación con el software.
- Cripto.
- Rondas de financiación, valoraciones, cotizaciones.
- Política y cotilleo corporativo (quién dimite, quién vuelve).
- Autopromoción de las propias newsletters (encuestas, comunidades, formularios).

**Excepción:** sube si afecta directamente a quien desarrolla (p. ej. una demanda o una ley que cambia cómo se pueden usar los modelos, una adquisición que cambia la licencia de una herramienta muy usada).

## Las tres puntuaciones (0–10)

- **Urgencia**: ¿hay que hablar de ello *hoy*, antes que nadie? Es alta para lanzamientos importantes, vulnerabilidades explotadas y cambios que obligan a actuar. Cae rápido con los días.
- **Valor didáctico**: ¿da para un vídeo explicativo de 10 minutos que siga siendo útil dentro de un mes? Es alta para conceptos nuevos, técnicas, releases con cambios de fondo y temas que mucha gente no entiende bien. Sube un poco si toca el stack de la persona editora (JavaScript/TypeScript, React, Node, MongoDB), porque ahí habla con más autoridad.
- **Peso semanal**: ¿tiene que estar en el Resumen semanal? Es alto para lo que un dev full stack debería saber sí o sí al acabar la semana.

Una línea de justificación por puntuación, concreta ("PostgreSQL es la BD más usada en back; release mayor con cambios en…"), no genérica ("es relevante").

## Calibración

Puntuaciones de referencia (0–3) dadas por la persona editora el 2026-11-22:

| Noticia | Nota | Por qué |
|---|---|---|
| Unauthenticated Remote Code Execution in NGINX | 3 | Urgente: software ubicuo, obliga a actuar |
| PostgreSQL 19 Released! | 2–3 | Didáctico: release mayor de una BD central |
| Meet the New Docker, Built to Run on Trust | 2 | Herramienta que usa todo el mundo |
| Actual curl rewrites in rust | 2 | Buen tema de opinión |
| Teach AI coding assistants your design system with Markdown | 2 | Didáctico y práctico |
| OpenAI's Performance Factory keeps ChatGPT fast | 1–2 | Interesante, poco accionable |
| DeepSeek V3 in pure JAX (GitHub Repo) | 1 | Nicho |
| Squircles | 0–1 | Curiosidad |
| Just How Big Is 'Grand Theft Auto VI'? | 0 | Videojuegos |
| Some Nvidia directors continue push to bring Huang back | 0 | Cotilleo corporativo |

## Historia bomba

Listón alto, del orden de 1–3 al mes. Es mejor avisar poco y bien.

- **Modelo puntero nuevo** de OpenAI, Anthropic, Google o Meta.
- **Vulnerabilidad crítica explotada masivamente** en software casi universal (nivel Log4Shell o xz).
- **Caída global** (nivel CrowdStrike o una región entera de AWS).
- **Compra o cambio de licencia o precio** que afecta a millones de devs (nivel GitHub, Docker o Terraform).

Una vulnerabilidad grave *sin* explotación masiva confirmada es urgencia alta, pero no bomba.

## Enfoque

Depende de la noticia, con estas prioridades:

1. **Práctico** por defecto: qué significa para ti como dev y qué deberías hacer.
2. **Análisis de industria** para el Resumen semanal y los posts de opinión: por qué pasa y hacia dónde va.
3. "Qué ha salido" a secas, nunca solo: no diferencia el canal.
