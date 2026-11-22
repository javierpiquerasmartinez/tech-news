# Ejecución local en el Mac, sin despliegue

Todo el arnés (Recolector, Explorador, Editor, Redactor) se ejecuta en el Mac de la persona editora; no hay servidor ni CI desplegado. Se descartó GitHub Actions pese a funcionar con el portátil cerrado, por preferencia explícita de mantenerlo todo local.

Los agentes son skills de Claude Code lanzadas con `claude -p` sobre una suscripción Pro (no API de pago), y `launchd` las programa. El límite de uso de Pro obliga a una sola ejecución diaria completa (Recolector + Explorador + Editor) más el Redactor semanal; no hay sondeo cada pocas horas.

## Consequences

- Si el Mac está apagado o dormido no se recoge nada: cada ejecución debe recoger "desde la última ejecución con éxito", no "las últimas 24 h", para que los huecos se rellenen solos al despertar. Las Fuentes con ventana corta (RSS de pocos items) pueden perder Items en ausencias largas.
- Las Historias bomba solo se detectan mientras el Mac está encendido, y con un retraso de hasta un día por la ejecución diaria.
- Cada token cuenta: todo lo que se pueda resolver de forma determinista (deduplicar por URL, filtrar patrocinios) se resuelve antes de llegar a un agente.
