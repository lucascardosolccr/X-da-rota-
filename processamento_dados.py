import os
import time
import pickle
import pandas as pd
import streamlit as st
from unidecode import unidecode
from config import session, CACHE_IBGE_PATH

@st.cache_data
def carregar_dados_ibge():
    if os.path.exists(CACHE_IBGE_PATH):
        if time.time() - os.path.getmtime(CACHE_IBGE_PATH) > (30 * 86400):
            os.remove(CACHE_IBGE_PATH)
        else:
            try:
                with open(CACHE_IBGE_PATH, "rb") as f:
                    d = pickle.load(f)
                    if len(d.get("municipios", {})) > 1000:
                        return d.get("municipios", {}), d.get("estados", {}), d.get("distritos", {}), list(d.get("municipios", {}).keys()) + list(d.get("distritos", {}).keys())
            except Exception: pass

    base_mun, base_est, base_dist = {}, {}, {}
    try:
        r_est = session.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados", timeout=8)
        if r_est.status_code == 200:
            for est in r_est.json():
                base_est[est["sigla"]] = unidecode(est["nome"]).upper()
                
        r_mun = session.get("https://servicodados.ibge.gov.br/api/v1/localidades/municipios", timeout=12)
        if r_mun.status_code == 200:
            for mun in r_mun.json():
                nome_norm = unidecode(mun["nome"]).upper().strip()
                uf_sigla = mun["microrregiao"]["mesorregiao"]["UF"]["sigla"].upper()
                if nome_norm not in base_mun: base_mun[nome_norm] = []
                base_mun[nome_norm].append({"uf": uf_sigla, "municipio": nome_norm, "lat": mun.get("lat", 0.0), "lon": mun.get("lon", 0.0)})
                
        r_dist = session.get("https://servicodados.ibge.gov.br/api/v1/localidades/distritos", timeout=12)
        if r_dist.status_code == 200:
            for dist in r_dist.json():
                nome_dist = unidecode(dist["nome"]).upper().strip()
                nome_muni = unidecode(dist["municipio"]["nome"]).upper().strip()
                uf_dist = dist["municipio"]["microrregiao"]["mesorregiao"]["UF"]["sigla"].upper()
                if nome_dist not in base_dist: base_dist[nome_dist] = []
                base_dist[nome_dist].append({"uf": uf_dist, "municipio": nome_muni, "lat": dist.get("lat", 0.0), "lon": dist.get("lon", 0.0)})

                if len(base_mun) > 1000:
                    with open(CACHE_IBGE_PATH, "wb") as f:
                        pickle.dump({"municipios": base_mun, "estados": base_est, "distritos": base_dist}, f)
    except Exception: pass
    
    lista_completa = list(base_mun.keys()) + list(base_dist.keys())
    return base_mun, base_est, base_dist, lista_completa

IBGE_MUNICIPIOS, IBGE_ESTADOS, IBGE_DISTRITOS, LISTA_TOPONIMOS = carregar_dados_ibge()

LISTA_CONTEXTO_FUZZY = []
for k, v_list in IBGE_MUNICIPIOS.items(): 
    for v in v_list: LISTA_CONTEXTO_FUZZY.append(f"{k} {v['uf']}")
for k, v_list in IBGE_DISTRITOS.items(): 
    for v in v_list: LISTA_CONTEXTO_FUZZY.append(f"{k} {v['uf']}")
LISTA_CONTEXTO_FUZZY = list(set(LISTA_CONTEXTO_FUZZY))

# ==============================================================================
# ENGINE DE CROSS-FILTERING GLOBAL (ALTAIR -> PYTHON STATE)
# ==============================================================================
def extrair_selecoes_altair():
    sel = {'regiao': [], 'uf': [], 'mun': [], 'status': [], 'linha_mun': [], 'scatter_mun': [], 'brush': {}}
    def _get_sel(key, field, sel_key):
        if key in st.session_state and 'selection' in st.session_state[key]:
            items = st.session_state[key]['selection'].get(sel_key, [])
            return [i[field] for i in items if isinstance(i, dict) and field in i]
        return []
        
    sel['regiao'] = _get_sel("dash_reg", 'Regiao_Sintetica_Origem', 'Reg')
    sel['uf'] = _get_sel("dash_uf", 'UF_Sintetica_Origem', 'UF')
    sel['status'] = _get_sel("dash_status", 'Status da Rota', 'Status')
    sel['mun'] = _get_sel("dash_mun", 'Municipio Origem', 'Mun')
    sel['linha_mun'] = _get_sel("dash_lr", 'Municipio Origem', 'LinhaMun')
    sel['scatter_mun'] = _get_sel("dash_scatter", 'Municipio Origem', 'ScatterMun')
    
    if "dash_scatter" in st.session_state and 'selection' in st.session_state["dash_scatter"]:
        sel['brush'] = st.session_state["dash_scatter"]['selection'].get('Brush', {})
    return sel

def sync_altair_to_widgets():
    sel = extrair_selecoes_altair()
    prev_sel_key = "prev_altair_sel"
    prev_sel = st.session_state.get(prev_sel_key, {'regiao':[], 'uf':[], 'mun':[], 'status':[], 'linha_mun':[], 'scatter_mun':[], 'brush':{}})
    
    def check_update(field, widget_key, default_val):
        if sel[field] != prev_sel[field]:
            st.session_state[widget_key] = sel[field][0] if sel[field] else default_val

    check_update('regiao', 'widget_regiao', 'Todas')
    check_update('uf', 'widget_uf', 'Todas')
    check_update('status', 'widget_status', 'Todos')
    
    if sel['mun'] != prev_sel['mun']:
        st.session_state['widget_mun'] = sel['mun'][0] if sel['mun'] else 'Todos'
    elif sel['linha_mun'] != prev_sel['linha_mun']:
        st.session_state['widget_mun'] = sel['linha_mun'][0] if sel['linha_mun'] else 'Todos'
    elif sel['scatter_mun'] != prev_sel['scatter_mun']:
        st.session_state['widget_mun'] = sel['scatter_mun'][0] if sel['scatter_mun'] else 'Todos'

    st.session_state[prev_sel_key] = sel

def aplicar_filtro_global(df_base, sel):
    df_cf = df_base.copy()
    if st.session_state.widget_regiao != "Todas": df_cf = df_cf[df_cf['Regiao_Sintetica_Origem'] == st.session_state.widget_regiao]
    if st.session_state.widget_uf != "Todas": df_cf = df_cf[df_cf['UF_Sintetica_Origem'] == st.session_state.widget_uf]
    if st.session_state.widget_mun != "Todos": df_cf = df_cf[df_cf['Municipio Origem'] == st.session_state.widget_mun]
    if st.session_state.widget_status != "Todos": df_cf = df_cf[df_cf['Status da Rota'] == st.session_state.widget_status]
    if st.session_state.widget_fonte != "Todas": df_cf = df_cf[df_cf['Fonte Geocoding Origem'] == st.session_state.widget_fonte]
    
    if sel['brush']:
        b = sel['brush']
        if 'Distancia' in b:
            df_cf = df_cf[(df_cf['Distancia'] >= b['Distancia'][0]) & (df_cf['Distancia'] <= b['Distancia'][1])]
        if 'Tempo_Horas' in b:
            df_cf = df_cf[(df_cf['Tempo_Horas'] >= b['Tempo_Horas'][0]) & (df_cf['Tempo_Horas'] <= b['Tempo_Horas'][1])]
    return df_cf

def renderizar_indicador_filtros(brush_active):
    active_html = ""
    if st.session_state.get('widget_regiao', 'Todas') != 'Todas': active_html += f"<span class='filter-badge'>Região: {st.session_state.widget_regiao}</span>"
    if st.session_state.get('widget_uf', 'Todas') != 'Todas': active_html += f"<span class='filter-badge'>UF: {st.session_state.widget_uf}</span>"
    if st.session_state.get('widget_mun', 'Todos') != 'Todos': active_html += f"<span class='filter-badge'>Município: {st.session_state.widget_mun}</span>"
    if st.session_state.get('widget_status', 'Todos') != 'Todos': active_html += f"<span class='filter-badge'>Status: {st.session_state.widget_status}</span>"
    if st.session_state.get('widget_fonte', 'Todas') != 'Todas': active_html += f"<span class='filter-badge'>Fonte: {st.session_state.widget_fonte}</span>"
    if brush_active: active_html += f"<span class='filter-badge'>Filtro de Área (Scatter)</span>"
        
    if active_html:
        st.markdown(f"<div style='background:#1E232F; padding:15px; border-radius:8px; border: 1px solid #3B82F6; margin-bottom:15px'><b>🔍 Filtros Ativos no Dashboard:</b><br><br> {active_html}</div>", unsafe_allow_html=True)

def get_agg_func(op_name):
    if 'Contagem Distinta' in op_name: return 'nunique'
    if 'Contagem' in op_name: return 'count'
    if 'Soma' in op_name: return 'sum'
    if 'Média' in op_name: return 'mean'
    if 'Mínimo' in op_name: return 'min'
    if 'Máximo' in op_name: return 'max'
    if 'Mediana' in op_name: return 'median'
    if 'Desvio Padrão' in op_name: return 'std'
    if 'Variância' in op_name: return 'var'
    if 'Percentil 25' in op_name: return lambda x: x.quantile(0.25)
    if 'Percentil 50' in op_name: return lambda x: x.quantile(0.50)
    if 'Percentil 75' in op_name: return lambda x: x.quantile(0.75)
    return 'count'