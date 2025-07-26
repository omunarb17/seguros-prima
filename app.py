# Autor: Orlando Munar Benitez
# Calculadora de Prima de Seguro de Vida
#
# Desarrollado con Streamlit

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="Calculadora de Prima de Seguro de Vida",
    layout="wide",
    initial_sidebar_state="expanded"
)

def calcular_prima(
    edad, sexo, valor_asegurado, inflacion, interes_tecnico,
    gastos_iniciales, gastos_administrativos, comision_anio_1, comision_anio_n,
    forma_pago, cnt_plazo_pago, testadistica_vida, plazo
):
    # Validación de plazo
    if plazo <= 0:
        return {
            'error': 'La edad ingresada no permite calcular un plazo válido para el seguro (plazo <= 0).',
            'proyeccion': None
        }
    # Filtrar la tabla para cod_tasa = 20
    tabla = testadistica_vida[testadistica_vida['cod_tasa'] == 20].copy()
    edad_base = edad
    rentabilidad = (1 + interes_tecnico / 100) * (1 + inflacion / 100) - 1
    
    # Seleccionar los registros necesarios
    registros = tabla[tabla['nro_edad'] >= edad_base].head(plazo).copy()
    registros['contador'] = np.arange(len(registros))
    registros['exp_1'] = (1 + inflacion / 100) ** registros['contador']
    registros['exp_2'] = (1 + rentabilidad) ** (registros['contador'] + 1)
    # Desplazamientos tipo c(0, x[-1])
    registros['exp_lx_1'] = np.concatenate(([0], registros['exp_1'].values[1:]))
    registros['exp_lx_2'] = np.concatenate(([0], (1 + rentabilidad) ** registros['contador'].values[1:]))

    # Numerador unitario y acumulado (siempre presente)
    if sexo == "Masculino":
        registros['numerador_unitario'] = registros['dx'] * (registros['exp_1'] / registros['exp_2'])
        lx_usado = registros['lx'].values[0]
    else:
        registros['numerador_unitario'] = registros['dx_mujer'] * (registros['exp_1'] / registros['exp_2'])
        lx_usado = registros['lx_mujer'].values[0]
    registros['numerador_acum'] = np.round(np.cumsum(registros['numerador_unitario']), 20)

    # Denominador unitario y acumulado: lógica idéntica a R usando arrays
    if sexo == "Masculino":
        lx = registros['lx'].values
    else:
        lx = registros['lx_mujer'].values
    exp_lx_1 = registros['exp_lx_1'].values
    exp_lx_2 = registros['exp_lx_2'].values
    denominador_unitario = np.zeros(len(registros))
    if len(registros) > 1:
        denominador_unitario[1:] = lx[1:] * (exp_lx_1[1:] / exp_lx_2[1:])
    registros['denominador_unitario'] = denominador_unitario
    registros['denominador_acum'] = np.round(np.cumsum(denominador_unitario), 20)

    numerador_final = np.round(registros['numerador_acum'].iloc[-1], 20)
    if cnt_plazo_pago == 0:
        denominador_final = np.round(registros['denominador_acum'].iloc[-1], 20)
    else:
        fila_limite = registros[registros['contador'] == (cnt_plazo_pago - 1)]
        if not fila_limite.empty:
            denominador_final = np.round(fila_limite['denominador_acum'].values[0], 20)
        else:
            denominador_final = np.round(registros['denominador_acum'].iloc[-1], 20)

    tasa_pura_basica = numerador_final / denominador_final if denominador_final != 0 else 0
    gi = gastos_iniciales / 100
    ga = gastos_administrativos / 100
    c1 = comision_anio_1 / 100
    cn = comision_anio_n / 100
    f_1 = np.round((1 - c1 - gi - ga) * lx_usado, 20)
    f_n = np.round((1 - cn - gi - ga) * denominador_final, 20)
    denominador_comercial = np.round(f_1 + f_n, 20)
    tasa_comercial = np.round(numerador_final / denominador_comercial, 5) if denominador_comercial != 0 else 0

    # Lógica de fraccionamiento
    cod_forma_pago = next(x['cod'] for x in tipos_pago if x['desc'] == forma_pago)
    divisor = {1: 1, 2: 2, 4: 4, 6: 12}[cod_forma_pago]
    factor = {1: 0, 2: 0.06, 4: 0.08, 6: 0.12}[cod_forma_pago]
    tasa_comercial_fracc = np.round((tasa_comercial / divisor) * (1 + factor) * divisor, 8)

    # Prima anual y fraccionada
    prima_comercial_anual = np.round(valor_asegurado * tasa_comercial, 2)
    prima_comercial_fracc = np.round((prima_comercial_anual / divisor) * (1 + factor) * divisor, 2)

    # Proyección de primas por periodo de pago
    n_periodos = plazo * divisor if cnt_plazo_pago == 0 else cnt_plazo_pago * divisor
    proyeccion = []
    for i in range(n_periodos):
        inflacion_acum = (1 + inflacion / 100) ** (i / divisor)
        prima_periodo = (prima_comercial_fracc / divisor) * inflacion_acum
        proyeccion.append({
            'Periodo': i + 1,
            'Prima ajustada': round(prima_periodo, 2)
        })
    df_proyeccion = pd.DataFrame(proyeccion)

    # Valores intermedios para depuración
    debug_vals = {
        'lx_usado': lx_usado,
        'numerador_final': numerador_final,
        'denominador_final': denominador_final,
        'f_1': f_1,
        'f_n': f_n,
        'denominador_comercial': denominador_comercial,
        'tasa_comercial': tasa_comercial
    }

    # Guardar registros para depuración (agregar lx, exp_lx_1, exp_lx_2, denominador_unitario)
    if sexo == "Masculino":
        debug_registros = registros[['contador', 'lx', 'exp_lx_1', 'exp_lx_2', 'denominador_unitario', 'denominador_acum']].copy()
    else:
        debug_registros = registros[['contador', 'lx_mujer', 'exp_lx_1', 'exp_lx_2', 'denominador_unitario', 'denominador_acum']].copy()
        debug_registros = debug_registros.rename(columns={'lx_mujer': 'lx'})

    return {
        'tasa_pura_basica': tasa_pura_basica,
        'tasa_comercial': tasa_comercial,
        'tasa_comercial_fracc': tasa_comercial_fracc,
        'prima_comercial_anual': prima_comercial_anual,
        'prima_comercial_fracc': prima_comercial_fracc,
        'proyeccion': df_proyeccion,
        'debug': debug_vals,
        'debug_registros': debug_registros
    }

def calcular_prima_multi(
    edad, sexo, valor_asegurado, inflacion, interes_tecnico,
    gastos_iniciales, gastos_administrativos, comision_anio_1, comision_anio_n,
    forma_pago, cnt_plazo_pago, testadistica_vida, plazo, cod_tasas
):
    resultados = []
    total_prima_emitida = 0
    for cod_tasa in cod_tasas:
        # Filtrar la tabla para el cod_tasa correspondiente
        tabla = testadistica_vida[testadistica_vida['cod_tasa'] == cod_tasa].copy()
        if tabla.empty:
            continue
        # --- Lógica igual a calcular_prima ---
        registros = tabla[tabla['nro_edad'] >= edad].head(plazo).copy()
        registros['contador'] = np.arange(len(registros))
        registros['exp_1'] = (1 + inflacion / 100) ** registros['contador']
        rentabilidad = (1 + interes_tecnico / 100) * (1 + inflacion / 100) - 1
        registros['exp_2'] = (1 + rentabilidad) ** (registros['contador'] + 1)
        registros['exp_lx_1'] = np.concatenate(([0], registros['exp_1'].values[1:]))
        registros['exp_lx_2'] = np.concatenate(([0], (1 + rentabilidad) ** registros['contador'].values[1:]))
        # Ajuste: para cod_tasa=14 o 18, usar siempre lx y dx
        if cod_tasa in [14, 18]:
            registros['numerador_unitario'] = registros['dx'] * (registros['exp_1'] / registros['exp_2'])
            lx_usado = registros['lx'].values[0]
            lx = registros['lx'].values
        else:
            if sexo == "Masculino":
                registros['numerador_unitario'] = registros['dx'] * (registros['exp_1'] / registros['exp_2'])
                lx_usado = registros['lx'].values[0]
                lx = registros['lx'].values
            else:
                registros['numerador_unitario'] = registros['dx_mujer'] * (registros['exp_1'] / registros['exp_2'])
                lx_usado = registros['lx_mujer'].values[0]
                lx = registros['lx_mujer'].values
        registros['numerador_acum'] = np.round(np.cumsum(registros['numerador_unitario']), 20)
        exp_lx_1 = registros['exp_lx_1'].values
        exp_lx_2 = registros['exp_lx_2'].values
        denominador_unitario = np.zeros(len(registros))
        if len(registros) > 1:
            denominador_unitario[1:] = lx[1:] * (exp_lx_1[1:] / exp_lx_2[1:])
        registros['denominador_unitario'] = denominador_unitario
        registros['denominador_acum'] = np.round(np.cumsum(denominador_unitario), 20)
        numerador_final = np.round(registros['numerador_acum'].iloc[-1], 20)
        if cnt_plazo_pago == 0:
            denominador_final = np.round(registros['denominador_acum'].iloc[-1], 20)
        else:
            fila_limite = registros[registros['contador'] == (cnt_plazo_pago - 1)]
            if not fila_limite.empty:
                denominador_final = np.round(fila_limite['denominador_acum'].values[0], 20)
            else:
                denominador_final = np.round(registros['denominador_acum'].iloc[-1], 20)
        tasa_pura_basica = numerador_final / denominador_final if denominador_final != 0 else 0
        gi = gastos_iniciales / 100
        ga = gastos_administrativos / 100
        c1 = comision_anio_1 / 100
        cn = comision_anio_n / 100
        f_1 = np.round((1 - c1 - gi - ga) * lx_usado, 20)
        f_n = np.round((1 - cn - gi - ga) * denominador_final, 20)
        denominador_comercial = np.round(f_1 + f_n, 20)
        tasa_comercial = np.round(numerador_final / denominador_comercial, 5) if denominador_comercial != 0 else 0
        cod_forma_pago = next(x['cod'] for x in tipos_pago if x['desc'] == forma_pago)
        divisor = {1: 1, 2: 2, 4: 4, 6: 12}[cod_forma_pago]
        factor = {1: 0, 2: 0.06, 4: 0.08, 6: 0.12}[cod_forma_pago]
        tasa_comercial_fracc = np.round((tasa_comercial / divisor) * (1 + factor) * divisor, 8)
        prima_comercial_anual = np.round(valor_asegurado * tasa_comercial, 2)
        prima_comercial_fracc = np.round((prima_comercial_anual / divisor) * (1 + factor) * divisor, 2)
        total_prima_emitida += prima_comercial_fracc
        # Nombre de cobertura
        if cod_tasa == 20:
            cobertura = "MUERTE"
            tipo = "BÁSICO"
        elif cod_tasa == 14:
            cobertura = "MUERTE ACCID. Y DESMEMBRAMIENTO"
            tipo = "MAD"
        elif cod_tasa == 18:
            cobertura = "INVALIDEZ TOTAL Y PERMANENTE"
            tipo = "ITP"
        else:
            cobertura = f"CÓD. {cod_tasa}"
            tipo = "-"
        resultados.append({
            'Cobertura': cobertura,
            'Tipo': tipo,
            'Valor Asegurado': f"$ {valor_asegurado:,.0f}".replace(",", "."),
            'Tasa Comercial': f"{tasa_comercial:.5f}",
            'Prima Anual': f"$ {prima_comercial_anual:,.0f}".replace(",", "."),
            'Prima Fraccionada': f"$ {prima_comercial_fracc:,.0f}".replace(",", ".")
        })
    # Agregar fila de total
    if resultados:
        resultados.append({
            'Cobertura': 'TOTAL PRIMA EMITIDA',
            'Tipo': '',
            'Valor Asegurado': '',
            'Tasa Comercial': '',
            'Prima Anual': '',
            'Prima Fraccionada': f"$ {total_prima_emitida:,.0f}".replace(",", ".")
        })
    return resultados

# --- Cargar datos de Excel ---
@st.cache_data
def cargar_tabla():
    return pd.read_excel('testadistica_vida.xlsx')

testadistica_vida = cargar_tabla()

# --- Sidebar: Parámetros de entrada ---
st.sidebar.title("Parámetros de Cálculo")

# Espacio para el logo
t_logo = st.sidebar.empty()
# t_logo.image("logo.png", width=150)  # Descomentar cuando tengas el logo

edad = st.sidebar.number_input("Edad actual", min_value=18, max_value=65, value=35)
sexo = st.sidebar.radio("Sexo", ["Masculino", "Femenino"])
valor_asegurado = st.sidebar.number_input("Valor asegurado", min_value=1000000, step=1000000, value=10000000)

# Mostrar valor asegurado con formato bonito
valor_asegurado_str = f"{valor_asegurado:,.0f}".replace(",", ".")
st.sidebar.markdown(f"<div style='font-size:1.5em; color:#1e90ff; font-weight:bold;'>$ {valor_asegurado_str}</div>", unsafe_allow_html=True)

# Inflación supuesta
inflacion = st.sidebar.selectbox("Inflación supuesta (%)", [4.5, 5.0, 5.5], index=1)
# Interés técnico
interes_tecnico = st.sidebar.selectbox("Interés técnico (%)", [4.0, 4.2, 4.5, 4.8, 5.0], index=0)

gastos_iniciales = st.sidebar.number_input("Gastos iniciales (%)", min_value=0.0, max_value=10.0, value=0.0)
gastos_administrativos = st.sidebar.number_input("Gastos administrativos (%)", min_value=0.0, max_value=10.0, value=0.0)
comision_anio_1 = st.sidebar.number_input("Comisión año 1 (%)", min_value=0.0, max_value=50.0, value=0.0)
comision_anio_n = st.sidebar.number_input("Comisión a partir año 2 (%)", min_value=0.0, max_value=50.0, value=0.0)

# Formas de pago
tipos_pago = [
    {"cod": 1, "desc": "ANUAL", "nro_divisor": 1},
    {"cod": 2, "desc": "SEMESTRAL", "nro_divisor": 2},
    {"cod": 4, "desc": "TRIMESTRAL", "nro_divisor": 4},
    {"cod": 6, "desc": "MENSUAL", "nro_divisor": 12},
]
forma_pago = st.sidebar.selectbox("Forma de pago", [x["desc"] for x in tipos_pago], index=0)

cnt_plazo_pago = st.sidebar.selectbox(
    "Cantidad de pagos",
    options=[0, 1, 4, 8],
    format_func=lambda x: {
        0: "Permanente (durante todo el plazo)",
        1: "Pago único",
        4: "4 pagos",
        8: "8 pagos"
    }[x]
)

# Plazo tope del producto (usuario escoge entre 70 y 80)
plazo_producto = st.sidebar.selectbox("Plazo tope del producto (edad máxima)", options=[70, 80], index=0)

if edad >= plazo_producto:
    total_plazo = 0
else:
    total_plazo = plazo_producto - edad

# Validación de edad máxima
edad_valida = edad <= 65

if not edad_valida:
    st.warning('La edad actual no puede ser mayor a 65 años. Por favor, ingresa una edad válida.')

# --- Panel principal ---
st.title("Calculadora de Prima de Seguro de Vida")
st.markdown("""
<p style='font-size:16px; color:#888; margin-bottom:1em;'>Autor: <b>Orlando Munar Benitez</b></p>
""", unsafe_allow_html=True)
st.markdown("""
""")

if st.button('Calcular Prima', disabled=not edad_valida):
    resultados = calcular_prima_multi(
        edad, sexo, valor_asegurado, inflacion, interes_tecnico,
        gastos_iniciales, gastos_administrativos, comision_anio_1, comision_anio_n,
        forma_pago, cnt_plazo_pago, testadistica_vida, total_plazo, [20, 14, 18]
    )
    if not resultados:
        st.error('No se pudo calcular la prima para las coberturas seleccionadas.')
    else:
        st.success('¡Cálculo realizado!')
        st.metric('Plazo del seguro (años)', total_plazo)
        st.dataframe(pd.DataFrame(resultados), use_container_width=True)

# --- CSS personalizado ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #f7fafd;
    }
    .stButton>button {
        color: #fff !important;
        background: linear-gradient(90deg, #1e90ff 0%, #00b894 100%) !important;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        transition: background 0.3s;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #1565c0 0%, #00916e 100%) !important;
        color: #fff !important;
        border: none;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 18px;
        font-weight: 600;
        color: #1e90ff;
    }
    .stExpanderHeader {
        font-size: 16px;
        color: #00b894;
    }
    </style>
    """,
    unsafe_allow_html=True
) 