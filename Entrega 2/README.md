# Entrega 2 — Proyecto de predicción de sesiones de recarga (Boulder)

## Propósito

Código inicial para preparar los datos de estaciones de Boulder, comparar modelos supervisados y registrar experimentos en MLflow. Este paquete **no reemplaza** la exploración original ni permite afirmar métricas sobre el CSV del grupo hasta ejecutarlo y contrastar sus resultados.

## Pasos en Windows (Git Bash o PowerShell)

1. Copiar el CSV del proyecto a `data/Electric_Vehicle_Charging_Station_Data.csv`.
2. Desde la carpeta `dsa_entrega2_base`, ejecutar:

```bash
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# Git Bash: source .venv/Scripts/activate
python -m pip install -r requirements.txt
python src/entrega2.py --csv data/Electric_Vehicle_Charging_Station_Data.csv
```

Si usan MLflow en EC2 con túnel SSH local activo:

```bash
python src/entrega2.py --csv data/Electric_Vehicle_Charging_Station_Data.csv --tracking-uri http://127.0.0.1:8050
```

**Importante:** la conexión a MLflow debe realizarse con el servidor realmente iniciado y accesible. No se ha ejecutado ningún experimento real contra EC2 desde aquí.

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
