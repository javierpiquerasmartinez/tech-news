# Investigación de fuentes de noticias tech

Fecha de la investigación: 2026-11-22. Solo hechos; no contiene decisiones de diseño.

Leyenda:

- **Verificado**: URL descargada el 2026-11-22 con HTTP 200 y contenido válido (RSS/Atom con items recientes, o JSON parseable). Se indica la fecha del item más reciente observado cuando aplica.
- **No verificado**: URL conocida pero no comprobada o que falló en la prueba.
- **Velocidad** = útil para detectar una "historia bomba" en horas. **Profundidad** = útil para análisis/contexto.

---

## Parte 1 — TLDR (tldr.tech)

### 1.1 Newsletters existentes (según https://tldr.tech/newsletters)

La página lista 14 newsletters. "TLDR WebDev" ya **no existe como tal**: `https://tldr.tech/webdev/2026-11-20` responde `307 → /dev/2026-11-20` y su RSS devuelve el feed de "TLDR Dev".

Cadencia deducida de las fechas de los 20 últimos items de cada RSS (días de la semana observados):

| Newsletter | Slug | Tema | Cadencia observada | Relevancia para el proyecto |
|---|---|---|---|---|
| TLDR (Startups, Tech & Programming) | `tech` | Tech general, startups, programación | Diaria L–V | Alta |
| TLDR AI | `ai` | Lanzamientos, investigación IA/ML | Diaria L–V | Alta |
| TLDR Dev (absorbe WebDev) | `dev` | Frontend, backend, full stack | Diaria L–V | Alta |
| TLDR InfoSec | `infosec` | Seguridad | Diaria L–V | Alta |
| TLDR DevOps | `devops` | DevOps, cloud | L / X / V | Alta |
| TLDR Data | `data` | Data engineering, data science | L / J | Media-alta |
| TLDR IT | `it` | Estrategia IT, cloud, seguridad corporativa | Diaria L–V | Media |
| TLDR Hardware | `hardware` | Robótica, semis, hardware | L / X / V | Media |
| TLDR Founders | `founders` | Startups | Diaria L–V | Baja |
| TLDR Product | `product` | Product management | M / V | Baja |
| TLDR Design | `design` | Diseño | Diaria L–V | Baja |
| TLDR Marketing | `marketing` | Marketing | Diaria L–V | Baja |
| TLDR Crypto | `crypto` | Crypto/Web3 | Diaria L–V | Baja |
| TLDR Fintech | `fintech` | Fintech | L / J | Baja |

No hay ediciones en sábado ni domingo en ningún feed.

### 1.2 Acceso web: archivo por fecha

- **Patrón de URL de edición**: `https://tldr.tech/{slug}/{YYYY-MM-DD}` (verificado: `/ai/2026-11-20`, `/tech/2026-11-20`, `/it/2026-11-20`).
- **Índice de archivo**: `https://tldr.tech/{slug}/archives` (verificado para `ai`).
- **Cuidado — soft 404**: una fecha sin edición (p. ej. `/ai/2026-11-21`, sábado, o `/ai/2026-11-23`, futura) devuelve **HTTP 200** con la landing de la newsletter (`<title>AI Newsletter: TLDR AI - Free, 5 Minutes`). Hay que detectar la ausencia de edición por contenido (p. ej. ausencia del encabezado `TLDR AI 2026-11-20` o de `<article>`), no por código HTTP.
- **Cache**: la página se sirve desde Vercel con `cache-control: private, no-cache, no-store` (renderizado dinámico).
- **Estructura HTML** (edición AI 2026-11-20): server-side rendered (no requiere JS). Secciones con `<h3 class="text-center font-bold">` (p. ej. "Headlines & Launches", "Deep Dives & Analysis", "Engineering & Research", "Miscellaneous", "Quick Links"), y cada noticia es un `<article>` con `<h3>Título (N minute read)</h3>`, un enlace al artículo original con `?utm_source=tldr{slug}` y un párrafo de resumen de 1–4 frases.
- **Patrocinios**: están en la web igual que en el email, marcados con `(Sponsor)` en el título; los enlaces de sponsor llevan parámetros UTM largos y `utm_medium=newsletter`. También aparece contenido promocional propio de TLDR ("TLDR Community", formularios Typeform). Ambos son fácilmente filtrables por el sufijo `(Sponsor)` o el dominio.
- **Sitemaps**: `https://tldr.tech/sitemap.xml` (landings y archivos) y `https://tldr.tech/story/sitemap.xml` (páginas `/story/{uuid}` por noticia individual).

### 1.3 RSS

- **Existe RSS por newsletter**: `https://tldr.tech/api/rss/{slug}` (verificado para los 14 slugs + `webdev`, que es alias de `dev`).
- Contenido del feed: **solo título de la edición (las 3 noticias destacadas con emojis), enlace a la edición y fecha** (`pubDate` a las 00:00 GMT del día). **No incluye `<description>` ni el contenido** de las noticias. Últimos 20 items.
- Uso práctico: el RSS sirve como **señal de "hay edición nueva"**; luego hay que descargar la página HTML de la edición para obtener noticias, resúmenes y enlaces.
- `https://tldr.tech/rss` (el `atom:link self` declarado en los feeds) devolvió 429 en la prueba: no fiable.

### 1.4 Web vs email (comparación real)

Comparado el email "TLDR IT 2026-11-20" (recibido en Gmail a las 13:17:55 UTC) con `https://tldr.tech/it/2026-11-20`:

- **Mismas 12 piezas** (11 noticias + 1 sponsor), mismos enlaces de destino y mismos resúmenes. El orden dentro de algunas secciones difiere ligeramente (p. ej. la web pone Palo Alto antes que Microsoft/Intel; Quick Links aparecen invertidos).
- **Solo en el email**: preheader (texto de vista previa), cabecera "Sign Up | Advertise | View Online", bloques "Want to advertise in TLDR?" y "Want to work at TLDR?" (empleo/referidos), firma con los nombres de los editores, enlaces de gestión de suscripción y baja. Nada de esto es contenido noticioso.
- **Solo en la web**: navegación, contador de lectores, enlaces de comunidad.
- Conclusión factual: para la extracción de noticias, **la web contiene todo el contenido editorial del email**.

### 1.5 Horario de envío y disponibilidad

- Horas de recepción observadas en el buzón del usuario (últimos 14 días, 3 newsletters suscritas): ~**11:12 UTC**, ~**13:17 UTC** y ~**14:13 UTC** según la newsletter (≈ 06:12, 08:17 y 09:13 hora del Este de EE. UU.). Cada newsletter mantiene una hora estable (variación de ±1 min).
- **No verificado**: el desfase exacto entre envío del email y publicación en la web. La edición del día anterior ya estaba disponible el 2026-11-22 y el `pubDate` del RSS es medianoche del día de edición, así que el RSS no da la hora real. Para medirlo habría que sondear la URL del día en torno a la hora de envío un día laborable.

### 1.6 Restricciones (robots / términos / rate limit)

- `robots.txt`: `User-Agent: * Allow: /`, solo se deshabilitan `/subscribed`, `/confirmed`, `/manage`, `/info`, `/finish`. Las ediciones, archivos y `/api/rss/*` están permitidos.
- Términos de servicio (`https://tldr.tech/terms`): no contienen cláusulas sobre scraping, crawling o uso automatizado (búsqueda de "scrap", "crawl", "robot", "automat", "reproduc", "commercial": sin coincidencias). Sí hay cláusula de copyright/DMCA genérica. Los resúmenes son texto de TLDR: reproducirlos literalmente en contenido propio sería un tema de derechos de autor, no de acceso.
- **Rate limiting agresivo**: varias peticiones seguidas (~1/s) devolvieron **HTTP 429** (`application/json`) en `/api/rss/*` y `/rss`. Con pausas de 2–5 s no hubo problemas. Conviene espaciar peticiones y cachear.

---

## Parte 2 — Otras fuentes

### 2.1 Agregadores

| Fuente | URL | Tema | Cadencia | Señal | Acceso (verificado 2026-11-22) | Velocidad / Profundidad |
|---|---|---|---|---|---|---|
| Hacker News (portada) | https://news.ycombinator.com | Tech/dev general | Continua | Alta | RSS `https://hnrss.org/frontpage` (✅, 1 fallo 502 transitorio); API oficial `https://hacker-news.firebaseio.com/v0/topstories.json` (✅ JSON, 500 ids); Algolia `https://hn.algolia.com/api/v1/search?tags=front_page` (✅) | **Velocidad** |
| HN filtrado por puntos | https://hnrss.org/newest?points=100 | Idem | Continua | Alta | RSS ✅ (también `/best` ✅). Permite umbral de puntos | **Velocidad** |
| Lobsters | https://lobste.rs | Programación, sistemas | Continua | Alta | RSS `https://lobste.rs/rss` ✅; JSON `https://lobste.rs/hottest.json` ✅ | Velocidad |
| Techmeme | https://www.techmeme.com | Industria tech | Continua | Alta | RSS `https://www.techmeme.com/feed.xml` ✅ | **Velocidad** |
| GitHub Trending | https://github.com/trending | Repos en auge | Diaria | Media | **Sin RSS ni API oficial** (`/trending.atom` → 406). Requiere scraping del HTML (200 ✅) | Velocidad (proyectos virales) |
| Reddit (r/programming, r/LocalLLaMA, r/netsec, r/MachineLearning, r/devops) | https://www.reddit.com | Comunidades | Continua | Media | **Bloqueado sin autenticación**: `.rss` → 404/429, `old.reddit` → HTML, `.json` → 403. Requiere app OAuth de la API de Reddit (uso comercial requiere acuerdo con Reddit) | Velocidad (r/LocalLLaMA es muy rápido en releases de modelos) |
| Hugging Face Daily Papers | https://huggingface.co/papers | Papers IA | Diaria | Alta | API `https://huggingface.co/api/daily_papers` ✅ (JSON, 50) | Profundidad |
| Hugging Face modelos trending | https://huggingface.co/models | Modelos abiertos | Continua | Media | API `https://huggingface.co/api/models?sort=trendingScore` ✅ | Velocidad (lanzamientos open-weight) |
| dev.to | https://dev.to | Dev comunidad | Continua | Media-baja | RSS `https://dev.to/feed` ✅ | — |
| Changelog News | https://changelog.com/news | Open source/dev | Semanal | Media | RSS `https://changelog.com/news/feed` ✅ | Profundidad |

### 2.2 Newsletters y blogs de alta señal

| Fuente | URL | Tema | Cadencia | Señal | Acceso | Velocidad / Profundidad |
|---|---|---|---|---|---|---|
| Simon Willison's Weblog | https://simonwillison.net | IA aplicada, LLMs, dev | Varias/día | Alta | Atom `https://simonwillison.net/atom/everything/` ✅ (último 2026-11-21) | **Velocidad** + profundidad |
| Latent Space | https://www.latent.space | Ingeniería IA | 2–3/semana | Alta | RSS `https://www.latent.space/feed` ✅ (Substack; posts de pago truncados) | Profundidad |
| The Pragmatic Engineer | https://newsletter.pragmaticengineer.com | Industria/ingeniería | 1–2/semana | Alta | RSS `.../feed` ✅; **gran parte de pago** (feed trae extracto) | Profundidad |
| Import AI (Jack Clark) | https://importai.substack.com | Investigación/política IA | Semanal (lunes) | Alta | RSS `https://importai.substack.com/feed` ✅ (también `https://jack-clark.net/feed/` ✅) | Profundidad |
| Ben's Bites | https://www.bensbites.com | IA producto | ~Semanal | Media | RSS `https://www.bensbites.com/feed` ✅ (último 2026-11-17) | Media |
| The Batch (DeepLearning.AI) | https://www.deeplearning.ai/the-batch/ | IA | Semanal (viernes) | Alta | RSS `https://charonhub.deeplearning.ai/rss/` ✅ (15 items, último 2026-11-20). `/the-batch/feed/` → 404 | Profundidad |
| Interconnects (Nathan Lambert) | https://www.interconnects.ai | Modelos abiertos, RL | ~Semanal | Alta | RSS `.../feed` ✅ | Profundidad |
| Don't Worry About the Vase (Zvi) | https://thezvi.substack.com | Resumen semanal IA | Semanal+ | Media-alta (muy largo) | RSS `.../feed` ✅ | Profundidad |
| ByteByteGo | https://blog.bytebytego.com | System design | Semanal | Media | RSS `.../feed` ✅ (parte de pago) | Profundidad (evergreen) |
| Console.dev | https://console.dev | Herramientas dev | Semanal (jueves) | Media-alta | RSS `https://console.dev/rss.xml` ✅ | Profundidad |
| JavaScript Weekly (Cooper Press) | https://javascriptweekly.com | JS | Semanal (martes) | Alta | RSS `https://cprss.s3.amazonaws.com/javascriptweekly.com.xml` ✅ | Profundidad |
| Node Weekly / Frontend Focus / Golang Weekly | cooperpress.com | Node / Frontend / Go | Semanal | Alta | RSS `https://cprss.s3.amazonaws.com/{nodeweekly.com,frontendfoc.us,golangweekly.com}.xml` ✅. (DB Weekly feed existe pero último item de 2021: inactivo) | Profundidad |
| DevOps Weekly | https://www.devopsweekly.com | DevOps | Semanal (domingo) | Alta | **Solo email** (Mailchimp). Sin RSS encontrado; `/archive/` → 404 | Profundidad |
| SRE Weekly | https://sreweekly.com | SRE, incidentes | Semanal | Alta | RSS `https://sreweekly.com/feed/` ✅ (último 2026-11-08: cadencia irregular) | Profundidad |
| tl;dr sec | https://tldrsec.com | AppSec, cloud sec | Semanal (jueves) | Alta | Web Beehiiv ✅; RSS declarado `https://rss.hiivinternal.com/feeds/xgTKUmMmUm.xml` **no verificado** (timeout); `tldrsec.com/feed` devuelve HTML | Profundidad |
| Risky Business (podcast) / Risky Bulletin | https://risky.biz | Seguridad | Semanal + diario | Alta | RSS podcast `https://risky.biz/feeds/risky-business/` ✅; newsletter `https://news.risky.biz/rss/` ✅ (diaria) | Bulletin: **velocidad**; podcast: profundidad |
| This Week in Security (Hackaday) | https://hackaday.com/tag/this-week-in-security/ | Seguridad | Semanal (viernes) | Media-alta | RSS `https://hackaday.com/tag/this-week-in-security/feed/` ✅ (la URL por categoría `/category/.../feed/` devuelve feed vacío) | Profundidad |
| LWN.net | https://lwn.net | Linux/kernel/open source | Diaria | Alta | RSS `https://lwn.net/headlines/rss` ✅ (algunos artículos de pago 1 semana) | Profundidad |
| InfoQ | https://www.infoq.com | Arquitectura, ingeniería | Diaria | Media | RSS `https://feed.infoq.com/` ✅ | Profundidad |
| The New Stack | https://thenewstack.io | Cloud native, DevOps | Diaria | Media | RSS `https://thenewstack.io/feed/` ✅ | Media |

### 2.3 Medios generalistas tech (velocidad)

| Fuente | Tema | Señal | Acceso |
|---|---|---|---|
| TechCrunch IA | IA/startups | Media | RSS `https://techcrunch.com/category/artificial-intelligence/feed/` ✅ |
| The Verge | Tech consumo + IA | Media | RSS `https://www.theverge.com/rss/index.xml` ✅ |
| Ars Technica | Tech/seguridad | Alta | RSS `https://feeds.arstechnica.com/arstechnica/technology-lab` ✅ |
| The Register | Enterprise, seguridad | Media-alta | Atom `https://www.theregister.com/headlines.atom` ✅ |

### 2.4 Blogs oficiales y changelogs de vendors

| Fuente | Tema | Señal | Acceso | Velocidad |
|---|---|---|---|---|
| OpenAI News | IA | Alta | RSS `https://openai.com/news/rss.xml` ✅ (histórico completo, último 2026-11-20) | **Sí** |
| OpenAI API changelog | IA/API | Alta | HTML `https://platform.openai.com/docs/changelog` (200); sin RSS conocido | Sí |
| Anthropic News | IA | Alta | **Sin RSS** (`/rss.xml` → 404). Alternativa: `https://www.anthropic.com/sitemap.xml` ✅ (282 URLs `/news/...`) o scraping de `/news` | **Sí** |
| Google AI blog (The Keyword) | IA | Alta | RSS `https://blog.google/technology/ai/rss/` ✅ | **Sí** |
| Google DeepMind blog | IA investigación | Alta | RSS `https://deepmind.google/blog/rss.xml` ✅ | Sí |
| Google Developers Blog | Dev/Gemini API | Alta | Atom `https://developers.googleblog.com/feeds/posts/default` ✅ | Sí |
| Gemini API changelog | IA/API | Alta | HTML `https://ai.google.dev/gemini-api/docs/changelog` (200); sin RSS conocido | Sí |
| Meta AI blog | IA | Alta | **Sin RSS** (`ai.meta.com/blog/` y `/blog/rss/` → 400 a clientes no navegador). Alternativa parcial: Engineering at Meta `https://engineering.fb.com/feed/` ✅ | Sí |
| Mistral AI | IA | Alta | RSS `https://mistral.ai/news/rss` ✅ (servido como text/plain, XML válido) | Sí |
| Hugging Face blog | IA abierta | Alta | RSS `https://huggingface.co/blog/feed.xml` ✅ | Sí |
| GitHub Blog | Dev | Alta | RSS `https://github.blog/feed/` ✅ | Sí |
| GitHub Changelog | Dev | Alta | RSS `https://github.blog/changelog/feed/` ✅ | Sí |
| GitHub Status | Incidentes | Alta | RSS `https://www.githubstatus.com/history.rss` ✅ | **Sí** (caídas) |
| AWS What's New | Cloud | Alta (alto volumen) | RSS `https://aws.amazon.com/about-aws/whats-new/recent/feed/` ✅ (100 items) | Sí |
| AWS News Blog | Cloud | Alta | RSS `https://aws.amazon.com/blogs/aws/feed/` ✅ | Sí |
| Google Cloud Blog | Cloud | Alta | RSS `https://cloudblog.withgoogle.com/rss/` ✅ | Sí |
| Azure Updates | Cloud | Alta (alto volumen) | RSS `https://www.microsoft.com/releasecommunications/api/v2/azure/rss` ✅ (200 items) | Sí |
| Cloudflare Blog | Infra/seguridad/web | Alta | RSS `https://blog.cloudflare.com/rss/` ✅ | Sí |
| Vercel | Web/frontend | Alta | Atom `https://vercel.com/atom` ✅ | Sí |
| Kubernetes Blog | Cloud native | Alta | RSS `https://kubernetes.io/feed.xml` ✅ | Media |
| CNCF Blog | Cloud native | Media | RSS `https://www.cncf.io/feed/` ✅ | Media |
| Chrome for Developers | Web | Alta | RSS `https://developer.chrome.com/static/blog/feed.xml` ✅ (último 2026-10-06) | Media |
| WebKit Blog | Web/Safari | Alta | RSS `https://webkit.org/feed/` ✅ | Media |
| MDN Blog | Web | Media | RSS `https://developer.mozilla.org/en-US/blog/rss.xml` ✅ (último abril 2026: poco activo) | Baja |
| Node.js Blog | JS runtime | Alta | RSS `https://nodejs.org/en/feed/blog.xml` ✅ (incluye releases de seguridad) | Sí |
| React Blog | Frontend | Alta | RSS `https://react.dev/rss.xml` ✅ | Media |

### 2.5 Seguridad: avisos y medios

| Fuente | Tema | Señal | Acceso | Velocidad |
|---|---|---|---|---|
| CISA KEV | Vulnerabilidades explotadas | Muy alta | JSON `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` ✅ (1790 entradas, `dateReleased` 2026-11-20) | **Sí** |
| CISA Advisories | Avisos | Alta | RSS `https://www.cisa.gov/cybersecurity-advisories/all.xml` ✅ | Sí |
| GitHub Advisory Database | Vulnerabilidades en dependencias | Alta (alto volumen) | API REST `https://api.github.com/advisories` ✅ (sin token: límite 60 req/h) | Sí |
| NVD (NIST) | CVEs | Alta (muy alto volumen) | API `https://services.nvd.nist.gov/rest/json/cves/2.0` ✅ (API key recomendada) | Sí (pero ruidoso) |
| BleepingComputer | Seguridad | Alta | RSS `https://www.bleepingcomputer.com/feed/` ✅ | **Sí** |
| The Hacker News | Seguridad | Media | RSS `https://feeds.feedburner.com/TheHackersNews` ✅ | Sí |
| Krebs on Security | Seguridad investigativa | Alta | RSS `https://krebsonsecurity.com/feed/` ✅ | Media |

### 2.6 Fuentes en español

| Fuente | Tema | Señal | Acceso |
|---|---|---|---|
| Xataka | Tech general | Media | RSS `https://www.xataka.com/feedburner.xml` ✅ |
| Genbeta | Software, dev, IA | Media | RSS `https://www.genbeta.com/feedburner.xml` ✅ |
| Hipertextual | Tech general | Media-baja | RSS `https://hipertextual.com/feed` ✅ |
| Una al día (Hispasec) | Seguridad | Media-alta | RSS `https://unaaldia.hispasec.com/feed` ✅ (último 2026-10-22: actividad irregular) |
| INCIBE-CERT avisos | Seguridad (avisos) | Alta | RSS `https://www.incibe.es/incibe-cert/alerta-temprana/avisos/feed` ✅ |

Observación: las fuentes en español son mayoritariamente medios generalistas que llegan después que las fuentes en inglés; útiles para ver cómo se ha contado ya una noticia en español (competencia), no para velocidad.

### 2.7 Redes sociales: qué no es accesible y alternativas

| Plataforma | Estado | Alternativas prácticas |
|---|---|---|
| X / Twitter | Requiere login para leer; API oficial de pago. Nitter público: `nitter.net/OpenAI/rss` → **410 Gone** | Los anuncios de labs casi siempre se publican también en su blog/RSS (OpenAI, Google, Mistral) o los recogen HN/Techmeme en minutos. Bluesky (abajo) |
| LinkedIn | Requiere login; sin RSS ni API pública de lectura de feeds | Ninguna fiable programáticamente; usar los blogs de empresa |
| Bluesky | **Abierto**: API pública sin auth `https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=...` ✅ y RSS por perfil `https://bsky.app/profile/{handle}/rss` ✅ | Seguir cuentas de investigadores/periodistas presentes en Bluesky |
| Mastodon | **Abierto**: RSS por perfil `https://{instancia}/@{usuario}.rss` ✅ (ej. `mastodon.social/@simon.rss`) | Idem |
| Reddit | Ver 2.1: requiere OAuth | API oficial con app registrada |

---

## Conclusiones (TLDR: web vs email)

1. **La web contiene todo el contenido editorial del email** (mismas noticias, resúmenes y enlaces; verificado con TLDR IT 2026-11-20). Lo exclusivo del email es publicidad propia, ofertas de empleo, firma y enlaces de gestión: nada útil para noticias.
2. **Acceso programático sin email es viable**: RSS por newsletter (`/api/rss/{slug}`) como detector de edición nueva + HTML de la edición (`/{slug}/{YYYY-MM-DD}`) renderizado en servidor y con estructura estable (`<article>` + `<h3>` + enlace + resumen). robots.txt lo permite y los ToS no lo prohíben.
3. **Trampas conocidas**: el RSS no trae contenido (solo título de edición); las fechas sin edición devuelven 200 con la landing (soft 404); el sitio aplica rate limit (429) con ráfagas de ~1 req/s; WebDev ahora es Dev.
4. **Lo no verificado**: cuánto tarda la edición en aparecer en la web respecto al envío (emails recibidos entre ~11:12 y ~14:13 UTC según newsletter). El email sigue siendo la única fuente con hora de llegada conocida.
5. TLDR es un **resumen diario (profundidad/curación)**, no una fuente de velocidad: llega 12–36 h después de las noticias. Para "historias bomba" las fuentes de velocidad verificadas son HN (hnrss con umbral de puntos), Techmeme, blogs oficiales con RSS (OpenAI, Google, Mistral, GitHub, AWS), Simon Willison, Risky Bulletin, BleepingComputer y CISA KEV.
