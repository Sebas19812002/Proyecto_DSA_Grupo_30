# Entrega 2 — Proyecto de predicción de sesiones de recarga (Boulder)

## Propósito

Código inicial para preparar los datos de estaciones de Boulder, comparar modelos supervisados y registrar experimentos en MLflow. Este paquete **no reemplaza** la exploración original ni permite afirmar métricas sobre el CSV del grupo hasta ejecutarlo y contrastar sus resultados.

## Pasos en Windows (Git Bash o PowerShell)

1. Traer el CSV con `dvc pull` (queda en `Entrega 1/Electric_Vehicle_Charging_Station_Data.csv`).
2. Desde la carpeta `Entrega 2`, ejecutar:
 
```bash
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# Git Bash: source .venv/Scripts/activate
python -m pip install -r requirements.txt
python src/entrega2.py --csv ../Entrega 1/Electric_Vehicle_Charging_Station_Data.csv
```

## Experimentos en MLflow (AWS EC2)

Los experimentos se ejecutan en una instancia EC2 (t2.medium, Ubuntu 24.04, 30 GB) con el servidor de MLflow en el puerto 8050. El repositorio se clona en la máquina y el CSV se descarga con `dvc pull`.

Cada ejecución crea en el experimento `DSA-recarga-Boulder`:

- Un run `Baseline_lag7` (predice con el valor de hace 7 días) como referencia.
- Diez runs, uno por configuración de hiperparámetros: cuatro de Ridge (`alpha`), tres de RandomForest (`n_estimators`, `max_depth`, `min_samples_leaf`) y tres de HistGradientBoosting (`max_iter`, `max_depth`, `learning_rate`). Las configuraciones están en la lista `CONFIGURACIONES` de `src/entrega2.py`.
- En cada run: parámetros, métricas (`val_MAE`, `val_RMSE`, `test_MAE`, `test_RMSE`, `mejora_vs_baseline_val_MAE`), tags (`familia`, `autor`, `entrega`) y el modelo.
- El run con menor `val_MAE` queda con el tag `seleccionado=si`, guarda `metricas_modelos.csv` y `predicciones_prueba.csv` como artefactos y se registra como una nueva versión de `modelo-recarga-boulder` en el Model Registry.

En la máquina EC2:

```bash
# Terminal 1: servidor de MLflow (dejar abierta)
source .venv/bin/activate
mlflow server -h 0.0.0.0 -p 8050 --allowed-hosts "localhost:8050,<IP>:8050" --cors-allowed-origins "http://<IP>:8050"

# Terminal 2: experimentos
source .venv/bin/activate
cd Proyecto_DSA_Grupo_30/"Entrega 2"
python3 src/entrega2.py --csv "../Entrega 1/Electric_Vehicle_Charging_Station_Data.csv" --tracking-uri http://localhost:8050
```

Interfaz: `http://<IP>:8050`. La selección del mejor modelo usa solo validación; el conjunto de prueba se reporta sin optimizar sobre él.

## Resultados

En `results/` se generan:

- `perfil_estaciones.csv`: criterios verificables y días sin registros de todas las estaciones.
- `cinco_estaciones.csv`: las cinco estaciones elegidas y sus estadísticas.
- `panel_diario_cinco_estaciones.csv`: serie diaria con la columna `sin_registro`.
- `metricas_modelos.csv`: MAE y RMSE en validación y prueba.
- `predicciones_prueba.csv`: serie que puede alimentar una simulación histórica.
- `modelo_seleccionado.joblib`: pipeline supervisado según MAE de validación.
- `resumen_ejecucion.json`: resumen y advertencias.

## Decisiones metodológicas pendientes de verificación

1. **Limpieza:** el informe 1 reportó 125.009 sesiones en 29 estaciones después de eliminar registros duplicados, sesiones con energía cero, cambios de nombre y estaciones asociadas a flota. Este script usa una regla conservadora de duplicados (estación, dirección, minuto, energía) y **NO conoce cuáles eran las 12 estaciones de flota**. Reconciliar cifras con el script original antes de presentarlas.
2. **Nombres:** fusiona `COMM VITALITY / ...` con `MUNICIPAL SC / ...` únicamente cuando ambas variantes existen. Comparar los identificadores con el trabajo original.
3. **Cinco estaciones:** el ranking prioriza días con actividad, tasa de cobertura y sesiones totales, exigiendo histórico anterior a 2022 y final posterior a mediados de 2023. Debe documentarse cuáles salieron, junto a la continuidad temporal.
4. **Días sin registros:** rellena solo fechas entre primera y última sesión, etiquetando `sin_registro=True`; la hipótesis cero requiere respaldo con evidencias de operación o evaluaciones de sensibilidad.
5. **Validación:** train hasta 2022-12-31; validación enero-junio 2023; prueba julio-noviembre 2023. Los lags se calculan con datos históricos y se usan valores reales pasados en evaluación de un paso (teacher forcing). Para un futuro real, la API necesitaría históricos actualizados.
6. **Comparación:** baseline de sesión del mismo día de la semana previa (lag 7), Ridge, RandomForest e HistGradientBoosting. Selección del mejor modelo SUPERVISADO con MAE de validación y reporte del desempeño de prueba sin optimizar allí.
7. **No filtrar nuevas señales del futuro:** solo se usan variables calendario y sesiones anteriores (`lag_1, lag_7, lag_14, media_7, media_14`).

## Seguimiento y Git

Subir `src/`, `requirements.txt`, `README.md` y los resultados **que hayan sido revisados**; los CSV crudos pueden versionarse con DVC de acuerdo con el repositorio del grupo. No subir `.venv/`, artefactos muy grandes ni credenciales AWS.

Capturas AWS: cuando se ejecuten experimentos reales en EC2, documentar de acuerdo con la guía usuario/IP de la instancia y URI/IP de MLflow; detener el proceso MLflow sin terminar la instancia, como indica la guía.

## API y tablero (prototipo funcional)

Una vez ejecutado el proceso de modelado, abrir **dos terminales adicionales** con el entorno activado, desde la raíz del paquete.

Terminal 1 — iniciar API:

```bash
uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Consultar estado en http://127.0.0.1:8000/health y documentación en http://127.0.0.1:8000/docs.

Terminal 2 — iniciar tablero:

```bash
streamlit run app/dashboard.py
```

El tablero consulta la API en el puerto 8000, permite elegir una de las cinco estaciones, seleccionar una fecha del **periodo histórico de prueba**, mostrar predicción, observar el conteo real e inspeccionar los días anteriores. En cada clic se llama al modelo en la API, sin mostrar un archivo de predicciones estáticas. Este prototipo no hace actualizaciones a producción ni predice fechas de 2026.

**Seguridad mínima:** ejecutar en `127.0.0.1` y no exponer FastAPI sin autenticación a Internet. No subir el modelo `.joblib` si no se ha verificado su procedencia. Para despliegue Docker habrá que definir imagen y mecanismos de protección en una fase posterior.
