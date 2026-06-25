import os
import time
import logging
import requests
from diskcache import Cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# CONFIGURAÇÃO DE LOGS E AMBIENTE
# ==============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MotorGeodesicoCorp")

METRICAS_DISTANCIA = {
    "total_calculos": 0, "sucesso_geographiclib": 0, "sucesso_geopy": 0,
    "fallback_haversine": 0, "correcoes_automaticas": 0, "falhas_criticas": 0,
    "cache_unpoisoned": 0, "barreira_territorial": 0, "desambiguacoes_estritas": 0
}

TOMTOM_API_KEY = "" # Insira sua credencial TomTom Logistics aqui

# ==============================================================================
# PERSISTÊNCIA EM DISCO (CACHES)
# ==============================================================================
cache_classificacao = Cache("./cache_classificacao")
cache_fuzzy = Cache("./cache_fuzzy")
cache_geo = Cache("./cache_geo")
cache_rotas = Cache("./cache_rotas")
cache_poi = Cache("./cache_poi")
cache_cep = Cache("./cache_cep")
cache_google = Cache("./cache_google")
cache_reverse = Cache("./cache_reverse")
cache_base_local = Cache("./cache_base_local")
cache_aprendizado = Cache("./cache_aprendizado")
cache_aprendizado_auto = Cache("./cache_aprendizado_auto")
cache_api_health = Cache("./cache_api_health")
cache_historico_lotes = Cache("./cache_historico_lotes")

def realizar_manutencao_logs_google():
    diretorio_logs = "logs_google"
    os.makedirs(diretorio_logs, exist_ok=True)
    limite_tempo = time.time() - (30 * 86400)
    try:
        for arquivo in os.listdir(diretorio_logs):
            caminho_completo = os.path.join(diretorio_logs, arquivo)
            if os.path.isfile(caminho_completo) and os.path.getmtime(caminho_completo) < limite_tempo:
                os.remove(caminho_completo)
    except Exception: pass

realizar_manutencao_logs_google()

# ==============================================================================
# REDE E SESSÃO
# ==============================================================================
session = requests.Session()
retry_strategy = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)
session.cookies.set("CONSENT", "YES+cb.20230101-00-p0.pt-BR+FX+902", domain=".google.com.br")
session.cookies.set("CONSENT", "YES+cb.20230101-00-p0.pt-BR+FX+902", domain=".google.com")

# ==============================================================================
# CONSTANTES E THREADS
# ==============================================================================
CACHE_IBGE_PATH = "municipios_ibge.pkl"
WORKERS_DISPONIVEIS = 8

EXECUTOR_GLOBAL = ThreadPoolExecutor(max_workers=WORKERS_DISPONIVEIS)
FILA_NOMINATIM = ThreadPoolExecutor(max_workers=1)
EXECUTOR_APIS = ThreadPoolExecutor(max_workers=16)

SINONIMOS_SEMANTICOS = {
    "UNB": "UNIVERSIDADE DE BRASILIA", "CATOLICA": "UNIVERSIDADE CATOLICA",
    "JK": "JUSCELINO KUBITSCHEK", "HBDF": "HOSPITAL DE BASE DO DISTRITO FEDERAL",
    "HRAN": "HOSPITAL REGIONAL DA ASA NORTE", "RODOVIARIA": "TERMINAL RODOVIARIO",
    "CD": "CENTRO DE DISTRIBUICAO", "HUB": "CENTRO LOGISTICO",
    "FILIAL": "BASE OPERACIONAL", "TECA": "TERMINAL DE CARGAS"
}

POI_KEYWORDS = [
    "AEROPORTO", "HOSPITAL", "UNIVERSIDADE", "FACULDADE", "ESCOLA", "SHOPPING", 
    "HOTEL", "RODOVIARIA", "ESTADIO", "MINISTERIO", "AGENCIA", "BANCO", 
    "IGREJA", "FORUM", "TRIBUNAL", "DELEGACIA", "PREFEITURA", "CLINICA",
    "CENTRO DE DISTRIBUICAO", "TERMINAL", "BASE OPERACIONAL"
]

BOUNDING_BOXES_UF = {
    "DF": {"lat_min": -16.05, "lat_max": -15.50, "lon_min": -48.30, "lon_max": -47.30},
    "SP": {"lat_min": -25.50, "lat_max": -19.50, "lon_min": -53.50, "lon_max": -44.00},
    "GO": {"lat_min": -19.50, "lat_max": -12.40, "lon_min": -53.30, "lon_max": -45.90},
}

CSS_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif !important; }
    .stApp { background-color: #0E1117; }
    [data-testid="stSidebar"] { background-color: #161A25; border-right: 1px solid #2D3342; }
    [data-testid="stMetric"] { background-color: #1E232F; border: 1px solid #2D3342; padding: 1.2rem; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-left: 4px solid #3B82F6; transition: transform 0.2s, box-shadow 0.2s; }
    [data-testid="stMetric"]:hover { transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.15); }
    [data-testid="stMetricLabel"] { color: #9CA3AF !important; font-weight: 500; font-size: 0.95rem; margin-bottom: 0.5rem; }
    [data-testid="stMetricValue"] { color: #F9FAFB !important; font-weight: 700; font-size: 1.8rem; }
    [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
    [data-baseweb="tab"] { background-color: #161A25; border: 1px solid #2D3342; border-bottom: none; border-radius: 8px 8px 0 0; padding: 12px 24px; color: #9CA3AF; font-weight: 600; transition: all 0.2s; }
    [data-baseweb="tab"]:hover { color: #F9FAFB; background-color: #1E232F; }
    [data-baseweb="tab"][aria-selected="true"] { background-color: #3B82F6; color: #FFFFFF; border-color: #3B82F6; }
    .stButton > button { border-radius: 6px; font-weight: 600; transition: all 0.2s; }
    .stButton > button[kind="primary"] { background-color: #3B82F6; color: white; border: none; }
    .stButton > button[kind="primary"]:hover { background-color: #2563EB; box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.5); }
    [data-testid="stExpander"] { background-color: #1E232F; border: 1px solid #2D3342; border-radius: 8px; }
    [data-testid="stExpander"] summary { font-weight: 600; color: #E5E7EB; }
    [data-testid="stDataFrame"] { border: 1px solid #2D3342; border-radius: 8px; overflow: hidden; }
    .corporate-header { background: linear-gradient(135deg, #161A25 0%, #1E232F 100%); padding: 24px; border-radius: 12px; margin-bottom: 30px; border-left: 6px solid #3B82F6; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }
    .corporate-title { color: #F9FAFB; margin: 0; font-weight: 700; font-size: 24px; letter-spacing: -0.5px; }
    .corporate-subtitle { color: #9CA3AF; margin: 5px 0 0 0; font-size: 15px; font-weight: 400; }
    .filter-badge { display: inline-block; background-color: #3B82F6; color: white; padding: 4px 10px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-right: 8px; margin-bottom: 8px; }
</style>
"""