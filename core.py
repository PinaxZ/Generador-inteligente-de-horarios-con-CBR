import pandas as pd, numpy as np, re, os
from scipy.spatial.distance import cdist


START_HOUR = 7
END_HOUR   = 22
SLOT_MIN   = 30

DAY_MAP = {
    'LU':0,'LUNES':0,'L':0,
    'MA':1,'MARTES':1,'MAR':1,
    'MI':2,'MIÉRCOLES':2,'MIERCOLES':2,'MIÉ':2,
    'JU':3,'JUEVES':3,'J':3,
    'VI':4,'VIERNES':4,'V':4,
    'SA':5,'SABADO':5,'SÁBADO':5,'S':5
}

SLOTS_PER_DAY = int((END_HOUR - START_HOUR) * 60 / SLOT_MIN)
TOTAL_SLOTS   = SLOTS_PER_DAY * 6


def filtrar_materias_disponibles(
        ruta_horarios_UACJ,
        ruta_plan_sistemas,
        ruta_perfil_estudiante,
        ruta_horarios_plan,
        ruta_salida,
        columnas_extra=None):
    #Carga archvios: (ruta_horarios_UACJ)Horario publicado UACJ, (ruta_plan_sistemas)plan academico de sistemas de alumno, (ruta_perfil_estudiante) Materias por cursar de estudiante
    #ruta_horarios_plan, ruta_salida seran salidas y corresponden a horario publicado UACJ solo con materias de plan academico de alumno y horario publicado UACJ solo con materias por cursar del estudiantes
    df_horarios=pd.read_csv(ruta_horarios_UACJ, dtype=str)
    df_plan =pd.read_csv(ruta_plan_sistemas, dtype=str)

    df_match=df_horarios[df_horarios['ClaveMateria'].isin(df_plan['Clave'])].copy()
    df_salida= (
        df_match[['ClaveMateria', 'Materia', 'Docente', 'Horario']]
        .rename(columns={'ClaveMateria': 'Clave'})
        .reset_index(drop=True)
        )
    df_salida.to_csv(ruta_horarios_plan, index=False, encoding='utf-8-sig')
    print(f'Se generó {ruta_horarios_plan} con {len(df_salida)} registros.')


    # Cargar archivos preprocesados
    df_hor = pd.read_csv(ruta_horarios_plan, dtype=str)
    df_per = pd.read_csv(ruta_perfil_estudiante, dtype=str)

    #filtro
    df_match = df_hor[df_hor['Clave'].isin(df_per['Clave'])].copy()

    #Seleccionar columnas
    mantener_cols = ['Clave','Materia', 'Docente', 'Horario']
    if columnas_extra:
        mantener_cols += columnas_extra
    df_out = df_match[mantener_cols].reset_index(drop=True)

    #Guardar y devolver
    df_out.to_csv(ruta_salida, index=False, encoding='utf-8-sig')
    return df_out
def hora_a_idx(time_str: str) -> int:
    h, m = map(int, time_str.split(':'))
    return ((h - START_HOUR) * 60 + m) // SLOT_MIN

def vector_horario(horario_str: str) -> np.ndarray:

    #Condicion IF corregida por Gemini IA. Da solucion a el error de recibir una variable distinta a un string
    #Error generado por materias que solo se ofertan en linea.
    if not isinstance(horario_str, str):
        return np.zeros(TOTAL_SLOTS, dtype=bool)
    vec = np.zeros(TOTAL_SLOTS, dtype=bool)

    # divide por coma si hay varios días
    segmentos = [seg.strip() for seg in horario_str.split(',')]

    for seg in segmentos:
        # por ejemplo, teniendo el formato: 'Lunes 11:00-13:00' pasria a: dia = 'Lunes', horas = '11:00-13:00'
        m = re.match(r'([A-Za-zÁÉÍÓÚÜáéíóúü]+)\s+(\d{1,2}:\d{2})-(\d{1,2}:\d{2})', seg)
        if not m:
            raise ValueError(f"mal formato de horario '{seg}'")
        dia_txt, ini, fin = m.groups()

        dia_key = re.sub(r'[^A-ZÁÉÍÓÚÜ]', '', dia_txt.upper())[:2]
        idx_dia = DAY_MAP.get(dia_key)
        if idx_dia is None:
            raise KeyError(f"dia '{dia_txt}' no reconocid0")

        i0 = hora_a_idx(ini)
        i1 = hora_a_idx(fin)
        offset = idx_dia * SLOTS_PER_DAY
        vec[offset + i0 : offset + i1] = True

    return vec

def vector_disponibilidad(ventana_dict):
    vec = np.zeros(TOTAL_SLOTS, dtype=bool)
    for dia_txt, rango in ventana_dict.items():
        dia_key = re.sub(r'[^A-ZÁÉÍÓÚÜ]', '', dia_txt.upper())[:2]
        idx_dia = DAY_MAP[dia_key]
        ini, fin = rango.split('-')
        i0 = hora_a_idx(ini)
        i1 = hora_a_idx(fin)
        offset = idx_dia * SLOTS_PER_DAY
        vec[offset+i0 : offset+i1] = True
    return vec

def cabe_en_disponibilidad(vec):
    return not np.any(vec & ~disponibilidad_vec)


def retroceso(idx, elegido, ocupado, cuenta_objetivo):
    global mejor_horario, mejor_puntaje
    # Condiciin de exito si, alcanzamos la meta de materias o no quedan mas
    if len(elegido) == cuenta_objetivo or idx == len(materias):
        if len(elegido) > 0:
            score = sum(r['score'] for r in elegido)
            if score > mejor_puntaje:
                mejor_horario, mejor_puntaje = elegido.copy(), score
        return

    materia = materias[idx]
    for _, row in candidatos[candidatos['Clave'] == materia].iterrows():
        if np.any(row['vec'] & ocupado):
            continue                      # choca con otro grupo
        retroceso(idx+1, elegido+[row],
                  ocupado | row['vec'],
                  cuenta_objetivo)

    # Opcion de saltar esta materia, para que el algoritmo encuentre haga eleccion de 4, 3, ... si 5 no caben
    retroceso(idx+1, elegido, ocupado, cuenta_objetivo)


# ────────────────────────────────────────────────────────────────────
#  Función orquestadora lista para usar en core.py
# ────────────────────────────────────────────────────────────────────
def generar_horario(ruta_horarios: str,
                    ruta_plan: str,
                    ruta_perfil: str,
                    ventana: dict,
                    ruta_encuestas: str = "inputs/encuestas_simuladas_100.csv",
                    n_max_materias: int = 5):
    """
    Devuelve (horario_df, puntaje_total).  Si no hay solución, horario_df
    estará vacío y puntaje_total será 0.

    Parámetros
    ----------
    ruta_plan     : CSV con el plan académico de la carrera
    ruta_perfil   : CSV con las materias pendientes del alumno
    ventana       : dict {'Lunes':'07:00-13:00', ...}
    ruta_encuestas: CSV con las encuestas históricas (default = 100 simuladas)
    n_max_materias: cuántas materias intentar (máximo 6 por defecto)
    """
    # 1️⃣  Filtrado inicial de grupos ──────────────────────────────────
    global mejor_horario, mejor_puntaje, materias, candidatos  # usa retroceso() existente
    base_dir      = os.path.dirname(ruta_horarios)
    tmp_plan_path = os.path.join(base_dir, "horarios_plan_tmp.csv")
    tmp_disp_path = os.path.join(base_dir, "materias_disponibles_tmp.csv")

    df_disp = filtrar_materias_disponibles(
        ruta_horarios, ruta_plan, ruta_perfil,
        tmp_plan_path, tmp_disp_path)

    # 2️⃣  Cargar biblioteca de casos y construir matrices one-hot ─────
    encuestas  = pd.read_csv(ruta_encuestas, dtype=str)
    biblioteca = encuestas[['Clave','Profesor',
                            'tiempoOffClass','materiaDificil',
                            'profesorDificil','acreditada']]

    base_dummy = pd.get_dummies(biblioteca.drop(columns='acreditada'))
    prob_dummy = (pd.get_dummies(df_disp.drop(columns='Horario'))
                  .reindex(columns=base_dummy.columns, fill_value=0))

    matriz_base = base_dummy.to_numpy(dtype=int)
    matriz_prob = prob_dummy.to_numpy(dtype=int)

    # 3️⃣  CBR: distancia de Hamming + prob_acreditar ──────────────────
    dist = cdist(matriz_prob, matriz_base, metric='hamming')
    k = 5
    idx_vecinos = dist.argsort(axis=1)[:, :k]

    prob_acred  = (biblioteca.iloc[idx_vecinos.ravel()]['acreditada']
                             .astype(int)
                             .to_numpy()
                             .reshape(len(df_disp), k)
                             .mean(axis=1))

    problema = df_disp[['Clave','Docente']].copy()
    problema['probabilidad_acreditar'] = prob_acred
    problema['decision'] = problema['probabilidad_acreditar'] \
        .apply(lambda p: 'Alta' if p >= 0.8 else 'Baja')

    # 4️⃣  Elegir el mejor profesor por materia (top_por_materia) ──────
    prob_unico = (problema.sort_values('probabilidad_acreditar', ascending=False)
                           .drop_duplicates(subset=['Clave','Docente'])
                            .reset_index(drop=True))

    top_por_materia = (prob_unico
                       .sort_values('probabilidad_acreditar', ascending=False)
                       .drop_duplicates(subset=['Clave']))

    # 5️⃣  Ligar con los horarios reales y calcular score ──────────────
    candidatos = (df_disp.merge(
                    top_por_materia[['Clave','Docente','probabilidad_acreditar']],
                    on=['Clave','Docente'], how='inner'))
    candidatos['score'] = candidatos['probabilidad_acreditar']
    candidatos['vec']   = candidatos['Horario'].apply(vector_horario)

    materias = candidatos['Clave'].unique()  # variable que retroceso lee

    # 6️⃣  Filtrar por disponibilidad declarada ────────────────────────
    disp_vec = vector_disponibilidad(ventana)
    candidatos = candidatos[candidatos['vec']
                            .apply(lambda v: not np.any(v & ~disp_vec))]\
                 .reset_index(drop=True)

    if candidatos.empty:
        return pd.DataFrame(), 0.0

    # 7️⃣  Backtracking: sin choques, max score, ≤ n_max_materias ──────

    mejor_horario, mejor_puntaje = None, -1

    for objetivo in range(min(n_max_materias, len(materias)), 0, -1):
        mejor_horario, mejor_puntaje = None, -1
        retroceso(0, [], np.zeros_like(disp_vec), objetivo)
        if mejor_horario:
            break

    # 8️⃣  Resultado final ─────────────────────────────────────────────
    if mejor_horario:
        horario_df = (pd.DataFrame(mejor_horario)
                      [['Clave','Materia','Docente','Horario','probabilidad_acreditar']]
                      .reset_index(drop=True))
        return horario_df, mejor_puntaje
    else:
        return pd.DataFrame(), 0.0
