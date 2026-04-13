"""
Triagem offline de chaves NF-e para classificar entradas vs. saídas.
Zero requisições SEFAZ — baseado apenas na estrutura da chave de 44 dígitos.

Estrutura da chave (44 dígitos):
  [0:2]   cUF       — Código da UF emitente
  [2:8]   AAMM      — Ano/Mês de emissão
  [6:20]  CNPJ      — CNPJ do emitente (14 dígitos)
  [20:22] mod       — Modelo: 55=NFe, 57=CTe, 65=NFCe
  ...
"""
import datetime


def classificar_entrada_saida(chaves_nfe: list, chaves_cte: list, cnpj_base: str) -> tuple:
    """
    Classifica as chaves NF-e em Entradas (pode manifestar) vs. Saídas/CTe (fallback direto).

    A comparação usa somente os 8 primeiros dígitos (CNPJ Raiz) para cobrir
    tanto Matriz quanto Filiais do mesmo grupo empresarial.

    Args:
        chaves_nfe:  Lista de chaves de NF-e (modelo 55) com 44 dígitos.
        chaves_cte:  Lista de chaves de CT-e (modelo 57) — nunca manifestável.
        cnpj_base:   CNPJ extraído do certificado A1 (14 dígitos, sem pontuação).

    Returns:
        (entradas, saidas_e_cte)
        - entradas:    NFe onde o cliente é DESTINATÁRIO → elegível para Manifestação
        - saidas_e_cte: NFe onde o cliente é EMITENTE + CT-e → vai direto ao fallback
    """
    cnpj_raiz_cert = cnpj_base[:8]
    entradas, saidas = [], []

    for chave in chaves_nfe:
        # Posições 6–19 = CNPJ completo (14 dígitos). Pegamos apenas [6:14] = CNPJ raiz
        # (8 primeiros dígitos) para cobrir Matriz + Filiais do mesmo grupo empresarial.
        cnpj_raiz_emitente = chave[6:14]
        if cnpj_raiz_emitente == cnpj_raiz_cert:
            saidas.append(chave)   # Emitida pelo próprio cliente — não manifesta
        else:
            entradas.append(chave)  # Destinatário — pode manifestar

    # CT-e (modelo 57) nunca é manifestável via NFeRecepcaoEvento4
    saidas.extend(chaves_cte)

    return entradas, saidas


def calcular_eta(total_entradas: int, total_saidas: int) -> dict:
    """
    Calcula o tempo estimado de cada fase para mostrar à operadora.

    Fase rápida:  Manifestação (~15s) + Delay (240s) + distNSU (~60s)
    Fase Playwright: ~15s/chave (10s captcha + 5s robô) — SEM rate-limit
    Fase lenta WebService: 180s/chave apenas se Playwright falhar
    """
    tempo_rapido_seg = (15 + 240 + 60) if total_entradas > 0 else 0
    # Playwright é o motor principal: ~15s por chave (captcha manual)
    # WebService legado (180s) só é usado se Playwright falhar totalmente
    tempo_playwright_seg = total_saidas * 15
    total_seg = tempo_rapido_seg + tempo_playwright_seg

    total = total_entradas + total_saidas
    pct_saidas = round(total_saidas / max(total, 1) * 100)

    return {
        'entradas': total_entradas,
        'saidas': total_saidas,
        'total': total,
        'pct_saidas': pct_saidas,
        'fase_rapida_min': round(tempo_rapido_seg / 60, 1),
        'fase_lenta_min': round(tempo_playwright_seg / 60, 1),
        'total_min': round(total_seg / 60, 1),
        'total_horas': round(total_seg / 3600, 1),
        'alerta_vermelho': pct_saidas > 80,  # Dispara popup se maioria são saídas
    }


def dh_evento_local() -> str:
    """
    Retorna o timestamp atual no formato ISO 8601 com fuso horário local.
    Ex: '2026-04-08T14:23:19-03:00'
    A SEFAZ rejeita UTC puro ('Z'). Nunca construir a string manualmente.
    """
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
