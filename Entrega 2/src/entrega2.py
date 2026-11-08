"""Entrega 2 DSA: preparación auditada, selección de estaciones y modelos iniciales.

Uso:
 python src/entrega2.py --csv "data/Electric_Vehicle_Charging_Station_Data.csv"
 python src/entrega2.py --csv "data/Electric_Vehicle_Charging_Station_Data.csv" \
     --tracking-uri http://127.0.0.1:8050 --experiment "DSA-recarga-Boulder"

El script no afirma que un día sin registro equivalga necesariamente a cero real.
"""
from __future__ import annotations
import argparse
import json
import re
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

START_CANDIDATES = ("Start_Date___Time", "Start Date / Time", "Start Date Time", "start_datetime")
STATION_CANDIDATES = ("Station_Name", "Station Name", "station", "station_name")
ENERGY_CANDIDATES = ("Energy__kWh_", "Energy (kWh)", "Energy_kWh", "energy_kwh")
DURATION_CANDIDATES = ("Total_Duration__hh_mm_ss_", "Total Duration (hh:mm:ss)", "Total Duration", "duration")
ADDRESS_CANDIDATES = ("Address", "address")
RENAME_PREFIX_OLD = "COMM VITALITY / "
RENAME_PREFIX_NEW = "MUNICIPAL SC / "
SEED = 42


def pick_column(df: pd.DataFrame, candidates: tuple[str, ...], required=True):
    # Permite nombres CSV del export de ArcGIS o nombres legibles del portal.
    canon = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    lookup = {canon(c): c for c in df.columns}
    for name in candidates:
        if canon(name) in lookup:
            return lookup[canon(name)]
    if required:
        raise ValueError(f"Columna requerida ausente. Busqué: {candidates}. Columnas del archivo: {list(df.columns)}")
    return None


def parse_mixed_dates(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    # Las fechas son locales de Boulder; se conservan fechas civiles, sin convertir a UTC.
    # Se conoce que el archivo contiene dos formatos (mes/día/año y ISO).
    result = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        mask = result.isna()
        result.loc[mask] = pd.to_datetime(s.loc[mask], format=fmt, errors="coerce")
    return result


def prepare_sessions(csv_path: Path, exclusions: Path | None = None):
    df = pd.read_csv(csv_path, low_memory=False)
    original = len(df)
    station_col = pick_column(df, STATION_CANDIDATES)
    start_col = pick_column(df, START_CANDIDATES)
    energy_col = pick_column(df, ENERGY_CANDIDATES)
    duration_col = pick_column(df, DURATION_CANDIDATES, required=False)
    address_col = pick_column(df, ADDRESS_CANDIDATES, required=False)
    base = pd.DataFrame(index=df.index)
    base["original_station"] = df[station_col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.upper()
    base["address"] = (df[address_col].astype("string").str.strip().str.upper() if address_col else "SIN_DIRECCION")
    base["raw_date"] = df[start_col].astype("string")
    base["fecha_hora"] = parse_mixed_dates(df[start_col])
    base["energia_kwh"] = pd.to_numeric(df[energy_col].astype("string").str.replace(",", ".", regex=False), errors="coerce")
    base["duracion"] = df[duration_col].astype("string") if duration_col else pd.Series(pd.NA,index=df.index,dtype="string")
    base["estacion"] = base["original_station"].copy()
    # Unificar prefijo solo si el nombre de destino existe realmente en el CSV.
    originals = set(base["original_station"].dropna())
    candidates = base["estacion"].str.startswith(RENAME_PREFIX_OLD, na=False)
    target = base.loc[candidates, "estacion"].str.replace(RENAME_PREFIX_OLD, RENAME_PREFIX_NEW, n=1, regex=False)
    eligible = target.isin(originals)
    base.loc[target.index[eligible], "estacion"] = target[eligible]
    remapped = int(eligible.sum())
    # Descartar fechas, estaciones, y energía no válidas. 0 kWh se trata como intento no válido,
    # coherente con las reglas del primer informe (debe discutirse en memoria).
    valid = base["fecha_hora"].notna() & base["estacion"].notna() & (base["energia_kwh"] > 0)
    if duration_col:
        valid &= ~base["duracion"].str.fullmatch(r"\s*0+:0+:0+\s*", na=False)
    clean = base.loc[valid].copy()
    # Duplicados de formato: ISO vs. mes/día/año. No redondear valores de energía aquí.
    # Una duplicación se exige por estación canónica, dirección, minuto e igual energía.
    clean["instante_minuto"] = clean["fecha_hora"].dt.floor("min")
    clean["es_iso"] = clean["raw_date"].str.match(r"^\d{4}-\d{2}-\d{2}", na=False)
    clean = clean.sort_values("es_iso")  # preferir registro no ISO, sin segundos, si colisionan
    dup_key = ["estacion", "address", "instante_minuto", "energia_kwh"]
    dup = clean.duplicated(dup_key, keep="first")
    duplicates = int(dup.sum())
    # Excluir estaciones correspondientes a flotas municipales
    flota = clean["estacion"].str.contains(r"FLT MNT|MSC E|OSMP FLEET", na=False)
    clean = clean.loc[~flota].copy()
    clean = clean.loc[~dup].copy()

    # Unificar los dos nombres del cargador JUNCTION ST1
    clean.loc[
        clean["estacion"] == "BOULDERJUNCTION / JUNCTION ST1",
        "estacion"] = "BOULDER / JUNCTION ST1"
    excluded_stations = []
    if exclusions and exclusions.exists():
        excluded_stations = [x.strip().upper() for x in exclusions.read_text(encoding="utf-8").splitlines()
                             if x.strip() and not x.lstrip().startswith("#")]
        clean = clean[~clean["estacion"].isin(excluded_stations)]
    clean["fecha"] = clean["fecha_hora"].dt.normalize()
    summary = {"filas_originales": original, "filas_validas_deduplicadas": len(clean),
               "duplicados_detectados_con_regla_conservadora": duplicates,
               "registros_renombrados": remapped,
               "filas_excluidas": original - len(clean),
               "estaciones_restantes": clean["estacion"].nunique(),
               "lista_exclusion_aplicada": excluded_stations,
               "nota": "Las cifras NO deben suponerse iguales al informe previo sin reconciliar las reglas de limpieza."}
    return clean, summary


def build_daily_panel(sessions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    actual = sessions.groupby(["estacion", "fecha"]).size().rename("sesiones").reset_index()
    parts, rows = [], []
    for station, g in actual.groupby("estacion", sort=True):
        start, end = g.fecha.min(), g.fecha.max()
        dates = pd.date_range(start, end, freq="D")
        full = pd.DataFrame({"estacion": station, "fecha": dates})
        full = full.merge(g, on=["estacion", "fecha"], how="left", validate="one_to_one")
        full["sin_registro"] = full["sesiones"].isna()
        full["sesiones"] = full["sesiones"].fillna(0).astype(int)
        parts.append(full)
        g_days = len(g)
        rows.append({"estacion": station, "primer_dia": start, "ultimo_dia": end,
                     "dias_calendario": len(full), "dias_con_sesiones": g_days,
                     "dias_sin_registro_asumidos_cero": int(full["sin_registro"].sum()),
                     "proporcion_dias_con_sesiones": g_days / len(full),
                     "sesiones_totales": int(g["sesiones"].sum()),
                     "media_sesiones_diarias": float(full["sesiones"].mean()),
                     "dias_2023": int((full.fecha.dt.year == 2023).sum())})
    return pd.concat(parts, ignore_index=True), pd.DataFrame(rows)


def choose_stations(profile, panel, n, train_end):
    # Seleccionar utilizando solo datos de entrenamiento.
    train = panel[panel["fecha"] <= pd.Timestamp(train_end)]

    resumen = train.groupby("estacion").agg(
        dias_entrenamiento=("fecha", "size"),
        dias_con_sesiones_entrenamiento=(
            "sin_registro", lambda x: (~x).sum()
        ),
        sesiones_entrenamiento=("sesiones", "sum")
    ).reset_index()

    candidatos = profile.merge(
        resumen, on="estacion", how="inner"
    )

    candidatos = candidatos[
        candidatos["dias_entrenamiento"] >= 450
    ].copy()

    # Calcular interrupciones en entrenamiento
    max_rachas = {}

    for estacion, g in train.groupby("estacion"):
        faltante = g.sort_values("fecha")["sin_registro"].fillna(False)
        bloques = faltante.ne(faltante.shift(fill_value=False)).cumsum()
        max_rachas[estacion] = int(faltante.groupby(bloques).sum().max())

    candidatos["mayor_interrupcion"] = candidatos["estacion"].map(max_rachas)
    candidatos = candidatos[candidatos["mayor_interrupcion"] <= 30].copy()

    if len(candidatos) < n:
        raise ValueError("No hay suficientes estaciones elegibles")

    candidatos = candidatos.sort_values(
        ["sesiones_entrenamiento",
         "dias_con_sesiones_entrenamiento",
         "estacion"],
        ascending=[False, False, True]
    )

    candidatos["rango_seleccion"] = range(
        1, len(candidatos) + 1
    )

    return candidatos.head(n).copy()


def features_from_panel(panel: pd.DataFrame) -> pd.DataFrame:
    frame = panel.sort_values(["estacion", "fecha"]).copy()

    # Identificar periodos de 7 o mas dias sin registros
    falta = frame["sin_registro"].fillna(False)

    cambio = falta.ne(
        falta.groupby(frame["estacion"]).shift(fill_value=False)
    )

    bloques = cambio.groupby(frame["estacion"]).cumsum()

    longitudes = falta.groupby(
        [frame["estacion"], bloques]
    ).transform("sum")

    frame["periodo_incierto"] = falta & (longitudes >= 7)

    # No considerar los periodos inciertos como demanda cero
    frame["sesiones"] = frame["sesiones"].astype(float)
    frame.loc[frame["periodo_incierto"], "sesiones"] = np.nan

    grp = frame.groupby("estacion", sort=False)["sesiones"]
    for lag in (1, 7, 14):
        frame[f"lag_{lag}"] = grp.shift(lag)
    frame["media_7_pasados"] = frame.groupby("estacion")["sesiones"].transform(
        lambda s: s.shift(1).rolling(7, min_periods=7).mean())
    frame["media_14_pasados"] = frame.groupby("estacion")["sesiones"].transform(
        lambda s: s.shift(1).rolling(14, min_periods=14).mean())
    frame["dia_semana"] = frame["fecha"].dt.day_of_week
    frame["mes"] = frame["fecha"].dt.month
    frame["dia_anio"] = frame["fecha"].dt.day_of_year
    return frame.dropna(subset=["sesiones", "lag_1", "lag_7", "lag_14", "media_7_pasados", "media_14_pasados"])


def score(y_true, y_pred) -> dict:
    p = np.maximum(0, np.asarray(y_pred, dtype=float))
    return {"MAE": round(float(mean_absolute_error(y_true, p)), 4),
            "RMSE": round(float(np.sqrt(mean_squared_error(y_true, p))), 4),
            "sesiones_observadas_media": round(float(np.mean(y_true)), 4),
            "sesiones_predichas_media": round(float(np.mean(p)), 4)}


def experiment(frame: pd.DataFrame, folder: Path, train_end: str, val_end: str, tracking_uri=None, experiment_name=None):
    features = ["estacion", "dia_semana", "mes", "dia_anio", "lag_1", "lag_7", "lag_14", "media_7_pasados", "media_14_pasados"]
    cats = ["estacion"]
    nums = [x for x in features if x not in cats]
    train = frame.loc[frame.fecha <= pd.Timestamp(train_end)]
    val = frame.loc[(frame.fecha > pd.Timestamp(train_end)) & (frame.fecha <= pd.Timestamp(val_end))]
    test = frame.loc[frame.fecha > pd.Timestamp(val_end)]
    if min(len(train), len(val), len(test)) <= 0:
        raise ValueError("No existen filas suficientes para separar entrenamiento, validación y prueba.")
    def preprocessor():
        return ColumnTransformer([("categorica", OneHotEncoder(handle_unknown="ignore"), cats),
                                  ("numerica", SimpleImputer(strategy="median"), nums)])
    models = {
        "Ridge": Ridge(alpha=10.0),
        "RandomForest": RandomForestRegressor(n_estimators=120, max_depth=12, min_samples_leaf=3,
                                               n_jobs=-1, random_state=SEED),
        # HistGradientBoosting trabaja con matrices densas; OneHotEncoder aquí usa sparse_output=False.
        "HistGradientBoosting": HistGradientBoostingRegressor(max_iter=120, max_depth=5,
                                                               learning_rate=0.07, random_state=SEED),
    }
    baseline_val = score(val.sesiones, val.lag_7)
    baseline_test = score(test.sesiones, test.lag_7)
    records, fitted = [], {}
    mlflow = None
    if tracking_uri:
        try:
            import mlflow as _mlflow
            mlflow = _mlflow
        except ImportError as exc:
            raise RuntimeError("Se indicó --tracking-uri, pero mlflow no está instalado.") from exc
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name or "DSA-recarga-Boulder")
    for name, estimator in models.items():
        # Garantizar representación densa compatible con HistGradientBoosting.
        # sklearn >=1.2: sparse_output=False; en otros entornos utilizar el fallback.
        try:
            encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        except TypeError:
            encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)
        prep = ColumnTransformer([("categorica", encoder, cats),
                                  ("numerica", SimpleImputer(strategy="median"), nums)])
        pipe = Pipeline([("preprocesamiento", prep), ("modelo", estimator)])
        pipe.fit(train[features], train.sesiones)
        val_pred = pipe.predict(val[features])
        test_pred = pipe.predict(test[features])
        val_metrics, test_metrics = score(val.sesiones, val_pred), score(test.sesiones, test_pred)
        records.append({"modelo": name, "val_MAE": val_metrics["MAE"], "val_RMSE": val_metrics["RMSE"],
                        "test_MAE": test_metrics["MAE"], "test_RMSE": test_metrics["RMSE"]})
        fitted[name] = (pipe, val_pred, test_pred)
        if mlflow:
            with mlflow.start_run(run_name=name):
                mlflow.log_params({"modelo": name, "train_end": train_end, "val_end": val_end,
                                   "numero_estaciones": int(frame.estacion.nunique()), "random_state": SEED})
                mlflow.log_params({
                    f"hp_{k}": str(v)
                    for k, v in estimator.get_params(deep=False).items()})

                mlflow.log_metrics({"val_MAE": val_metrics["MAE"], "val_RMSE": val_metrics["RMSE"],
                                    "test_MAE": test_metrics["MAE"], "test_RMSE": test_metrics["RMSE"],
                                    "baseline_val_MAE": baseline_val["MAE"]})
                mlflow.sklearn.log_model(
                    sk_model=pipe,
                    name="modelo",
                    serialization_format="cloudpickle")

    metrics_df = pd.DataFrame(records).sort_values("val_MAE")
    winner = str(metrics_df.iloc[0].modelo)
    joblib.dump({"model": fitted[winner][0], "features": features,
                 "stations": sorted(frame.estacion.unique().tolist()), "winner": winner,
                 "train_end": train_end, "val_end": val_end}, folder / "modelo_seleccionado.joblib")
    # La columna de predicción y los reales usan información previa a la fecha objetivo para cada fila.
    pred = test[["estacion", "fecha", "sesiones", "lag_7", "sin_registro"]].copy()
    pred["prediccion_modelo"] = np.maximum(0, fitted[winner][2])
    pred.rename(columns={"sesiones": "real_asumido", "lag_7":"prediccion_baseline_7d"}).to_csv(
        folder / "predicciones_prueba.csv", index=False)
    metrics_df.to_csv(folder / "metricas_modelos.csv", index=False)
    return {"filas_entrenamiento":len(train), "filas_validacion":len(val), "filas_prueba":len(test),
            "baseline_semanal": {"validacion": baseline_val, "prueba": baseline_test},
            "mejor_modelo_segun_validacion": winner, "metricas_modelos": records,
            "advertencia": "La evaluación usa lags reales del histórico; para un escenario futuro simulado "
                           "debe proporcionarse un histórico actualizado hasta el día previo al pronóstico."}


def main():
    ap=argparse.ArgumentParser(description="DSA entrega 2 Boulder")
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--out", default=Path("results"), type=Path)
    ap.add_argument("--exclude-stations", type=Path, default=None)
    ap.add_argument("--n-stations", type=int, default=5)
    ap.add_argument("--train-end", default="2022-12-31")
    ap.add_argument("--val-end", default="2023-06-30")
    ap.add_argument("--tracking-uri", default=None)
    ap.add_argument("--experiment", default="DSA-recarga-Boulder")
    args=ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    sessions, cleaning = prepare_sessions(args.csv, args.exclude_stations)
    panel, profile = build_daily_panel(sessions)
    selection = choose_stations(profile, panel, args.n_stations, args.train_end)
    profile.sort_values("dias_con_sesiones",ascending=False).to_csv(args.out/"perfil_estaciones.csv", index=False)
    selection.to_csv(args.out/"cinco_estaciones.csv", index=False)
    panel = panel[panel.estacion.isin(selection.estacion)].copy()
    panel.to_csv(args.out/"panel_diario_cinco_estaciones.csv", index=False)
    training_frame = features_from_panel(panel)
    exp = experiment(training_frame,args.out,args.train_end,args.val_end,args.tracking_uri,args.experiment)
    report={"limpieza":cleaning,"seleccion":selection.estacion.tolist(),"experimentos":exp,
            "politica_ceros":"Días intermedios sin sesión registrados como cero provisional, no probado; "
                            "no rellenar fuera de la ventana primera-última sesión. Verificar faltantes reales."}
    (args.out/"resumen_ejecucion.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

if __name__=="__main__": main()
