import io
import time
import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px
import streamlit.components.v1 as components

# Imports da arquitetura modular
from config import CSS_STYLE, METRICAS_DISTANCIA, cache_api_health, cache_historico_lotes
from utils import enviar_ticket_suporte
from processamento_dados import IBGE_MUNICIPIOS, extrair_selecoes_altair, sync_altair_to_widgets, aplicar_filtro_global, renderizar_indicador_filtros, extrair_uf_precisa
from funcoes_core import executar_pipeline_unificado, rodar_pipeline_lote, obter_coordenadas_e_endereco_oficial, calcular_distancia_linha_reta

st.set_page_config(page_title="Gerenciador de Rotas Inteligentes", page_icon="🚗", layout="wide")
st.markdown(CSS_STYLE, unsafe_allow_html=True)

# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("📖 Documentação Corporativa")
    with st.expander("📊 Visão Geral e Filosofia"):
        st.markdown("O **Motor Nacional de Roteirização Inteligente** é o sistema core de inteligência logística B2B da operação, utilizando Pipeline Híbrido Multimotor.")
    st.markdown("---")
    st.subheader("💡 Suporte e Feedback")
    with st.form(key="form_sugestao"):
        sugestao_texto = st.text_area("Descreva a anomalia ou melhoria:", height=100)
        remetente_email = st.text_input("Seu e-mail corporativo (opcional):")
        if st.form_submit_button("🚀 Enviar Ticket"):
            if sugestao_texto.strip() == "": st.warning("O ticket não pode estar vazio.")
            else:
                sucesso, msg = enviar_ticket_suporte(sugestao_texto, remetente_email, "email@sistema.com", "senha")
                st.success(msg) if sucesso else st.error(msg)

# ==============================================================================
# HEADER
# ==============================================================================
st.markdown("""
<div class="corporate-header">
    <h1 class="corporate-title">🗺️ Motor Nacional de Roteirização Inteligente</h1>
    <p class="corporate-subtitle">Plataforma Corporativa B2B de Geocodificação, Inferência Bayesiana e Auditoria Logística Avançada.</p>
</div>
""", unsafe_allow_html=True)

abas = st.tabs(["📍 Geocodificação", "⚙️ Processamento Lote", "📦 Alocação de Hubs", "📊 Enterprise Analytics", "🧮 Calculadora Analítica", "🚨 Classificação Territorial", "📚 Enciclopédia Core", "📘 Manual do Usuário", "🔌 Monitor APIs", "🕵️ Auditoria"])

# ==============================================================================
# TAB 1: INDIVIDUAL
# ==============================================================================
with abas[0]:
    st.info("💡 **Objetivo:** Validar rapidamente uma única rota. Digite Origem e Destino para extração oficial.")
    col_ind1, col_ind2 = st.columns(2)
    with col_ind1: orig_ind = st.text_input("Origem (Endereço, POI)", "Ribeirão Cascalheira , MT, Brasil")
    with col_ind2: dest_ind = st.text_input("Destino (Endereço, POI)", "SAO MIGUEL DO ARAGUAIA , GO, Brasil")
    
    if st.button("🚀 Calcular Rota Individual", type="primary"):
        with st.spinner("Acionando motores de geocodificação unificada..."):
            res_ind = executar_pipeline_unificado(orig_ind, dest_ind)
            if res_ind:
                st.success("✅ Rota estabelecida com sucesso!")
                m1, m2, m3 = st.columns(3)
                m1.metric("Distância Viária", f"{res_ind[0]} km")
                m2.metric("Linha Reta", f"{res_ind[4]} km")
                m3.metric("Tempo", res_ind[1])
                st.info(f"🧠 **XAI Estratégia:** {res_ind[28]}")
                try: components.iframe(res_ind[29], height=470)
                except: st.warning("Mapa local bloqueado.")

# ==============================================================================
# TAB 2: LOTE
# ==============================================================================
with abas[1]:
    arquivo = st.file_uploader("Selecionar Arquivo Excel", type=["xlsx"], key="lote_std")
    if arquivo:
        df = pd.read_excel(arquivo)
        st.success(f"Tabela com {len(df)} registros mapeada.")
        if st.button("Iniciar Processamento em Lote", type="primary"):
            st.session_state['df_processado'] = rodar_pipeline_lote(df, set(zip(df['Origem'], df['Destino'])), [(1, (o, d)) for o, d in zip(df['Origem'], df['Destino'])], "Op", st.progress(0), st.empty())
            st.success("✨ Processamento em lote concluído!")
            st.dataframe(st.session_state['df_processado'], height=250)

# ==============================================================================
# TAB 3: ALOCAÇÃO DE HUBS
# ==============================================================================
with abas[2]:
    st.info("💡 **Objetivo:** Inteligência Logística de Hubs. Descubra a base mais próxima do cliente.")
    # (A lógica de interface para alocação é diretamente atrelada ao upload de 2 planilhas cruzando df_hubs e df_destinos)

# ==============================================================================
# TAB 4: ENTERPRISE ANALYTICS
# ==============================================================================
with abas[3]:
    st.markdown("### 📊 Enterprise Analytics Dashboard")
    if 'df_processado' in st.session_state:
        sync_altair_to_widgets()
        df_cf = aplicar_filtro_global(st.session_state['df_processado'], extrair_selecoes_altair())
        renderizar_indicador_filtros(extrair_selecoes_altair()['brush'])
        
        col1, col2 = st.columns(2)
        col1.metric("Rotas Filtradas", len(df_cf))
        col2.metric("Distância Total", f"{df_cf['Distancia'].sum()} km")
    else: st.warning("Processe um lote para ver os Dashboards.")

# ==============================================================================
# TAB 5 A 10: ENCICLOPÉDIA, MANUAL, ETC.
# ==============================================================================
with abas[6]:
    st.markdown("# 📚 Enciclopédia Operacional e Base de Conhecimento Core")
    with st.expander("7. Distância em Linha Reta (A Matemática do Árbitro)"):
        st.markdown(r"""
        Fórmulas trigonométricas internas para fallback (Haversine):
        $$a = \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)$$
        $$c = 2 \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1-a}\right)$$
        $$d = 6371 \cdot c$$
        """)

with abas[8]:
    st.markdown("### 🔌 Painel de Monitoramento de Infraestrutura (APIs Health Check)")
    st.dataframe(pd.DataFrame([METRICAS_DISTANCIA]), use_container_width=True)