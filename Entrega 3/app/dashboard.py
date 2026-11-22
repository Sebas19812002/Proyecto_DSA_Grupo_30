"""Tablero de análisis y simulación histórica de sesiones de recarga.

Requiere FastAPI y la variable DSA_API_URL para la conexión entre contenedores.
Los filtros se aplican mediante los botones de consulta y no al editarlos.
Los resultados corresponden a fechas históricas, no a pronósticos actuales.
"""
from __future__ import annotations

import os
from pathlib import Path
import altair as alt
import pandas as pd
import requests
import streamlit as st

API = os.getenv("DSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
VERDE = "#103C36"
TURQUESA = "#0E968B"
IMAGEN_PORTADA = Path(__file__).resolve().parent / "assets" / "portada_recarga.jpg"

st.set_page_config(
    page_title="Predicción de sesiones de recarga de vehículos eléctricos",
    layout="wide",
    initial_sidebar_state="expanded")

# Espaciado equilibrado para pantallas de escritorio, sin amontonar títulos o filtros.
st.markdown("""
<style>
  .stApp { background: #F5F8F7; }
  .block-container {
    max-width: 100%;
    padding: .8rem 1.4rem .55rem !important;
  }
  [data-testid="stHeader"] { height: 2.8rem; background: transparent; z-index: 9998; }
  /* Mantiene visible el control de cierre de la barra lateral. */
  [data-testid="stSidebarCollapseButton"] {
    visibility: visible !important;
    opacity: 1 !important;
  }
  [data-testid="stSidebarCollapseButton"] button {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 40px !important;
    min-width: 40px !important;
    height: 40px !important;
    padding: 0 !important;
    background-color: #E0F1ED !important;
    border: 1px solid #B6DED4 !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 7px rgba(0, 0, 0, .12) !important;
  }
  [data-testid="stSidebarCollapseButton"] button :is(svg, span, i) {
    color: #103C36 !important;
    fill: currentColor !important;
  }
  [data-testid="stSidebarCollapseButton"] button:hover {
    background-color: #B6E8DC !important;
    border-color: #0E968B !important;
  }
  /* Streamlit 1.67: boton real para abrir el panel cerrado. */
  button[data-testid="stExpandSidebarButton"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 42px !important;
    min-width: 42px !important;
    height: 42px !important;
    padding: 0 !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: #FFFFFF !important;
    background-color: #103C36 !important;
    border: 1px solid #0E968B !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 9px rgba(16, 60, 54, .22) !important;
    cursor: pointer !important;
    pointer-events: auto !important;
  }
  button[data-testid="stExpandSidebarButton"] :is(svg, span, i) {
    color: #FFFFFF !important;
    fill: currentColor !important;
  }
  button[data-testid="stExpandSidebarButton"]:hover {
    background-color: #17574D !important;
    border-color: #B6E8DC !important;
  }
  :is(button[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] button):focus-visible {
    outline: 2px solid #0E968B !important;
    outline-offset: 2px !important;
  }
  /* Al cerrar el menu, reserva espacio para que el boton no se superponga al titulo. */
  .stApp:has([data-testid="stSidebar"][data-collapsed="true"]) .block-container {
    padding-top: 3.7rem !important;
  }
  [data-testid="stSidebar"] { background: #103C36; }
  [data-testid="stSidebar"] * { color: #EFFCF8; }
  [data-testid="stSidebar"] .stRadio label { font-size: .88rem; }
  [data-testid="stVerticalBlock"] { gap: .72rem; }
  [data-testid="stHorizontalBlock"] { gap: .85rem; }
  h1, h2, h3 { color: #153E38; line-height: 1.3; }
  p { margin-bottom: .4rem; }
  [data-testid="stMetric"] {
    background: #E0F1ED; border: 1px solid #C9E4DE;
    border-radius: 10px; padding: .64rem .78rem;
    min-height: 98px;
  }
  [data-testid="stMetricLabel"] { font-size: .78rem; line-height: 1.35; min-height: 2.2rem; }
  [data-testid="stMetricValue"] { color: #08675E; font-size: 1.55rem; }
  [data-testid="stWidgetLabel"] { margin-bottom: .2rem !important; }
  div[data-baseweb="select"] > div,
  div[data-baseweb="input"] > div { min-height: 38px; }
  /* Colores del botón de consulta. El tema se refuerza en .streamlit/config.toml. */
  :is([data-testid="stFormSubmitButton"], .stFormSubmitButton, .st-key-boton_consulta_dsa) button,
  button[data-testid="stBaseButton-primaryFormSubmit"],
  button[data-testid="stBaseButton-primary"],
  button[kind="primaryFormSubmit"],
  button[kind="primary"] {
    background: #103C36 !important;
    background-color: #103C36 !important;
    border: 1px solid #103C36 !important;
    color: #FFFFFF !important;
    border-radius: 8px;
    min-height: 40px;
    width: 100%;
    font-weight: 650;
    box-shadow: none !important;
    transition: background-color .16s ease, border-color .16s ease;
  }
  :is([data-testid="stFormSubmitButton"], .stFormSubmitButton, .st-key-boton_consulta_dsa) button:hover,
  button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
  button[data-testid="stBaseButton-primary"]:hover,
  button[kind="primaryFormSubmit"]:hover,
  button[kind="primary"]:hover {
    background: #17574D !important;
    background-color: #17574D !important;
    border-color: #17574D !important;
    color: #FFFFFF !important;
  }
  :is([data-testid="stFormSubmitButton"], .stFormSubmitButton, .st-key-boton_consulta_dsa) button:active,
  button[data-testid="stBaseButton-primaryFormSubmit"]:active,
  button[kind="primaryFormSubmit"]:active {
    background: #0B302B !important;
    border-color: #0B302B !important;
  }
  :is([data-testid="stFormSubmitButton"], .stFormSubmitButton, .st-key-boton_consulta_dsa) button:focus-visible,
  button[data-testid="stBaseButton-primaryFormSubmit"]:focus-visible {
    outline: 2px solid #0E968B !important;
    outline-offset: 2px;
  }
  :is([data-testid="stFormSubmitButton"], .stFormSubmitButton, .st-key-boton_consulta_dsa) button :is(p,span),
  button[data-testid="stBaseButton-primaryFormSubmit"] :is(p,span),
  button[kind="primary"] :is(p,span) { color: #FFFFFF !important; }
  [data-testid="stMetric"] {
    box-shadow: 0 1px 3px rgba(16, 60, 54, .04);
  }
  .ev-header {
    background: #103C36; color: white; padding: .82rem 1.05rem .94rem;
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
  .ev-headline small { color: #B6E8DC; font-size: .78rem; }
  .ev-subtitle {
    color: #B6E8DC; margin-top: .3rem; font-size: .78rem;
    line-height: 1.35; text-align: center;
  }
  .ev-story {
    margin-top: .52rem; color: #E0F3EF; font-size: .84rem;
    line-height: 1.48; width: 100%; max-width: none;
    text-align: justify; box-sizing: border-box;
  }
  .ev-story b { color: #fff; }
  .ev-title {
    font-size: 1.1rem; font-weight: 700; color: #163F39;
    line-height: 1.4; padding: .42rem 0 .35rem;
    min-height: 2.15rem; box-sizing: border-box;
  }
  .ev-text { font-size: .81rem; color: #44635C; line-height: 1.4; }
  .ev-foot {
    font-size: .78rem; color: #355C54; background: #E8F2EF;
    border-left: 3px solid #0E968B; padding: .58rem .8rem;
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
        (tabla.fecha >= dia - pd.Timedelta(days=dias)) & (tabla.fecha < dia)].copy()


def resumen(tabla: pd.DataFrame, dia: pd.Timestamp, dias: int = 30) -> dict:
    tramo = ventana(tabla, dia, dias)
    reales = tramo.loc[~tramo.cero_asumido]
    return {
        "media": float(reales.sesiones.mean()) if len(reales) else None,
        "total": int(reales.sesiones.sum()) if len(reales) else None,
        "registrados": len(reales),
        "sin_registro": int(tramo.cero_asumido.sum()),
        "dias": len(tramo)}


def numero(x: float | None, decimales: int = 1) -> str:
    return "N/D" if x is None or pd.isna(x) else f"{x:.{decimales}f}"


def grafica(
    tabla: pd.DataFrame, dia: pd.Timestamp, dias: int,
    prediccion: dict | None = None) -> None:
    # La línea representa exclusivamente días ANTERIORES a la fecha estimada.
    datos = tabla.loc[
        (tabla.fecha >= dia - pd.Timedelta(days=dias)) & (tabla.fecha < dia)].copy()
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
            color="#ffcf7a", filled=True, shape="square", size=45).encode(
            x="fecha:T", y="marcador:Q",
                 tooltip=["fecha:T", alt.Tooltip("calidad:N")])
    base += alt.Chart(pd.DataFrame({"fecha": [dia]})).mark_rule(
        color="#d1fff5", strokeDash=[4, 4], opacity=.7).encode(x="fecha:T")
    if prediccion is not None:
        # El modelo estima SOLO la fecha objetivo; no dibujamos 60 predicciones.
        estimado = pd.DataFrame({
            "fecha": [dia], "valor": [float(prediccion["prediccion_sesiones"])]})
        base += alt.Chart(estimado).mark_point(
            color="#ffd05b", filled=True, shape="diamond", size=170).encode(
            x="fecha:T", y=alt.Y("valor:Q"),
                 tooltip=[alt.Tooltip("valor:Q", title="Estimación de la fecha objetivo", format=".2f")])
        if not prediccion["observacion_es_cero_asumido"]:
            real = pd.DataFrame({
                "fecha": [dia], "valor": [float(prediccion["observado_historico"])]})
            base += alt.Chart(real).mark_point(
                color="white", filled=True, shape="circle", size=145,
                stroke=VERDE, strokeWidth=1.3).encode(
                x="fecha:T", y=alt.Y("valor:Q"),
                     tooltip=[alt.Tooltip("valor:Q", title="Sesiones observadas en la fecha", format=".0f")])
    st.altair_chart(
        base.properties(height=228, background=TURQUESA)
        .configure_axis(labelColor="white", titleColor="white", gridColor="#52b6ad",
                        domainColor="#b5e9e3", tickColor="#b5e9e3")
        .configure_view(stroke=None),
        use_container_width=True)


def grafica_dia_semana(tabla: pd.DataFrame, dia: pd.Timestamp, dias: int) -> None:
    """Promedio de sesiones por día de la semana con registros confirmados."""

    datos = ventana(tabla, dia, dias)
    datos = datos.loc[
        (~datos["cero_asumido"]) & datos["sesiones"].notna()].copy()

    if datos.empty:
        st.info("No hay registros confirmados para analizar este periodo.")
        return

    nombres = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo"}

    datos["dia_numero"] = datos["fecha"].dt.dayofweek
    datos["dia_semana"] = datos["dia_numero"].map(nombres)

    resumen_dias = (datos.groupby(["dia_numero", "dia_semana"], as_index=False)
        .agg(promedio_sesiones=("sesiones", "mean"), dias_registrados=("sesiones", "count"))
        .sort_values("dia_numero"))

    orden = list(nombres.values())

    grafico = (alt.Chart(resumen_dias)
        .mark_bar(color=TURQUESA, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("dia_semana:N", sort=orden, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("promedio_sesiones:Q", title="Promedio de sesiones"),
            tooltip=[
                alt.Tooltip("dia_semana:N", title="Día"),
                alt.Tooltip("promedio_sesiones:Q", title="Promedio de sesiones", format=".2f"),
                alt.Tooltip("dias_registrados:Q", title="Días con registro")])
        .properties(height=260))

    st.altair_chart(grafico, use_container_width=True)

    st.caption(
        f"Promedio calculado con {len(datos)} días con registro "
        f"en los {dias} días anteriores a la fecha seleccionada. "
        "Se excluyen los días sin registro confirmado.")


def franja(mensaje: str) -> None:
    st.markdown(f'<div class="ev-foot">{mensaje}</div>', unsafe_allow_html=True)


# La portada es una vista de entrada; la API solo se consulta al ingresar a los paneles.
if "pantalla_dsa" not in st.session_state:
    st.session_state["pantalla_dsa"] = "inicio"

if st.session_state["pantalla_dsa"] == "inicio":
    st.markdown("""
    <style>
      .block-container {
        max-width: 1200px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding: .45rem 1.5rem 1.6rem !important;
      }
      [data-testid="stSidebar"],
      [data-testid="stSidebarCollapsedControl"],
      button[data-testid="stExpandSidebarButton"] { display: none !important; }
      [data-testid="stHeader"] { display: none !important; }
      .ev-landing-title {
        color: #103C36;
        margin: 0 auto .85rem;
        max-width: 1100px;
        font-size: clamp(1.55rem, 2.4vw, 2.5rem);
        font-weight: 750;
        line-height: 1.16;
        letter-spacing: -.017em;
        text-align: center;
      }
      .st-key-portada_foto [data-testid="stImage"] img {
        display: block;
        width: 100%;
        height: min(30vw, 315px);
        min-height: 220px;
        object-fit: cover;
        object-position: center 48%;
        border-radius: 12px;
      }
      .st-key-portada_foto [data-testid="stImage"] { width: 100%; }
      .ev-landing-caption { text-align: right; font-size: .72rem; color: #657F79; margin-top: -.2rem; }
      .ev-landing-caption a, .ev-landing-footer a { color: #0B786E; text-decoration: underline; }
      .ev-landing-intro {
        font-size: .96rem;
        line-height: 1.64;
        color: #284C46;
        margin: .3rem 0 .7rem;
        max-width: 1100px;
      }
      .ev-landing-scope {
        font-size: .85rem;
        line-height: 1.6;
        color: #4C6B64;
        padding: 0 0 0 1.1rem;
        margin: .25rem 0 .2rem;
        list-style: disc outside;
      }
      .ev-landing-scope li { margin: 0 0 .28rem; }
      .ev-landing-scope li::marker { color: #0E968B; }
      .ev-landing-footer {
        border-top: 1px solid #CFDFDA;
        margin-top: 1rem;
        padding-top: .95rem;
        color: #496760;
        font-size: .78rem;
        line-height: 1.6;
      }
      .ev-landing-footer strong {
        display: block;
        font-size: .83rem;
        color: #103C36;
        margin-bottom: .3rem;
      }
      .st-key-entrar_tablero button {
        width: 100%;
        min-height: 44px;
        background: #103C36 !important;
        border-color: #103C36 !important;
        color: white !important;
      }
      .st-key-entrar_tablero button:hover { background: #17574D !important; }
      @media (max-width: 720px) {
        .block-container { padding: 1rem .8rem !important; }
        .ev-landing-title { font-size: 1.48rem; text-align: left; }
        .st-key-portada_foto [data-testid="stImage"] img { height: 230px; }
        .ev-landing-caption { text-align: left; }
      }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <h1 class="ev-landing-title">PREDICCIÓN DEL NÚMERO DIARIO DE SESIONES DE RECARGA DE
    VEHÍCULOS ELÉCTRICOS EN ESTACIONES DE BOULDER, COLORADO</h1>
    """, unsafe_allow_html=True)

    with st.container(key="portada_foto"):
        st.image(str(IMAGEN_PORTADA), use_container_width=True)
        st.markdown("""
        <div class="ev-landing-caption">Imagen tomada de:
        <a href="https://www.facebook.com/share/p/1FHnCLhvJP/" target="_blank" rel="noopener noreferrer">https://www.facebook.com/share/p/1FHnCLhvJP/</a></div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="ev-landing-intro">
      La planificación operativa de las estaciones públicas de recarga requiere comprender cómo varía su utilización para orientar la disponibilidad del servicio y la asignación de recursos. Este tablero muestra el comportamiento de las sesiones diarias en cinco estaciones de Boulder, Colorado, y permite contrastar estimaciones con registros históricos para identificar patrones de demanda y evaluar su utilidad en la toma de decisiones. Las estimaciones corresponden a fechas históricas y no representan pronósticos de la demanda actual.
    </div>
    """, unsafe_allow_html=True)

    contexto, acceso = st.columns([3.5, 1.0], gap="large", vertical_alignment="center")
    with contexto:
        st.markdown("""
        <ul class="ev-landing-scope">
          <li>El prototipo analiza cinco estaciones seleccionadas por la continuidad de sus registros, con información disponible hasta noviembre de 2023.</li>
          <li>Utiliza un modelo Ridge (α = 0,1) para realizar estimaciones retrospectivas de un día.</li>
        </ul>
        """, unsafe_allow_html=True)
    with acceso:
        if st.button("Ingresar al tablero", type="primary", use_container_width=True, key="entrar_tablero"):
            st.session_state["pantalla_dsa"] = "tablero"
            st.rerun()

    st.markdown('<div class="ev-landing-footer"></div>', unsafe_allow_html=True)
    fuente, equipo = st.columns([1.15, 1.0], gap="large")
    with fuente:
        st.markdown("""
        <div class="ev-landing-footer" style="border:0; margin:0; padding:0;">
          <strong>Fuente y alcance</strong>
          Electric Vehicle Charging Station Data, datos abiertos de la ciudad de Boulder:
          <a href="https://open-data.bouldercolorado.gov/datasets/95992b3938be4622b07f0b05eba95d4c_0/about"
             target="_blank" rel="noopener noreferrer">consultar conjunto de datos</a>.
          La base original comprende 148.136 registros entre 2018 y noviembre de 2023.
        </div>
        """, unsafe_allow_html=True)
    with equipo:
        st.markdown("""
        <div class="ev-landing-footer" style="border:0; margin:0; padding:0;">
          <strong>Equipo de desarrollo</strong>
          Johan Vargas, Daniel Aguirre, Daneyro Culchac<br>
          Maestría en Inteligencia Analítica de Datos — Universidad de los Andes<br>
          FastAPI - Streamlit - Docker - MLflow
        </div>
        """, unsafe_allow_html=True)

    st.stop()

with st.sidebar:
    st.markdown("**Navegación**")
    seccion = st.radio(
        "Sección", ["Panel principal", "Análisis histórico", "Simulación por fecha"],
        label_visibility="collapsed")
    st.caption("Datos: Boulder, hasta noviembre de 2023")
    st.caption("Simulaciones históricas, no pronósticos actuales")
    st.markdown("---")
    if st.button("Volver al inicio", key="volver_portada_dsa", use_container_width=True):
        st.session_state["pantalla_dsa"] = "inicio"
        st.rerun()

DESCRIPCIONES_PANEL = {
    "Panel principal": (
        "Este panel ofrece una visión general de la actividad de recarga de la estación elegida, "
        "muestra el promedio diario reciente, las sesiones estimadas para una fecha histórica y "
        "cuánto se alejan del comportamiento habitual. También permite ver la evolución de los "
        "60 días anteriores, para dar contexto a los resultados. Elige una estación y una fecha, "
        "y pulsa «Consultar estimación»."),
    "Análisis histórico": (
        "Este panel permite ver cómo ha cambiado la actividad de recarga con el tiempo, identificar "
        "los días de mayor y menor uso y comparar el comportamiento de las cinco estaciones. "
        "Incluye indicadores de sesiones registradas y de cobertura de datos, además de los "
        "patrones de actividad según el día de la semana. Elige una estación, una fecha y un período "
        "(30, 60 o 90 días), y pulsa «Consultar análisis»."),
    "Simulación por fecha": (
        "Este panel permite evaluar la estimación del modelo para un día histórico específico: "
        "compara las sesiones previstas con las realmente registradas y con la actividad de siete "
        "días antes. Además, muestra la diferencia entre la estimación y el valor observado, junto "
        "con la evolución de los 60 días anteriores. Elige una estación y una fecha, y pulsa "
        "«Consultar estimación».")}

st.markdown(f"""
<div class="ev-header">
  <div class="ev-headline">
    <strong>Predicción de sesiones de recarga de vehículos eléctricos</strong>
    <small>EV Charging Analytics</small>
  </div>
  <div class="ev-subtitle">Datos hasta noviembre de 2023 de cinco estaciones públicas de Boulder, Colorado</div>
  <div class="ev-story">{DESCRIPCIONES_PANEL[seccion]}</div>
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

# Los filtros se preparan dentro de un formulario. El tablero solo aplica
# nuevas selecciones cuando se pulsa el botón de consulta.
primera_estacion = next(iter(mapa))
fecha_inicial = pd.Timestamp(mapa[primera_estacion]["fecha_max"]).date()
fecha_min_global = min(pd.Timestamp(x["fecha_min"]).date() for x in lista)
fecha_max_global = max(pd.Timestamp(x["fecha_max"]).date() for x in lista)

# La consulta confirmada se mantiene al cambiar de sección en la barra lateral.
if "consulta_aplicada" not in st.session_state:
    st.session_state["consulta_aplicada"] = {
        "estacion": primera_estacion,
        "fecha": fecha_inicial.isoformat(),
        "periodo": 60}
consulta_actual = st.session_state["consulta_aplicada"]

# Se usan claves distintas para los controles y los resultados aplicados.
if "filtro_estacion" not in st.session_state:
    st.session_state["filtro_estacion"] = consulta_actual["estacion"]
if "filtro_fecha" not in st.session_state:
    st.session_state["filtro_fecha"] = pd.Timestamp(consulta_actual["fecha"]).date()
if seccion == "Análisis histórico" and "filtro_periodo" not in st.session_state:
    st.session_state["filtro_periodo"] = consulta_actual["periodo"]

with st.form("formulario_consulta", border=False):
    if seccion == "Análisis histórico":
        f1, f2, f3, f4 = st.columns([2.5, 1.3, 1.0, 1.6], vertical_alignment="bottom")
    else:
        f1, f2, f4 = st.columns([2.7, 1.3, 1.6], vertical_alignment="bottom")

    with f1:
        estacion_elegida = st.selectbox(
            "Estación", list(mapa), key="filtro_estacion")
    with f2:
        # Un formulario no cambia dinámicamente el rango de fechas al seleccionar
        # otra estación. Se permite el rango global y se valida al consultar.
        fecha_elegida = st.date_input(
            "Fecha objetivo", min_value=fecha_min_global,
            max_value=fecha_max_global, key="filtro_fecha")
    periodo_elegido = consulta_actual["periodo"]
    if seccion == "Análisis histórico":
        with f3:
            periodo_elegido = st.selectbox(
                "Periodo", [30, 60, 90], index=1,
                format_func=lambda n: f"{n} días", key="filtro_periodo")
    with f4:
        etiqueta_boton = (
            "Consultar análisis" if seccion == "Análisis histórico"
            else "Consultar estimación")
        consultar = st.form_submit_button(
            etiqueta_boton, type="primary", use_container_width=True, key="boton_consulta_dsa")

if consultar:
    limites = mapa[estacion_elegida]
    fecha_min_estacion = pd.Timestamp(limites["fecha_min"]).date()
    fecha_max_estacion = pd.Timestamp(limites["fecha_max"]).date()
    if not fecha_min_estacion <= fecha_elegida <= fecha_max_estacion:
        st.warning(
            f"La estación seleccionada tiene registros entre "
            f"{fecha_min_estacion:%d/%m/%Y} y {fecha_max_estacion:%d/%m/%Y}. "
            "Elige una fecha dentro de ese intervalo y vuelve a consultar. "
            "Se mantienen los resultados de la última consulta válida.")
    else:
        st.session_state["consulta_aplicada"] = {
            "estacion": estacion_elegida,
            "fecha": fecha_elegida.isoformat(),
            "periodo": periodo_elegido}
        # Cada consulta solicitada vuelve a pedir la predicción a FastAPI.
        if seccion != "Análisis histórico":
            predecir.clear()

# El resto del tablero SIEMPRE utiliza los filtros confirmados, no los que
# todavía están editándose en el formulario.
consulta_actual = st.session_state["consulta_aplicada"]
seleccion = consulta_actual["estacion"]
fecha = pd.Timestamp(consulta_actual["fecha"]).date()
periodo = consulta_actual["periodo"]
if seccion == "Análisis histórico":
    st.caption(
        f"Última consulta: {seleccion}. Período analizado: "
        f"{periodo} días anteriores al {fecha:%d/%m/%Y}.")
else:
    st.caption(f"Resultados de la última consulta: {seleccion}. Fecha: {fecha:%d/%m/%Y}.")

objetivo = pd.Timestamp(fecha)
try:
    datos = historico(seleccion)
except (requests.RequestException, ValueError) as exc:
    st.error(f"No fue posible consultar el histórico. Detalle: {exc}")
    st.stop()
if datos.empty:
    st.warning("No existen datos para esta estación.")
    st.stop()

stats = resumen(datos, objetivo, periodo if seccion == "Análisis histórico" else 30)
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
        f'<div class="ev-title">Estimación de número de sesiones para el {fecha:%d/%m/%Y} con su comportamiento en 60 días anteriores.</div>',
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

elif seccion == "Análisis histórico":
    a, b, c, d = st.columns(4)
    a.metric("Promedio de sesiones por día con registro", numero(stats["media"]))
    b.metric(f"Sesiones registradas en {periodo} días", str(stats["total"]) if stats["total"] is not None else "N/D")
    c.metric(f"Días con registro en {periodo} días", str(stats["registrados"]))
    d.metric(f"Días sin registro en {periodo} días", str(stats["sin_registro"]))
    izquierda, derecha = st.columns([1.35, 1.0], gap="medium")
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
                r = resumen(otra, objetivo, periodo)
                if r["media"] is not None:
                    filas.append({"Estación": estacion.replace("BOULDER / ", ""),
                                  "Media": r["media"],
                                  "Cobertura": f'{r["registrados"]}/{r["dias"]}'})
            except requests.RequestException:
                continue
        if filas:
            comparacion = pd.DataFrame(filas)
            barras = alt.Chart(comparacion).mark_bar(
                color=TURQUESA, size=25, cornerRadiusEnd=3).encode(
                y=alt.Y("Estación:N", sort="-x", title=None,
                        axis=alt.Axis(labelLimit=180, labelFontSize=11)),
                x=alt.X("Media:Q", title="Sesiones por día con registro", scale=alt.Scale(zero=True)),
                tooltip=["Estación:N", alt.Tooltip("Media:Q", format=".2f"), "Cobertura:N"]).properties(height=228)
            st.altair_chart(barras, use_container_width=True)
        else:
            st.info("No hay comparación disponible para este periodo.")
    franja(
        '<b>Calidad de datos:</b> los promedios excluyen días sin registro; '
        'la ausencia de una sesión registrada no demuestra inactividad de una estación. '
        'Comparación descriptiva, no ranking de capacidad disponible.')

    st.markdown('<div class="ev-title">Patrón de sesiones por día de la semana</div>', unsafe_allow_html=True)

    grafica_dia_semana(datos, objetivo, periodo)

else:  # Simulación por fecha
    a, b, c, d = st.columns(4)
    a.metric("Sesiones estimadas en fecha objetivo", numero(pred, 2))
    b.metric("Sesiones observadas en ese día", numero(observado, 0))
    c.metric("Referencia hace 7 días", numero(
        float(resultado["referencia_7_dias"]) if resultado else None, 0))
    d.metric("Diferencia estimación - observado", numero(
        pred - observado if pred is not None and observado is not None else None, 2))
    st.markdown(
        f'<div class="ev-title">Estimación para el {fecha:%d/%m/%Y} y comportamiento evolutivo en los 60 días anteriores</div>',
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

