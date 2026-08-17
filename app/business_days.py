"""
Calendário de dias úteis brasileiro.

Calcula feriados nacionais automaticamente para qualquer ano (não é uma
lista fixa que teria que ser atualizada todo ano) e oferece funções para
somar dias corridos e "empurrar" uma data para o próximo dia útil.

Cobre feriados nacionais fixos + móveis baseados na Páscoa (Carnaval,
Sexta-feira Santa, Corpus Christi). Não cobre feriados estaduais/municipais
nem o calendário específico da B3 — para a maioria dos comércios isso já é
suficiente; se sua operadora considerar algum feriado local, dá pra somar
depois em FERIADOS_EXTRAS.
"""
from datetime import date, timedelta

# Datas extras (feriados locais, pontos facultativos bancários etc.) — adicione
# aqui se precisar, no formato date(ano, mes, dia).
FERIADOS_EXTRAS = set()


def _pascoa(ano: int) -> date:
    """Calcula a data da Páscoa para o ano dado (algoritmo de Gauss/Meeus)."""
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano: int) -> set:
    pascoa = _pascoa(ano)
    return {
        date(ano, 1, 1),                      # Confraternização Universal
        pascoa - timedelta(days=47),          # Carnaval (terça-feira)
        pascoa - timedelta(days=2),           # Sexta-feira Santa
        pascoa + timedelta(days=60),          # Corpus Christi
        date(ano, 4, 21),                     # Tiradentes
        date(ano, 5, 1),                      # Dia do Trabalho
        date(ano, 9, 7),                      # Independência
        date(ano, 10, 12),                    # Nossa Senhora Aparecida
        date(ano, 11, 2),                     # Finados
        date(ano, 11, 15),                    # Proclamação da República
        date(ano, 11, 20),                    # Dia da Consciência Negra
        date(ano, 12, 25),                    # Natal
    }


_cache_feriados = {}


def eh_feriado(d: date) -> bool:
    if d.year not in _cache_feriados:
        _cache_feriados[d.year] = feriados_nacionais(d.year) | FERIADOS_EXTRAS
    return d in _cache_feriados[d.year]


def eh_dia_util(d: date) -> bool:
    return d.weekday() < 5 and not eh_feriado(d)  # 5=sábado, 6=domingo


def proximo_dia_util(d: date) -> date:
    """Se d já é dia útil, devolve d. Senão, avança até o próximo dia útil."""
    while not eh_dia_util(d):
        d += timedelta(days=1)
    return d


def somar_dias_uteis(d: date, quantidade: int) -> date:
    """Avança 'quantidade' dias úteis a partir de d (não conta d em si)."""
    atual = d
    restante = quantidade
    passo = 1 if quantidade >= 0 else -1
    while restante != 0:
        atual += timedelta(days=passo)
        if eh_dia_util(atual):
            restante -= passo
    return atual


def calcular_data_prevista(data_venda: date, prazo_dias_corridos: int) -> date:
    """
    Regra usada aqui: soma dias CORRIDOS (como a operadora calcula o prazo
    contratual) e, se a data cair em fim de semana/feriado, empurra para o
    próximo dia útil (é quando o valor efetivamente cai na conta).
    """
    bruta = data_venda + timedelta(days=prazo_dias_corridos)
    return proximo_dia_util(bruta)
