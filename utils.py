import re
import math
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import logger, METRICAS_DISTANCIA

# Motores Geodésicos Estratificados
try:
    from geographiclib.geodesic import Geodesic
    GEOGRAPHICLIB_DISPONIVEL = True
except ImportError:
    GEOGRAPHICLIB_DISPONIVEL = False

try:
    from geopy.distance import geodesic
    GEOPY_DISPONIVEL = True
except ImportError:
    GEOPY_DISPONIVEL = False

class ParserGeograficoBR:
    @staticmethod
    def extrair_componentes(texto):
        componentes = {"cep": "", "numero": "", "complemento": "", "resto": texto}
        cep_match = re.search(r'\b\d{5}-?\d{3}\b', componentes["resto"])
        if cep_match:
            componentes["cep"] = cep_match.group(0).replace("-", "")
            componentes["resto"] = componentes["resto"].replace(cep_match.group(0), "").strip(" ,-")
        
        num_match = re.search(r'\b(?:N|NO|NUMERO|NUM)?\s*(\d{1,5})\b', componentes["resto"], re.IGNORECASE)
        if num_match: componentes["numero"] = num_match.group(1)
            
        comp_match = re.search(r'\b(BLOCO|BL|APTO|APT|APARTAMENTO|SALASL|SALA|CONJUNTO|CJ|CASA|LOJA|PAVIMENTO)\s*([A-Z0-9]+)\b', componentes["resto"], re.IGNORECASE)
        if comp_match: componentes["complemento"] = f"{comp_match.group(1)} {comp_match.group(2)}"
            
        return componentes

def parse_tempo_minutos(t_str):
    if not isinstance(t_str, str): return 999999
    try:
        h = re.search(r'(\d+)\s*h', t_str)
        m = re.search(r'(\d+)\s*min', t_str)
        horas = int(h.group(1)) if h else 0
        mins = int(m.group(1)) if m else 0
        if not h and not m:
            nums = re.findall(r'\d+', t_str)
            if nums: return int(nums[0])
            return 999999
        return horas * 60 + mins
    except Exception:
        return 999999

def validar_coordenada_brasil(lat, lon):
    try:
        lat_f, lon_f = float(lat), float(lon)
        if (-35.0 <= lat_f <= 6.0) and (-75.0 <= lon_f <= -28.0):
            return True, lat_f, lon_f
        if (-35.0 <= lon_f <= 6.0) and (-75.0 <= lat_f <= -28.0):
            return True, lon_f, lat_f 
        return False, lat_f, lon_f
    except (ValueError, TypeError):
        return False, 0.0, 0.0

def calcular_distancia_linha_reta(lat1, lon1, lat2, lon2, contexto=""):
    METRICAS_DISTANCIA["total_calculos"] += 1
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        dist_final, status_final = 0.0, ""
        if lat1 == 0.0 or lon1 == 0.0 or lat2 == 0.0 or lon2 == 0.0: 
            return 0.0, "Falha Operacional (Coordenadas Ausentes)"
        if lat1 == lat2 and lon1 == lon2: 
            return 0.0, "Calculada Normalmente (Pontos Coincidentes)"
            
        calculado_sucesso = False
        if GEOGRAPHICLIB_DISPONIVEL:
            try:
                dist_metros = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)['s12']
                dist_km = dist_metros / 1000.0
                if dist_km > 0:
                    METRICAS_DISTANCIA["sucesso_geographiclib"] += 1
                    dist_final, status_final = round(dist_km, 2), "Calculada via GeographicLib WGS-84"
                    calculado_sucesso = True
            except Exception as e:
                logger.warning(f"GeographicLib falhou: {e}")
                
        if not calculado_sucesso and GEOPY_DISPONIVEL:
            try:
                dist_km = geodesic((lat1, lon1), (lat2, lon2)).km
                if dist_km > 0:
                    METRICAS_DISTANCIA["sucesso_geopy"] += 1
                    dist_final, status_final = round(dist_km, 2), "Calculada via Geopy Geodesic"
                    calculado_sucesso = True
            except Exception as e:
                logger.warning(f"Geopy falhou: {e}")

        if not calculado_sucesso:
            lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2_r - lat1_r
            dlon = lon2_r - lon1_r
            a = math.sin(dlat / 2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2)**2
            c = 2 * math.asin(math.sqrt(a))
            dist_haversine = 6371.0 * c
            
            if dist_haversine >= 0.01:
                METRICAS_DISTANCIA["fallback_haversine"] += 1
                dist_final, status_final = round(dist_haversine, 2), "Calculada via Fallback Haversine"
            else:
                logger.error(f"FALHA CRÍTICA PREVENIDA: Distância zerada para pontos diferentes. Ctx: {contexto}")
                METRICAS_DISTANCIA["correcoes_automaticas"] += 1
                dist_final, status_final = 0.01, "Calculada após reprocessamento (Correção Anti-Zero)"

        if dist_final > 5000.0:
            logger.error(f"ANOMALIA TERRITORIAL: Distância excede os limites do Brasil. Ctx: {contexto}")
            METRICAS_DISTANCIA["barreira_territorial"] += 1
            return 0.01, "Falha de Bounding Box"

        return dist_final, status_final
    except Exception as e:
        logger.error(f"Erro fatal no motor geodésico ({contexto}): {e}")
        METRICAS_DISTANCIA["falhas_criticas"] += 1
        return 0.0, "Falha Operacional Crítica no Motor Geodésico"

def enviar_ticket_suporte(sugestao_texto, remetente_email, smtp_user, smtp_pass):
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = "lucas.c.cruz@gmail.com"
        msg['Subject'] = "Ticket de Manutenção - Motor Corporativo de Rotas"
        corpo = f"Novo Ticket gerado no painel UX:\n\nRemetente: {remetente_email}\n\nDescrição:\n{sugestao_texto}"
        msg.attach(MIMEText(corpo, 'plain'))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True, "Ticket transmitido com sucesso via backbone!"
    except Exception as e:
        return False, f"Erro ao tentar transmitir a solicitação via SMTP: {str(e)}"