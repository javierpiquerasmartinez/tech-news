"""Edición de un proyecto de CapCut en UN solo ciclo de guardado, con las funciones de capcut-kit.

Se ejecuta como proceso aparte en el entorno del kit (necesita pyobjc), desde `tn.capcut`:

    uv run --with pyobjc-framework-ApplicationServices --with pyobjc-framework-Quartz \\
        python capcut_edicion.py plan.json

Cada comando del kit cierra y reabre CapCut; con decenas de capas serían minutos de
reinicios. Aquí se importa el kit (sin copiar su código, ADR-0005) y se aplica todo dentro
de un único `edit_draft`.

plan.json:
  {"kit": "<ruta del kit>", "proyecto": "<nombre del proyecto>",
   "capas": [{"fichero": "...mov", "inicio": 12.4, "nivel": 1, "silencio": true}],
   "zoom_alterno": 1.05}
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def cargar_kit(ruta: Path):
    spec = importlib.util.spec_from_file_location("capcut_bridge", ruta / "capcut-bridge.py")
    kit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kit)
    return kit


def main(ruta_plan: str) -> None:
    plan = json.loads(Path(ruta_plan).read_text())
    kit = cargar_kit(Path(plan["kit"]))

    def mutate(d, folder):
        # Zoom leve alterno en los cortes del plano principal: disimula los saltos de imagen.
        zoom = plan.get("zoom_alterno")
        if zoom:
            principales = [s for t in d["tracks"] if t["type"] == "video" and t["flag"] == 0 for s in t["segments"]]
            for i, s in enumerate(principales):
                escala = zoom if i % 2 else 1.0
                s["clip"]["scale"] = {"x": escala, "y": escala}
                s["uniform_scale"] = {"on": True, "value": escala}
        for c in plan["capas"]:
            path = kit.local_media(folder, c["fichero"])
            w, h, dur_us, has_audio = kit.probe(path)
            mid = kit.uid()
            d["materials"]["videos"].append(kit.video_material(mid, path, w, h, dur_us, has_audio))
            seg = kit.segment(mid, 0, dur_us, round(c["inicio"] * 1e6), kit.segment_extras(d["materials"]))
            seg["render_index"] = seg["track_render_index"] = c["nivel"]
            if c.get("silencio"):
                seg["volume"] = seg["last_nonzero_volume"] = 0.0
            kit.overlay_track(d, c["nivel"])["segments"].append(seg)

    kit.edit_draft(plan["proyecto"], mutate, reopen=False)
    print(json.dumps({"proyecto": plan["proyecto"], "capas": len(plan["capas"])}))


if __name__ == "__main__":
    main(sys.argv[1])
