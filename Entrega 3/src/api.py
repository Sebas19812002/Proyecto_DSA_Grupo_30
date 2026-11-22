"""API FastAPI para simulación retrospectiva honesta de inferencia de un día.

Ejecutar desde la raíz de dsa_entrega2_base:
    uvicorn src.api:app --reload --port 8000

Este prototipo NO recibe actualizaciones en tiempo real ni afirma pronosticar 2026.
"""
from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from .entrega2 import features_from_panel
except ImportError:
    from entrega2 import features_from_panel

app = FastAPI(title="EV Charging Analytics - DSA", version="0.1.0",
              description="Predicción histórica de sesiones diarias, exclusivamente para evaluación.")

class PredictionRequest(BaseModel):
    estacion: str
    fecha: str  # YYYY-MM-DD

@lru_cache(maxsize=1)
def resources():
    root = Path(os.getenv("DSA_RESULTS_DIR", "results"))
    model_path, panel_path = root / "modelo_seleccionado.joblib", root / "panel_diario_cinco_estaciones.csv"
    if not model_path.exists() or not panel_path.exists():
        raise FileNotFoundError("Ejecute primero src/entrega2.py para generar modelo y panel.")
    saved = joblib.load(model_path)  # Sólo cargar artefactos generados localmente y de confianza.
    panel = pd.read_csv(panel_path, parse_dates=["fecha"])
    panel["sin_registro"] = panel["sin_registro"].map(lambda x: str(x).lower() == "true")
    frame = features_from_panel(panel)
    return saved, panel, frame

@app.get("/health")
def health():
    try:
        saved, panel, _ = resources()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"estado": "listo", "modelo": saved["winner"], "numero_estaciones": int(panel.estacion.nunique()),
            "tipo": "simulacion_historica_no_tiempo_real"}

@app.get("/stations")
def stations():
    try:
        saved, panel, frame = resources()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    allowed = frame[frame.fecha > pd.Timestamp(saved["val_end"])]
    rows=[]
    for s, g in allowed.groupby("estacion"):
        rows.append({"estacion":str(s), "fecha_min":str(g.fecha.min().date()),
                     "fecha_max":str(g.fecha.max().date()), "dias":len(g)})
    return rows

@app.get("/history")
def history(estacion: str):
    try:
        _, panel, _ = resources()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    data=panel[panel.estacion == estacion].sort_values("fecha")
    if data.empty:
        raise HTTPException(404, "Estación no encontrada")
    return [{"fecha": str(r.fecha.date()), "sesiones":int(r.sesiones),
             "cero_asumido":bool(r.sin_registro)} for r in data.itertuples()]

@app.post("/predict")
def predict(req: PredictionRequest):
    try:
        saved, _, frame=resources()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        t=pd.Timestamp(req.fecha)
        if t.tzinfo is not None or t.strftime("%Y-%m-%d") != req.fecha:
            raise ValueError("La fecha debe ser AAAA-MM-DD")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Fecha inválida; formato YYYY-MM-DD") from exc
    if t <= pd.Timestamp(saved["val_end"]):
        raise HTTPException(422, "Seleccione una fecha posterior al periodo de validación.")
    row=frame[(frame.estacion == req.estacion)&(frame.fecha == t)]
    if row.empty:
        raise HTTPException(404, "No hay datos de contexto suficientes para esa estación y fecha.")
    inputs=row[saved["features"]]  # En particular, NO incluye la variable objetivo de fecha consultada.
    result=max(0.0, float(saved["model"].predict(inputs)[0]))
    r=row.iloc[0]
    return {"estacion":req.estacion, "fecha":req.fecha, "prediccion_sesiones":round(result,3),
            "referencia_7_dias":float(r["lag_7"]), "observado_historico":int(r["sesiones"]),
            "observacion_es_cero_asumido":bool(r["sin_registro"]),
            "modelo":saved["winner"], "tipo":"evaluacion_historica_un_paso",
            "advertencia":"Las entradas lag se construyen con sesiones históricas observadas hasta el día previo."}
