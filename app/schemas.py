from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel


class LoginRequest(BaseModel):
    login: str
    senha: str


class CadastroRequest(BaseModel):
    """Serve tanto pra criar conta nova quanto pra redefinir senha (mesmo login)."""
    login: str
    nome: Optional[str] = None
    senha: str
    confirmar_senha: str
    codigo_convite: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    nome: Optional[str] = None


class VendaIn(BaseModel):
    """Formato que o watcher local envia para cada linha nova de venda."""
    empresa: str
    operadora: str  # "REDE" | "CIELO" | "SANTANDER"
    data_venda: date
    data_pagamento: Optional[date] = None
    valor_bruto: float
    valor_liquido: Optional[float] = None
    bandeira: Optional[str] = None
    modalidade: Optional[str] = None
    parcelas: Optional[int] = None
    autorizacao: Optional[str] = None
    nsu: Optional[str] = None
    lote: Optional[str] = None
    prazo_recebimento_bruto: Optional[str] = None
    status_original: Optional[str] = None
    arquivo_origem: Optional[str] = None
    linha_origem: Optional[int] = None
    chave_dedup: str


class IngestBatch(BaseModel):
    vendas: List[VendaIn]


class IngestResult(BaseModel):
    recebidas: int
    inseridas: int
    duplicadas: int


class VendaOut(BaseModel):
    id: int
    empresa: str
    operadora: str
    data_venda: date
    data_pagamento: Optional[date]
    data_prevista: Optional[date]
    valor_bruto: float
    valor_liquido: float
    valor_descontado: float
    bandeira: Optional[str]
    modalidade: Optional[str]
    parcelas: Optional[int]
    autorizacao: Optional[str]
    nsu: Optional[str]
    lote: Optional[str] = None
    status_recebimento: str
    confirmado_via: Optional[str] = None
    status_original: Optional[str] = None

    class Config:
        from_attributes = True


class RuizIn(BaseModel):
    """Uma linha do extrato Ruiz, enviada pelo watcher."""
    empresa: str
    operadora: str
    emissao: date
    bandeira: Optional[str] = None
    modalidade: Optional[str] = None
    lote: Optional[str] = None
    conta: Optional[str] = None
    valor: float
    arquivo_origem: Optional[str] = None
    linha_origem: Optional[int] = None
    chave_dedup: str


class RuizBatch(BaseModel):
    registros: List[RuizIn]


class FuturaIn(BaseModel):
    """Uma linha do extrato Futura, enviada pelo watcher."""
    empresa: str
    operadora: str
    emissao: date
    bandeira: Optional[str] = None
    modalidade: Optional[str] = None
    conta: Optional[str] = None
    valor: float
    ano: Optional[int] = None
    arquivo_origem: Optional[str] = None
    linha_origem: Optional[int] = None
    chave_dedup: str


class FuturaBatch(BaseModel):
    registros: List[FuturaIn]


class ConfirmarRecebimento(BaseModel):
    data_pagamento: date
    valor_liquido: Optional[float] = None


class DiaProgramacao(BaseModel):
    data: date
    valor_previsto: float
    qtd_vendas: int
    por_empresa: dict


class KpiOperadora(BaseModel):
    operadora: str
    valor_recebido: float
    valor_a_receber: float
    valor_descontado: float
    valor_bruto_total: float
    qtd_vendas: int


class PixIn(BaseModel):
    """Uma linha do extrato PIX, enviada pelo watcher."""
    empresa: str
    operadora: str
    data: date
    conta: Optional[str] = None
    modalidade: Optional[str] = None
    bandeira: Optional[str] = None
    valor: float
    nsu: Optional[str] = None
    usuario: Optional[str] = None
    arquivo_origem: Optional[str] = None
    linha_origem: Optional[int] = None
    chave_dedup: str


class PixBatch(BaseModel):
    registros: List[PixIn]


class PagamentoIn(BaseModel):
    """Uma linha (uma parcela) do relatório Recebíveis, enviada pelo watcher."""
    empresa: str
    operadora: str
    nsu: str
    parcela: Optional[str] = None
    valor_liquido: float
    data_prevista: Optional[date] = None
    status_relatorio: Optional[str] = None
    aba_origem: Optional[str] = None
    arquivo_origem: Optional[str] = None
    linha_origem: Optional[int] = None
    chave_dedup: str


class PagamentoBatch(BaseModel):
    registros: List[PagamentoIn]


class ParcelaOut(BaseModel):
    """Uma parcela de uma venda parcelada, para o modal de detalhe."""
    nsu: str
    parcela: Optional[str]
    valor_liquido: float
    data_prevista: Optional[date]
    status_relatorio: Optional[str]
    status_conciliacao: str  # PENDENTE | CONCILIADO

    class Config:
        from_attributes = True


class AuditoriaOut(BaseModel):
    usuario_login: Optional[str]
    acao: str
    detalhe: Optional[str]
    criado_em: datetime

    class Config:
        from_attributes = True
