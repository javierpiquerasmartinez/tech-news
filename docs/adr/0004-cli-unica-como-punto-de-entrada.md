# Una CLI única como punto de entrada de todo

Toda acción sobre el sistema (lanzar un rol, descartar o destacar una Historia, cambiar el estado de una Propuesta) pasa por la CLI del proyecto (`tn`). `launchd`, la interfaz web local y las conversaciones con Claude Code son solo clientes de esa CLI: ninguno escribe en la base de datos ni en los Markdown por su cuenta. Así una acción hecha hablando con Claude es exactamente igual que el botón equivalente de la web, todo queda registrado como Ejecución, y nada ocurre por un camino que la persona editora no pueda lanzar a mano.
