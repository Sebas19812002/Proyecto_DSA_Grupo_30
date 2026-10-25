# %% Cargar los datos
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ruta_datos = Path(__file__).resolve().parent / "Electric_Vehicle_Charging_Station_Data.csv"
df = pd.read_csv(ruta_datos)

print("Filas y columnas:", df.shape)
print()
print(df.dtypes)
df.head()

# %% Calidad de los datos
print("Nulos por columna:")
print(df.isna().sum())
print()
print("Filas completamente idénticas (incluyendo identificadores): ", df.duplicated().sum())
print("Estaciones distintas:", df["Station_Name"].nunique())
print()
print("Ejemplos de fechas:")
print(df["Start_Date___Time"].head(3).tolist())
print()
print("Zonas horarias:", df["Start_Time_Zone"].unique())
print()
print("Tipos de puerto:")
print(df["Port_Type"].value_counts())
print()
df[["Energy__kWh_", "GHG_Savings__kg_", "Gasoline_Savings__gallons_"]].describe()

# %% Fechas, duraciones y valores raros
s = df["Start_Date___Time"]
fecha_vieja = pd.to_datetime(s, format="%m/%d/%Y %H:%M", errors="coerce")
fecha_nueva = pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S", errors="coerce")
df["inicio"] = fecha_vieja.fillna(fecha_nueva)
df["formato_fecha"] = fecha_vieja.notna().map({True: "m/d/Y", False: "ISO"})

print("Sesiones por formato de fecha:")
print(df["formato_fecha"].value_counts())
print("Fechas que no se pudieron convertir:", df["inicio"].isna().sum())
print()
print("Rango de fechas por formato:")
print(df.groupby("formato_fecha")["inicio"].agg(["min", "max"]))
print()
print("Zona horaria por formato:")
print(pd.crosstab(df["formato_fecha"], df["Start_Time_Zone"]))
print()

df["duracion_h"] = pd.to_timedelta(df["Total_Duration__hh_mm_ss_"]).dt.total_seconds() / 3600
df["carga_h"] = pd.to_timedelta(df["Charging_Time__hh_mm_ss_"]).dt.total_seconds() / 3600

print("Sesiones con 0 kWh:", (df["Energy__kWh_"] == 0).sum())
print("Sesiones con duración 0:", (df["duracion_h"] == 0).sum())
print("Sesiones de más de 24 h:", (df["duracion_h"] > 24).sum())
print("Tiempo de carga mayor que la duración:", (df["carga_h"] > df["duracion_h"]).sum())
print()
print("Correlación de la energía con las variables de ahorro:")
print(df[["Energy__kWh_", "GHG_Savings__kg_", "Gasoline_Savings__gallons_"]].corr().round(3))
print()
df[["duracion_h", "carga_h"]].describe()
# %% Revisar 2023 y sesiones con 0 kWh
df["mes"] = df["inicio"].dt.to_period("M")

print("Sesiones por mes y formato (2023):")
print(pd.crosstab(df.loc[df["inicio"].dt.year == 2023, "mes"],
                  df.loc[df["inicio"].dt.year == 2023, "formato_fecha"]))
print()

print("Hora de inicio por formato (% de sesiones):")
df["hora"] = df["inicio"].dt.hour
print((pd.crosstab(df["hora"], df["formato_fecha"], normalize="columns") * 100).round(1))
print()

cero = df["Energy__kWh_"] == 0
print("Duración de sesiones con 0 kWh vs con energía (horas):")
print(df.groupby(cero)["duracion_h"].describe().round(2))
print()
print("% de sesiones con 0 kWh por año:")
print((df.groupby(df["inicio"].dt.year)["Energy__kWh_"].apply(lambda x: (x == 0).mean()) * 100).round(1))

# %% Duplicados y limpiar
# Confirmar que cada sesión ISO tiene su gemela en el formato viejo
iso = df[df["formato_fecha"] == "ISO"]
vieja = df[(df["formato_fecha"] == "m/d/Y") & (df["inicio"] >= "2023-06-01") & (df["inicio"] < "2023-09-01")]
llave_iso = iso["Station_Name"] + "|" + iso["inicio"].dt.floor("min").astype(str)
llave_vieja = vieja["Station_Name"] + "|" + vieja["inicio"].astype(str)
print(f"Sesiones ISO con gemela en el formato viejo: {llave_iso.isin(llave_vieja).mean() * 100:.1f}%")
print()

# Limpieza
n0 = len(df)
limpio = df[df["formato_fecha"] == "m/d/Y"].copy()
print("Quitando duplicados ISO:       ", n0 - len(limpio))
n_antes = len(limpio)
columnas_comparacion = [
    c for c in limpio.columns
    if c not in ["ObjectID", "ObjectId2"]]

limpio = limpio.drop_duplicates(subset=columnas_comparacion).copy()

print("Quitando duplicados adicionales:", n_antes - len(limpio))
# Conservar los datos deduplicados antes de excluir sesiones con 0 kWh
sin_dup = limpio.copy()

n1 = len(limpio)
limpio = limpio[limpio["duracion_h"] > 0]
print("Quitando duración 0:           ", n1 - len(limpio))
n2 = len(limpio)
limpio = limpio[limpio["Energy__kWh_"] > 0]
print("Quitando sesiones con 0 kWh:   ", n2 - len(limpio))
limpio = limpio.drop(columns=["GHG_Savings__kg_", "Gasoline_Savings__gallons_", "Port_Type",
                              "ObjectID", "ObjectId2", "formato_fecha"])
print()
print(f"Sesiones finales: {len(limpio):,} de {n0:,} ({len(limpio) / n0 * 100:.1f}%)")
print()
print("% de sesiones con 0 kWh por año (sin duplicados):")
print((sin_dup.groupby(sin_dup["inicio"].dt.year)["Energy__kWh_"].apply(lambda x: (x == 0).mean()) * 100).round(1))

# %% Sesiones diarias por estación (variable objetivo)
import numpy as np

limpio["fecha"] = limpio["inicio"].dt.normalize()

# Contar sesiones por estación y día -> tabla con fechas en filas y estaciones en columnas
tabla = limpio.groupby(["fecha", "Station_Name"]).size().unstack()
todas_fechas = pd.date_range(tabla.index.min(), tabla.index.max(), freq="D")
tabla = tabla.reindex(todas_fechas).fillna(0)

# Cada estación cuenta solo entre su primer y su último día de actividad
primer = limpio.groupby("Station_Name")["fecha"].min()
ultimo = limpio.groupby("Station_Name")["fecha"].max()
for est in tabla.columns:
    fuera = (tabla.index < primer[est]) | (tabla.index > ultimo[est])
    tabla.loc[fuera, est] = np.nan

# Pasar a formato largo: una fila por estación-día
panel = tabla.stack().dropna().reset_index()
panel.columns = ["fecha", "estacion", "sesiones"]

s = panel["sesiones"]
print(f"Observaciones estación-día: {len(panel):,}")
print(f"Media: {s.mean():.2f} | Mediana: {s.median():.0f} | Desv. estándar: {s.std():.2f} | Máximo: {s.max():.0f}")
print(f"Días con 0 sesiones: {(s == 0).mean() * 100:.1f}%")
print(f"Varianza / media: {s.var() / s.mean():.2f}")
print()

# Gráfico: total diario y estaciones activas
total = panel.groupby("fecha")["sesiones"].sum()
activas = panel.groupby("fecha")["estacion"].count()
fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
ax[0].plot(total, color="#93C5FD", linewidth=0.6, label="Diario")
ax[0].plot(total.rolling(30, center=True).mean(), color="#1E3A8A", linewidth=2, label="Media móvil 30 días")
ax[0].set_title("Sesiones diarias totales (todas las estaciones)")
ax[0].set_ylabel("Sesiones")
ax[0].legend(frameon=False)
ax[1].plot(activas, color="gray")
ax[1].set_title("Estaciones activas")
ax[1].set_ylabel("Estaciones")
plt.tight_layout()
plt.show()

# %% Patrones temporales
dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

panel["dia_semana"] = panel["fecha"].dt.dayofweek
panel["mes"] = panel["fecha"].dt.month

por_dia = panel.groupby("dia_semana")["sesiones"].mean()
por_mes = panel.groupby("mes")["sesiones"].mean()

fig, ax = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
ax[0].bar(dias, por_dia.values, color="#2563EB")
ax[0].set_title("Sesiones promedio por estación según día de la semana")
ax[0].set_ylabel("Sesiones por estación-día")
ax[1].bar(meses, por_mes.values, color="#2563EB")
ax[1].set_title("Sesiones promedio por estación según mes")
plt.tight_layout()
plt.show()

# Mapa de calor: hora de inicio vs día de la semana
limpio["dia_semana"] = limpio["inicio"].dt.dayofweek
limpio["hora"] = limpio["inicio"].dt.hour
calor = pd.crosstab(limpio["dia_semana"], limpio["hora"])

fig, ax = plt.subplots(figsize=(12, 3.5))
im = ax.imshow(calor, aspect="auto", cmap="Blues")
ax.set_yticks(range(7), dias)
ax.set_xticks(range(24), range(24))
ax.set_xlabel("Hora de inicio")
ax.set_title("Cuándo empiezan las sesiones")
plt.colorbar(im, ax=ax, label="Sesiones")
plt.show()

print("Promedio por día de la semana:")
print(por_dia.round(2).set_axis(dias))
print(f"\nFin de semana vs entre semana: {(por_dia[5:].mean() / por_dia[:5].mean() - 1) * 100:+.1f}%")

# %% Comparación entre estaciones
por_estacion = panel.groupby("estacion").agg(
    media=("sesiones", "mean"),
    dias_activa=("sesiones", "size"),
    pct_dias_cero=("sesiones", lambda x: (x == 0).mean() * 100),
).sort_values("media", ascending=False)

print(por_estacion.round(2).head(10))
print("...")
print(por_estacion.round(2).tail(5))
print()
print(f"Estaciones con menos de 90 días de datos: {(por_estacion['dias_activa'] < 90).sum()}")
print(f"Media de la estación más usada: {por_estacion['media'].max():.2f} | menos usada: {por_estacion['media'].min():.2f}")

top15 = por_estacion.head(15).sort_values("media")
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh(top15.index.str[:40], top15["media"], color="#2563EB")
ax.set_title("Sesiones diarias promedio - 15 estaciones más usadas")
ax.set_xlabel("Sesiones por día")
plt.tight_layout()
plt.show()

top4 = por_estacion.head(4).index
fig, axes = plt.subplots(2, 2, figsize=(12, 6), sharex=True, sharey=True)
for ax, est in zip(axes.ravel(), top4):
    serie = panel[panel["estacion"] == est].set_index("fecha")["sesiones"]
    ax.plot(serie.rolling(30).mean(), color="#2563EB")
    ax.set_title(est[:40], fontsize=10)
fig.suptitle("Sesiones diarias (media móvil 30 días) - 4 estaciones más usadas")
plt.tight_layout()
plt.show()
# %% Revisar estaciones con la misma dirección
fechas_est = limpio.groupby("Station_Name").agg(
    primera=("fecha", "min"),
    ultima=("fecha", "max"),
    sesiones=("fecha", "size"),
    direccion=("Address", "first"),
)
# %% Unificar estaciones renombradas y excluir flota
limpio["estacion"] = limpio["Station_Name"].str.split(" / ").str[1].str.strip()

flota = limpio["estacion"].str.contains("FLT MNT|MSC E|OSMP FLEET")
print("Sesiones de flota excluidas:", flota.sum())
limpio = limpio[~flota]

print("Estaciones antes:", limpio["Station_Name"].nunique(), "| después de unificar:", limpio["estacion"].nunique())
print()

# Reconstruir el panel estación-día (igual que en el paso 6, con el nuevo identificador)
tabla = limpio.groupby(["fecha", "estacion"]).size().unstack()
tabla = tabla.reindex(pd.date_range(tabla.index.min(), tabla.index.max(), freq="D")).fillna(0)
primer = limpio.groupby("estacion")["fecha"].min()
ultimo = limpio.groupby("estacion")["fecha"].max()
for est in tabla.columns:
    tabla.loc[(tabla.index < primer[est]) | (tabla.index > ultimo[est]), est] = np.nan

panel = tabla.stack().dropna().reset_index()
panel.columns = ["fecha", "estacion", "sesiones"]

s = panel["sesiones"]
print(f"Observaciones estación-día: {len(panel):,}")
print(f"Estaciones: {panel['estacion'].nunique()}")
print(f"Media: {s.mean():.2f} | Mediana: {s.median():.0f} | Desv. estándar: {s.std():.2f} | Máximo: {s.max():.0f}")
print(f"Días con 0 sesiones: {(s == 0).mean() * 100:.1f}%")
print(f"Varianza / media: {s.var() / s.mean():.2f}")
print()
print(panel.groupby("estacion")["sesiones"].agg(["mean", "size"]).sort_values("mean", ascending=False).round(2))

# Direcciones que aparecen con más de un nombre de estación
repetidas = fechas_est.groupby("direccion").filter(lambda g: len(g) > 1)
print(repetidas.sort_values(["direccion", "primera"]).to_string())
print()

# Prefijos de los nombres y cuándo se usaron
fechas_est["prefijo"] = fechas_est.index.str.split(" / ").str[0]
print(fechas_est.groupby("prefijo").agg(estaciones=("sesiones", "size"),
                                         primera=("primera", "min"),
                                         ultima=("ultima", "max")))
# %% Correlación con días anteriores
panel = panel.sort_values(["estacion", "fecha"])
correlaciones = []
for k in range(1, 15):
    anterior = panel.groupby("estacion")["sesiones"].shift(k)
    correlaciones.append(panel["sesiones"].corr(anterior))

fig, ax = plt.subplots(figsize=(9, 3.5))
colores = ["#1E3A8A" if k % 7 == 0 else "#93C5FD" for k in range(1, 15)]
ax.bar(range(1, 15), correlaciones, color=colores)
ax.set_xticks(range(1, 15))
ax.set_xlabel("Días atrás")
ax.set_ylabel("Correlación")
ax.set_title("Correlación de las sesiones de hoy con las de días anteriores (misma estación)")
plt.show()

for k, c in enumerate(correlaciones, start=1):
    print(f"{k:2d} días atrás: {c:.2f}")

# %%
