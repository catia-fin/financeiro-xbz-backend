"""
Modelos do banco.

Regra de ouro do sistema: NUNCA fazer UPDATE que apague valor já gravado e
NUNCA fazer DELETE de venda. O watcher só faz INSERT de linhas novas; se uma
linha já existe (mesma empresa + operadora + chave_dedup), ela é ignorada.
Conciliação/observações entram como campos que só evoluem de PENDENTE -> algo,
nunca voltam a apagar dado histórico.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    login = Column(String(80), unique=True, nullable=False, index=True)
    senha_hash = Column(String(200), nullable=False)
    nome = Column(String(120), nullable=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, server_default=func.now())


class Auditoria(Base):
    """
    Histórico de ações — quem fez o quê. Fica guardado, mas não aparece em
    destaque na tela (é consultado à parte, quando precisar checar algo).
    Nunca é apagado.
    """
    __tablename__ = "auditoria"
    id = Column(Integer, primary_key=True)
    usuario_login = Column(String(80), nullable=True)  # texto solto — nunca falha mesmo se o usuário for removido depois
    acao = Column(String(60), nullable=False)  # LOGIN | CADASTRO | REDEFINIU_SENHA | CONFIRMOU_RECEBIMENTO | ...
    detalhe = Column(String(400), nullable=True)
    criado_em = Column(DateTime, server_default=func.now())


class Empresa(Base):
    __tablename__ = "empresas"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(30), unique=True, nullable=True)   # ex.: código de estabelecimento
    nome = Column(String(120), unique=True, nullable=False)


class Operadora(Base):
    """REDE, CIELO, SANTANDER... cadastro simples, dá pra adicionar mais depois."""
    __tablename__ = "operadoras"
    id = Column(Integer, primary_key=True)
    nome = Column(String(40), unique=True, nullable=False)  # "REDE", "CIELO", "SANTANDER"


class Venda(Base):
    """
    Uma linha do relatório de vendas de uma operadora.
    valor_descontado é calculado (bruto - liquido) e representa taxa/desconto da venda.
    status_recebimento é derivado da data_pagamento na hora da ingestão e pode ser
    recalculado depois (endpoint de manutenção), mas a linha em si nunca é apagada.
    """
    __tablename__ = "vendas"
    id = Column(Integer, primary_key=True)

    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    operadora_id = Column(Integer, ForeignKey("operadoras.id"), nullable=False)

    data_venda = Column(Date, nullable=False)
    data_pagamento = Column(Date, nullable=True)  # quando cai na conta (se já informado no relatório)
    data_prevista = Column(Date, nullable=True)   # estimativa calculada (prazo da modalidade + dias úteis)

    valor_bruto = Column(Float, nullable=False, default=0)
    valor_liquido = Column(Float, nullable=False, default=0)
    valor_descontado = Column(Float, nullable=False, default=0)  # bruto - liquido

    bandeira = Column(String(40), nullable=True)
    modalidade = Column(String(40), nullable=True)   # débito / crédito à vista / parcelado
    parcelas = Column(Integer, nullable=True)
    autorizacao = Column(String(40), nullable=True)
    nsu = Column(String(40), nullable=True)

    status_recebimento = Column(String(20), default="A_RECEBER")  # A_RECEBER | RECEBIDO
    confirmado_via = Column(String(20), nullable=True)  # RUIZ | FUTURA | PIX | RECEBIVEIS | MANUAL
    lote = Column(String(60), nullable=True)  # "resumo de vendas/número do lote" — quando o relatório já traz
    prazo_recebimento_bruto = Column(String(60), nullable=True)  # texto original da coluna "Prazo de recebimento"
    status_original = Column(String(60), nullable=True)  # status como veio no relatório (Pago/Cancelado/Expirado...) — nunca apagado, só usado pra filtrar a tela

    # rastreabilidade da origem (arquivo/linha) — não usado para exibir, só auditoria
    arquivo_origem = Column(String(400), nullable=True)
    linha_origem = Column(Integer, nullable=True)

    # chave usada para nunca duplicar a mesma linha vinda do relatório
    chave_dedup = Column(String(200), nullable=False, index=True)

    criado_em = Column(DateTime, server_default=func.now())

    empresa = relationship("Empresa")
    operadora = relationship("Operadora")

    __table_args__ = (
        UniqueConstraint("empresa_id", "operadora_id", "chave_dedup", name="uq_venda_dedup"),
    )


class Ruiz(Base):
    """
    Extrato de conferência (ex.: administradora/contabilidade terceira).
    Bate contra uma Venda por data + valor + empresa + bandeira/modalidade
    (regra especial para PIX — ver app/conciliacao.py). Quando bate, a
    Venda correspondente é marcada como RECEBIDO.
    """
    __tablename__ = "ruiz"
    id = Column(Integer, primary_key=True)

    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    operadora_id = Column(Integer, ForeignKey("operadoras.id"), nullable=False)

    emissao = Column(Date, nullable=False)
    bandeira = Column(String(60), nullable=True)
    modalidade = Column(String(60), nullable=True)
    lote = Column(String(60), nullable=True)
    conta = Column(String(60), nullable=True)
    valor = Column(Float, nullable=False, default=0)

    status = Column(String(20), default="PENDENTE")  # PENDENTE | CONCILIADO
    venda_id = Column(Integer, ForeignKey("vendas.id"), nullable=True)

    arquivo_origem = Column(String(400), nullable=True)
    linha_origem = Column(Integer, nullable=True)
    chave_dedup = Column(String(200), nullable=False, index=True)
    criado_em = Column(DateTime, server_default=func.now())

    empresa = relationship("Empresa")
    operadora = relationship("Operadora")
    venda = relationship("Venda")

    __table_args__ = (
        UniqueConstraint("empresa_id", "operadora_id", "chave_dedup", name="uq_ruiz_dedup"),
    )


class Futura(Base):
    """
    Segunda fonte de conferência (ex.: pagamentos futuros/outlet), separada
    do Ruiz. Mesma lógica de conciliação contra a Venda.
    """
    __tablename__ = "futura"
    id = Column(Integer, primary_key=True)

    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    operadora_id = Column(Integer, ForeignKey("operadoras.id"), nullable=False)

    emissao = Column(Date, nullable=False)
    bandeira = Column(String(60), nullable=True)
    modalidade = Column(String(60), nullable=True)
    conta = Column(String(60), nullable=True)
    valor = Column(Float, nullable=False, default=0)
    ano = Column(Integer, nullable=True)

    status = Column(String(20), default="PENDENTE")  # PENDENTE | CONCILIADO
    venda_id = Column(Integer, ForeignKey("vendas.id"), nullable=True)

    arquivo_origem = Column(String(400), nullable=True)
    linha_origem = Column(Integer, nullable=True)
    chave_dedup = Column(String(200), nullable=False, index=True)
    criado_em = Column(DateTime, server_default=func.now())

    empresa = relationship("Empresa")
    operadora = relationship("Operadora")
    venda = relationship("Venda")

    __table_args__ = (
        UniqueConstraint("empresa_id", "operadora_id", "chave_dedup", name="uq_futura_dedup"),
    )


class Pix(Base):
    """
    Extrato de PIX, separado do Ruiz/Futura. Concilia contra a Venda pelo
    VALOR LÍQUIDO (não o bruto), já que PIX normalmente não tem desconto de
    taxa igual cartão.
    """
    __tablename__ = "pix"
    id = Column(Integer, primary_key=True)

    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    operadora_id = Column(Integer, ForeignKey("operadoras.id"), nullable=False)

    data = Column(Date, nullable=False)
    conta = Column(String(60), nullable=True)
    modalidade = Column(String(60), nullable=True)
    bandeira = Column(String(60), nullable=True)
    valor = Column(Float, nullable=False, default=0)
    nsu = Column(String(40), nullable=True)
    usuario = Column(String(60), nullable=True)

    status = Column(String(20), default="PENDENTE")
    venda_id = Column(Integer, ForeignKey("vendas.id"), nullable=True)

    arquivo_origem = Column(String(400), nullable=True)
    linha_origem = Column(Integer, nullable=True)
    chave_dedup = Column(String(200), nullable=False, index=True)
    criado_em = Column(DateTime, server_default=func.now())

    empresa = relationship("Empresa")
    operadora = relationship("Operadora")
    venda = relationship("Venda")

    __table_args__ = (
        UniqueConstraint("empresa_id", "operadora_id", "chave_dedup", name="uq_pix_dedup"),
    )


class Pagamento(Base):
    """
    Relatório "Recebíveis" — previsão do que vai cair, por NSU/parcela (uma
    venda parcelada aparece como várias linhas aqui, uma por parcela: 1/3,
    2/3, 3/3...). Concilia contra a Venda pelo NSU (é o vínculo mais
    confiável nesse relatório, já que o valor vem fatiado por parcela).
    """
    __tablename__ = "pagamentos"
    id = Column(Integer, primary_key=True)

    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    operadora_id = Column(Integer, ForeignKey("operadoras.id"), nullable=False)

    nsu = Column(String(40), nullable=False, index=True)
    parcela = Column(String(20), nullable=True)  # ex.: "1/3"
    valor_liquido = Column(Float, nullable=False, default=0)
    data_prevista = Column(Date, nullable=True)
    status_relatorio = Column(String(60), nullable=True)  # status como veio no próprio relatório
    aba_origem = Column(String(60), nullable=True)  # "pagamentos" ou "pagamentos futuros"

    status = Column(String(20), default="PENDENTE")
    venda_id = Column(Integer, ForeignKey("vendas.id"), nullable=True)

    arquivo_origem = Column(String(400), nullable=True)
    linha_origem = Column(Integer, nullable=True)
    chave_dedup = Column(String(200), nullable=False, index=True)
    criado_em = Column(DateTime, server_default=func.now())

    empresa = relationship("Empresa")
    operadora = relationship("Operadora")
    venda = relationship("Venda")

    __table_args__ = (
        UniqueConstraint("empresa_id", "operadora_id", "chave_dedup", name="uq_pagamento_dedup"),
    )
