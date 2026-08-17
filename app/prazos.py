"""
Prazo de recebimento por operadora + modalidade, em DIAS CORRIDOS (a data
prevista final já é ajustada para dia útil por business_days.py).

Estes são valores TÍPICOS de mercado — ajuste para o que está no seu
contrato real com cada operadora. Se quiser, no futuro isso pode virar uma
tela de configuração em vez de um arquivo; por enquanto, edite os números
abaixo e reinicie o backend.

Formato: PRAZOS[OPERADORA][CHAVE_MODALIDADE] = dias corridos
CHAVE_MODALIDADE é um pedaço de texto que precisa aparecer (sem acento,
maiúsculo) dentro do texto de modalidade que vem do relatório.
"""

PRAZOS = {
    "REDE": {
        "PIX": 0,
        "DEBITO": 1,
        "CREDITO": 30,   # crédito à vista — usado quando não é parcelado
        "PARCELADO": 30,  # por parcela — parcela N vence em N x este valor
    },
    "CIELO": {
        "PIX": 0,
        "DEBITO": 1,
        "CREDITO": 30,
        "PARCELADO": 30,
    },
    "SANTANDER": {
        "PIX": 0,
        "DEBITO": 1,
        "CREDITO": 30,
        "PARCELADO": 30,
    },
}

PRAZO_PADRAO_DIAS = 30  # usado se não achar nenhuma combinação acima


def _normalizar(txt: str) -> str:
    import unicodedata
    if not txt:
        return ""
    t = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return t.strip().upper()


def calcular_prazo_dias(operadora: str, modalidade: str, parcelas: int | None) -> int:
    """
    Decide quantos dias corridos até o dinheiro cair, a partir da
    modalidade (texto livre vindo do relatório) e do número de parcelas.
    """
    op = _normalizar(operadora)
    mod = _normalizar(modalidade or "")
    tabela = PRAZOS.get(op, {})

    if "PIX" in mod:
        return tabela.get("PIX", 0)
    if "DEBITO" in mod or "DÉBITO" in (modalidade or "").upper():
        return tabela.get("DEBITO", 1)
    if parcelas and parcelas > 1:
        return tabela.get("PARCELADO", PRAZO_PADRAO_DIAS) * parcelas
    if "PARCEL" in mod:
        # parcelado mas sem número de parcelas informado — assume 1 ciclo
        return tabela.get("PARCELADO", PRAZO_PADRAO_DIAS)
    if "CREDITO" in mod:
        return tabela.get("CREDITO", PRAZO_PADRAO_DIAS)

    return PRAZO_PADRAO_DIAS
