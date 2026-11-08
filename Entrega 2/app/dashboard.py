"""EV Charging Analytics | tablero equilibrado en una sola pantalla de simulación histórica.

Reemplaza app/dashboard.py por este archivo. No modifica la API ni el modelo.
Requiere FastAPI en http://127.0.0.1:8000 (o configurar DSA_API_URL).
Las predicciones son retrospectivas; no representan pronósticos actuales.
"""
from __future__ import annotations

import os
from datetime import date

import altair as alt
import pandas as pd
import requests
import streamlit as st

API = os.getenv("DSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
VERDE = "#103c36"
TURQUESA = "#0e968b"

st.set_page_config(
    page_title="Predicción de sesiones de recarga de vehículos eléctricos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded")

# Espaciado equilibrado para pantallas de escritorio, sin amontonar títulos o filtros.
st.markdown("""
<style>
  .stApp { background: #f5f8f7; }
  .block-container {
    max-width: 100%;
    padding: .8rem 1.4rem .55rem !important;
  }
  [data-testid="stHeader"] { height: 2.1rem; background: transparent; }
  [data-testid="stSidebar"] { background: #103c36; }
  [data-testid="stSidebar"] * { color: #effcf8; }
  [data-testid="stSidebar"] .stRadio label { font-size: .88rem; }
  [data-testid="stVerticalBlock"] { gap: .72rem; }
  [data-testid="stHorizontalBlock"] { gap: .85rem; }
  h1, h2, h3 { color: #153e38; line-height: 1.3; }
  p { margin-bottom: .4rem; }
  [data-testid="stMetric"] {
    background: #e0f1ed; border: 1px solid #c9e4de;
    border-radius: 10px; padding: .64rem .78rem;
    min-height: 85px;
  }
  [data-testid="stMetricLabel"] { font-size: .78rem; line-height: 1.3; }
  [data-testid="stMetricValue"] { color: #08675e; font-size: 1.55rem; }
  [data-testid="stWidgetLabel"] { margin-bottom: .2rem !important; }
  div[data-baseweb="select"] > div,
  div[data-baseweb="input"] > div { min-height: 38px; }
  .stButton button[kind="primary"] {
    background: #0b8f84; border-color: #0b8f84;
    border-radius: 7px; width: 100%;
  }
  .stButton button { min-height: 38px; }
  .ev-header {
    background: #103c36; color: white; padding: .82rem 1.05rem .94rem;
    border-radius: 9px; min-height: 111px;
    margin-bottom: .55rem; box-sizing: border-box;
  }
  .ev-headline {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; text-align: center; gap: .16rem;
  }
  .ev-headline strong {
    display: block; width: 100%; text-align: center;
    font-size: clamp(1.4rem, 2vw, 1.85rem);
    font-weight: 750; line-height: 1.22; letter-spacing: .005em;
  }
  .ev-headline small { color: #b6e8dc; font-size: .78rem; }
  .ev-subtitle {
    color: #b6e8dc; margin-top: .3rem; font-size: .78rem;
    line-height: 1.35; text-align: center;
  }
  .ev-story {
    margin-top: .52rem; color: #e0f3ef; font-size: .84rem;
    line-height: 1.48; width: 100%; max-width: none;
    text-align: justify; box-sizing: border-box;
  }
  .ev-story b { color: #fff; }
  .ev-title {
    font-size: 1.1rem; font-weight: 700; color: #163f39;
    line-height: 1.4; padding: .42rem 0 .35rem;
    min-height: 2.15rem; box-sizing: border-box;
  }
  .ev-text { font-size: .81rem; color: #44635c; line-height: 1.4; }
  .ev-foot {
    font-size: .78rem; color: #355c54; background: #e8f2ef;
    border-left: 3px solid #07988b; padding: .58rem .8rem;
    border-radius: 4px; line-height: 1.4;
  }
  [data-testid="stAlert"] { padding: .4rem .7rem; }
  [data-testid="stAltairChart"] { margin: 0 !important; }
  hr { margin: .25rem 0 !important; }
  footer, #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=120, show_spinner=False)
def estaciones() -> list[dict]:
    resp = requests.get(f"{API}/stations", timeout=10)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=120, show_spinner=False)
def historico(estacion: str) -> pd.DataFrame:
    resp = requests.get(f"{API}/history", params={"estacion": estacion}, timeout=15)
    resp.raise_for_status()
    tabla = pd.DataFrame(resp.json())
    if tabla.empty:
        return tabla
    tabla["fecha"] = pd.to_datetime(tabla["fecha"])
    tabla["sesiones"] = pd.to_numeric(tabla["sesiones"], errors="coerce")
    tabla["cero_asumido"] = tabla["cero_asumido"].map(
        lambda x: x is True or str(x).lower() == "true")
    return tabla.sort_values("fecha").reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False)
def predecir(estacion: str, fecha: str) -> dict:
    # POST real al modelo: no se utilizan predicciones precalculadas.
    resp = requests.post(
        f"{API}/predict", json={"estacion": estacion, "fecha": fecha}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def ventana(tabla: pd.DataFrame, dia: pd.Timestamp, dias: int) -> pd.DataFrame:
    return tabla.loc[
        (tabla.fecha >= dia - pd.Timedelta(days=dias)) & (tabla.fecha < dia)
    ].copy()


def resumen(tabla: pd.DataFrame, dia: pd.Timestamp, dias: int = 30) -> dict:
    tramo = ventana(tabla, dia, dias)
    reales = tramo.loc[~tramo.cero_asumido]
    return {
        "media": float(reales.sesiones.mean()) if len(reales) else None,
        "total": int(reales.sesiones.sum()) if len(reales) else None,
        "registrados": len(reales),
        "sin_registro": int(tramo.cero_asumido.sum()),
        "dias": len(tramo),
    }


def numero(x: float | None, decimales: int = 1) -> str:
    return "N/D" if x is None or pd.isna(x) else f"{x:.{decimales}f}"


def grafica(
    tabla: pd.DataFrame, dia: pd.Timestamp, dias: int,
    prediccion: dict | None = None) -> None:
    # La línea representa exclusivamente días ANTERIORES a la fecha estimada.
    datos = tabla.loc[
        (tabla.fecha >= dia - pd.Timedelta(days=dias)) & (tabla.fecha < dia)
    ].copy()
    if datos.empty:
        st.warning("No hay datos en el periodo seleccionado.")
        return
    # Los ceros provisionales no se representan como observaciones reales.
    datos["observado"] = datos.sesiones.where(~datos.cero_asumido)
    datos["calidad"] = datos.cero_asumido.map(
        {True: "Sin registro (cero provisional)", False: "Con registro"})
    eje_x = alt.X("fecha:T", title=None, axis=alt.Axis(format="%d %b", labelAngle=0))
    eje_y = alt.Y("observado:Q", title="Sesiones", scale=alt.Scale(zero=True))
    linea = alt.Chart(datos).mark_line(color="white", strokeWidth=2.5, point=False).encode(
        x=eje_x, y=eje_y,
        tooltip=[alt.Tooltip("fecha:T", format="%Y-%m-%d"),
                 alt.Tooltip("observado:Q", title="Sesiones", format=".0f"),
                 alt.Tooltip("calidad:N")])
    base = linea
    no_registro = datos.loc[datos.cero_asumido].copy()
    if not no_registro.empty:
        no_registro["marcador"] = 0
        base += alt.Chart(no_registro).mark_point(
            color="#ffcf7a", filled=True, shape="square", size=45
        ).encode(x="fecha:T", y="marcador:Q",
                 tooltip=["fecha:T", alt.Tooltip("calidad:N")])
    base += alt.Chart(pd.DataFrame({"fecha": [dia]})).mark_rule(
        color="#d1fff5", strokeDash=[4, 4], opacity=.7
    ).encode(x="fecha:T")
    if prediccion is not None:
        # El modelo estima SOLO la fecha objetivo; no dibujamos 60 predicciones.
        estimado = pd.DataFrame({
            "fecha": [dia], "valor": [float(prediccion["prediccion_sesiones"])]})
        base += alt.Chart(estimado).mark_point(
            color="#ffd05b", filled=True, shape="diamond", size=170
        ).encode(x="fecha:T", y=alt.Y("valor:Q"),
                 tooltip=[alt.Tooltip("valor:Q", title="Estimación de la fecha objetivo", format=".2f")])
        if not prediccion["observacion_es_cero_asumido"]:
            real = pd.DataFrame({
                "fecha": [dia], "valor": [float(prediccion["observado_historico"])]})
            base += alt.Chart(real).mark_point(
                color="white", filled=True, shape="circle", size=145,
                stroke=VERDE, strokeWidth=1.3
            ).encode(x="fecha:T", y=alt.Y("valor:Q"),
                     tooltip=[alt.Tooltip("valor:Q", title="Sesiones observadas en la fecha", format=".0f")])
    st.altair_chart(
        base.properties(height=228, background=TURQUESA)
        .configure_axis(labelColor="white", titleColor="white", gridColor="#52b6ad",
                        domainColor="#b5e9e3", tickColor="#b5e9e3")
        .configure_view(stroke=None),
        use_container_width=True)


def franja(mensaje: str) -> None:
    st.markdown(f'<div class="ev-foot">{mensaje}</div>', unsafe_allow_html=True)


with st.sidebar:
    st.markdown("**Navegación**")
    seccion = st.radio(
        "Sección", ["Panel principal", "Análisis histórico", "Simulación por fecha"],
        label_visibility="collapsed")
    st.caption("Datos: Boulder, hasta noviembre de 2023")
    st.caption("Simulaciones históricas, no pronósticos actuales")

st.markdown("""
<div class="ev-header">
  <div class="ev-headline">
    <strong>Predicción de sesiones de recarga de vehículos eléctricos</strong>
    <small>EV Charging Analytics</small>
  </div>
  <div class="ev-subtitle">
    Cinco estaciones públicas de Boulder, Colorado | Simulación retrospectiva con datos hasta noviembre de 2023
  </div>
  <div class="ev-story">
    La planificación operativa de las estaciones públicas de recarga requiere comprender cómo varía su utilización para orientar
    la disponibilidad del servicio y la asignación de recursos. Este tablero analiza el comportamiento de las sesiones diarias en
    cinco estaciones de Boulder, Colorado, y permite contrastar estimaciones con registros históricos para identificar patrones de
    demanda y evaluar su utilidad en la toma de decisiones. Las estimaciones corresponden a fechas históricas y no representan pronósticos de la demanda actual.
    Elaborado por: Johan Vargas, Daniel Aguirre, Daneyro Culchac
      </div>
</div>
""", unsafe_allow_html=True)

try:
    lista = estaciones()
except (requests.RequestException, ValueError) as exc:
    st.error(f"No se pudo conectar con FastAPI ({API}). Verifica el servidor. Detalle: {exc}")
    st.stop()
if not lista:
    st.error("La API no devolvió estaciones disponibles.")
    st.stop()
mapa = {x["estacion"]: x for x in lista}

st.markdown(f'<div class="ev-title">{seccion}</div>', unsafe_allow_html=True)

# Filtros y consulta en la misma fila para ahorrar altura.
f1, f2, f3 = st.columns([2.7, 1.2, 1.0], vertical_alignment="bottom")
with f1:
    seleccion = st.selectbox("Estación", list(mapa), key="estacion")
with f2:
    conf = mapa[seleccion]
    fecha_min = pd.Timestamp(conf["fecha_min"]).date()
    fecha_max = pd.Timestamp(conf["fecha_max"]).date()
    fecha = st.date_input(
        "Fecha objetivo", value=fecha_max, min_value=fecha_min,
        max_value=fecha_max, key=f"fecha_{seleccion}")
with f3:
    if seccion == "Análisis histórico":
        periodo = st.selectbox("Periodo", [30, 60, 90], index=1, format_func=lambda n: f"{n} días")
    else:
        recalc = st.button("Consultar estimación", type="primary")
        if recalc:
            predecir.clear()
        periodo = 60

objetivo = pd.Timestamp(fecha)
try:
    datos = historico(seleccion)
except (requests.RequestException, ValueError) as exc:
    st.error(f"No fue posible consultar el histórico. Detalle: {exc}")
    st.stop()
if datos.empty:
    st.warning("No existen datos para esta estación.")
    st.stop()

stats = resumen(datos, objetivo)
resultado = None
if seccion != "Análisis histórico":
    try:
        # La API infiere con rezagos hasta el día anterior al seleccionado.
        resultado = predecir(seleccion, str(fecha))
    except requests.RequestException as exc:
        st.warning(f"No es posible simular esa fecha: {exc}")

pred = float(resultado["prediccion_sesiones"]) if resultado else None
observado = (
    float(resultado["observado_historico"])
    if resultado and not resultado["observacion_es_cero_asumido"] else None)
variacion = (
    100 * (pred - stats["media"]) / stats["media"]
    if pred is not None and stats["media"] is not None and stats["media"] > 0
    else None)

if seccion == "Panel principal":
    a, b, c, d = st.columns(4)
    a.metric("Promedio diario | 30 días con registro", numero(stats["media"]))
    b.metric("Estimación para el día elegido", numero(pred))
    c.metric("Variación frente al promedio", "N/D" if variacion is None else f"{variacion:+.1f}%")
    d.metric("Observado en el día elegido", numero(observado, 0))
    st.markdown(
        f'<div class="ev-title">60 días anteriores y estimación puntual para el {fecha:%d/%m/%Y}</div>',
        unsafe_allow_html=True)
    grafica(datos, objetivo, 60, resultado)
    cobertura = f'{stats["registrados"]}/{stats["dias"]}'
    diferencia = numero(pred - observado, 2) if pred is not None and observado is not None else "N/D"
    if resultado is not None:
        marca_real = ('círculo blanco = observado del día seleccionado' if observado is not None
                      else 'sin registro confirmado en el día seleccionado')
        franja(
            f'<b>Lectura:</b> línea blanca = 60 días históricos previos | rombo amarillo = estimación solo para '
            f'{fecha:%d/%m/%Y} | {marca_real} | diferencia estimado - observado: '
            f'{diferencia} sesiones | cobertura previa (30 días): {cobertura}. '
            '<b>La línea no representa predicciones.</b>')
    else:
        franja('<b>Lectura:</b> la línea blanca muestra 60 días anteriores. '
               'No se dispone de una estimación para la fecha seleccionada.')

elif seccion == "Análisis histórico":
    a, b, c, d = st.columns(4)
    a.metric("Promedio diario | días con registro", numero(stats["media"]))
    b.metric("Sesiones registradas | últimos 30 días", str(stats["total"]) if stats["total"] is not None else "N/D")
    c.metric("Días con registro | últimos 30", str(stats["registrados"]))
    d.metric("Días sin registro | últimos 30", str(stats["sin_registro"]))
    izquierda, derecha = st.columns([1.6, 1.0], gap="medium")
    with izquierda:
        st.markdown('<div class="ev-title">Evolución de la estación</div>', unsafe_allow_html=True)
        grafica(datos, objetivo, periodo)
    with derecha:
        st.markdown('<div class="ev-title">Comparación de cinco estaciones</div>', unsafe_allow_html=True)
        filas = []
        for item in lista:
            estacion = item["estacion"]
            try:
                otra = historico(estacion)
                r = resumen(otra, objetivo, 30)
                if r["media"] is not None:
                    filas.append({"Estación": estacion.replace("BOULDER / ", ""),
                                  "Media": r["media"],
                                  "Cobertura": f'{r["registrados"]}/{r["dias"]}'})
            except requests.RequestException:
                continue
        if filas:
            comparacion = pd.DataFrame(filas)
            barras = alt.Chart(comparacion).mark_bar(color=TURQUESA).encode(
                y=alt.Y("Estación:N", sort="-x", title=None,
                        axis=alt.Axis(labelLimit=160, labelFontSize=10)),
                x=alt.X("Media:Q", title="Sesiones/día con registro"),
                tooltip=["Estación:N", alt.Tooltip("Media:Q", format=".2f"), "Cobertura:N"],
            ).properties(height=200)
            st.altair_chart(barras, use_container_width=True)
        else:
            st.info("No hay comparación disponible para este periodo.")
    franja(
        '<b>Calidad de datos:</b> los promedios excluyen días sin registro; '
        'la ausencia de una sesión registrada no demuestra inactividad de una estación. '
        'Comparación descriptiva, no ranking de capacidad disponible.')

else:  # Simulación por fecha
    a, b, c, d = st.columns(4)
    a.metric("Sesiones estimadas en fecha objetivo", numero(pred, 2))
    b.metric("Sesiones observadas en ese día", numero(observado, 0))
    c.metric("Referencia hace 7 días", numero(
        float(resultado["referencia_7_dias"]) if resultado else None, 0))
    d.metric("Diferencia estimación - observado", numero(
        pred - observado if pred is not None and observado is not None else None, 2))
    st.markdown(
        f'<div class="ev-title">60 días de contexto histórico y estimación del {fecha:%d/%m/%Y}</div>',
        unsafe_allow_html=True)
    grafica(datos, objetivo, 60, resultado)
    estado = (
        'Sin dato observado confiable en la fecha seleccionada: cero provisional.'
        if resultado and resultado["observacion_es_cero_asumido"]
        else 'La comparación utiliza el dato observado únicamente para evaluación.')
    if resultado is not None:
        punto_real = ('el círculo blanco marca el registro de ese día' if observado is not None
                      else 'no hay dato registrado confirmado para ese día')
        franja(
            f'<b>Lectura:</b> la línea muestra los 60 días previos; el rombo amarillo estima únicamente '
            f'las sesiones del {fecha:%d/%m/%Y}; {punto_real}. {estado} '
            '<b>No hay predicciones para los 60 días ni pronósticos actuales.</b>')
    else:
        franja('<b>Lectura:</b> la línea muestra los 60 días anteriores a la fecha indicada; '
               'no hay estimación disponible para el día seleccionado.')


with st.expander("Ficha técnica y calidad de la estimación", expanded=False):
    st.markdown(
        "- **Ámbito:** cinco estaciones públicas de recarga de Boulder, Colorado.\n"
        "- **Modelo seleccionado:** Ridge, por su menor MAE en validación.\n"
        "- **Periodo de evaluación:** julio a noviembre de 2023 (765 observaciones estación-día).\n"
        "- **MAE de validación:** 1,43 sesiones por estación y día.\n"
        "- **MAE de prueba:** 1,53 sesiones por estación y día.\n"
        "- **RMSE de prueba:** 1,96 sesiones.\n"
        "- **Referencia semanal:** MAE de prueba de 2,06 sesiones.\n"
        "- **Horizonte de la estimación:** un único día histórico seleccionado (no 60 días).\n"
        "- **Gráfica:** 60 días anteriores como contexto; marcador amarillo para la estimación puntual.\n"
        "- **Alcance y limitaciones:** simulación histórica, no pronóstico actual. Los datos terminan en "
        "noviembre de 2023 y algunos días sin registro requieren cautela al interpretarlos.")
