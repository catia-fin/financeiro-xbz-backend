from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..prazos import calcular_prazo_dias
from ..business_days import calcular_data_prevista
from .. import conciliacao

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _get_or_create_empresa(db: Session, nome: str) -> models.Empresa:
    emp = db.query(models.Empresa).filter(models.Empresa.nome == nome).first()
    if not emp:
        emp = models.Empresa(nome=nome)
        db.add(emp)
        db.flush()
    return emp


def _get_or_create_operadora(db: Session, nome: str) -> models.Operadora:
    op = db.query(models.Operadora).filter(models.Operadora.nome == nome.upper()).first()
    if not op:
        op = models.Operadora(nome=nome.upper())
        db.add(op)
        db.flush()
    return op


@router.post("/vendas", response_model=schemas.IngestResult)
def ingest_vendas(
    batch: schemas.IngestBatch,
    db: Session = Depends(get_db),
    _=Depends(security.exigir_chave_watcher),
):
    """
    Recebe um lote de linhas vindas do watcher local.
    Regra: só INSERT. Se a combinação (empresa, operadora, chave_dedup) já existe,
    a linha é ignorada (nunca sobrescrita, nunca apagada).
    """
    inseridas = 0
    duplicadas = 0

    for v in batch.vendas:
        empresa = _get_or_create_empresa(db, v.empresa.strip().upper())
        operadora = _get_or_create_operadora(db, v.operadora.strip())

        valor_liquido = v.valor_liquido if v.valor_liquido is not None else v.valor_bruto
        valor_descontado = round(max(v.valor_bruto - valor_liquido, 0), 2)
        status_recebimento = "RECEBIDO" if (v.data_pagamento and v.data_pagamento <= date.today()) else "A_RECEBER"

        data_prevista = v.data_pagamento
        if not data_prevista:
            prazo_dias = calcular_prazo_dias(v.operadora, v.modalidade, v.parcelas)
            data_prevista = calcular_data_prevista(v.data_venda, prazo_dias)

        venda = models.Venda(
            empresa_id=empresa.id,
            operadora_id=operadora.id,
            data_venda=v.data_venda,
            data_pagamento=v.data_pagamento,
            data_prevista=data_prevista,
            valor_bruto=v.valor_bruto,
            valor_liquido=valor_liquido,
            valor_descontado=valor_descontado,
            bandeira=v.bandeira,
            modalidade=v.modalidade,
            parcelas=v.parcelas,
            autorizacao=v.autorizacao,
            nsu=v.nsu,
            lote=v.lote,
            prazo_recebimento_bruto=v.prazo_recebimento_bruto,
            status_original=v.status_original,
            status_recebimento=status_recebimento,
            arquivo_origem=v.arquivo_origem,
            linha_origem=v.linha_origem,
            chave_dedup=v.chave_dedup,
        )
        db.add(venda)
        try:
            db.flush()  # tenta gravar essa linha; se violar a chave única, cai no except
            inseridas += 1
        except IntegrityError:
            db.rollback()
            duplicadas += 1

    db.commit()
    conciliacao.conciliar_pendencias(db)
    return schemas.IngestResult(recebidas=len(batch.vendas), inseridas=inseridas, duplicadas=duplicadas)


@router.post("/ruiz", response_model=schemas.IngestResult)
def ingest_ruiz(
    batch: schemas.RuizBatch,
    db: Session = Depends(get_db),
    _=Depends(security.exigir_chave_watcher),
):
    """Recebe um lote de linhas do extrato Ruiz e tenta conciliar na hora."""
    inseridas = 0
    duplicadas = 0
    for r in batch.registros:
        empresa = _get_or_create_empresa(db, r.empresa.strip().upper())
        operadora = _get_or_create_operadora(db, r.operadora.strip())
        registro = models.Ruiz(
            empresa_id=empresa.id,
            operadora_id=operadora.id,
            emissao=r.emissao,
            bandeira=r.bandeira,
            modalidade=r.modalidade,
            lote=r.lote,
            conta=r.conta,
            valor=r.valor,
            arquivo_origem=r.arquivo_origem,
            linha_origem=r.linha_origem,
            chave_dedup=r.chave_dedup,
        )
        db.add(registro)
        try:
            db.flush()
            inseridas += 1
        except IntegrityError:
            db.rollback()
            duplicadas += 1

    db.commit()
    conciliacao.conciliar_pendencias(db)
    return schemas.IngestResult(recebidas=len(batch.registros), inseridas=inseridas, duplicadas=duplicadas)


@router.post("/futura", response_model=schemas.IngestResult)
def ingest_futura(
    batch: schemas.FuturaBatch,
    db: Session = Depends(get_db),
    _=Depends(security.exigir_chave_watcher),
):
    """Recebe um lote de linhas do extrato Futura e tenta conciliar na hora."""
    inseridas = 0
    duplicadas = 0
    for f in batch.registros:
        empresa = _get_or_create_empresa(db, f.empresa.strip().upper())
        operadora = _get_or_create_operadora(db, f.operadora.strip())
        registro = models.Futura(
            empresa_id=empresa.id,
            operadora_id=operadora.id,
            emissao=f.emissao,
            bandeira=f.bandeira,
            modalidade=f.modalidade,
            conta=f.conta,
            valor=f.valor,
            ano=f.ano,
            arquivo_origem=f.arquivo_origem,
            linha_origem=f.linha_origem,
            chave_dedup=f.chave_dedup,
        )
        db.add(registro)
        try:
            db.flush()
            inseridas += 1
        except IntegrityError:
            db.rollback()
            duplicadas += 1

    db.commit()
    conciliacao.conciliar_pendencias(db)
    return schemas.IngestResult(recebidas=len(batch.registros), inseridas=inseridas, duplicadas=duplicadas)


@router.post("/pix", response_model=schemas.IngestResult)
def ingest_pix(
    batch: schemas.PixBatch,
    db: Session = Depends(get_db),
    _=Depends(security.exigir_chave_watcher),
):
    """Recebe um lote de linhas do extrato PIX (concilia por valor líquido)."""
    inseridas = 0
    duplicadas = 0
    for p in batch.registros:
        empresa = _get_or_create_empresa(db, p.empresa.strip().upper())
        operadora = _get_or_create_operadora(db, p.operadora.strip())
        registro = models.Pix(
            empresa_id=empresa.id,
            operadora_id=operadora.id,
            data=p.data,
            conta=p.conta,
            modalidade=p.modalidade,
            bandeira=p.bandeira,
            valor=p.valor,
            nsu=p.nsu,
            usuario=p.usuario,
            arquivo_origem=p.arquivo_origem,
            linha_origem=p.linha_origem,
            chave_dedup=p.chave_dedup,
        )
        db.add(registro)
        try:
            db.flush()
            inseridas += 1
        except IntegrityError:
            db.rollback()
            duplicadas += 1

    db.commit()
    conciliacao.conciliar_pendencias(db)
    return schemas.IngestResult(recebidas=len(batch.registros), inseridas=inseridas, duplicadas=duplicadas)


@router.post("/pagamentos", response_model=schemas.IngestResult)
def ingest_pagamentos(
    batch: schemas.PagamentoBatch,
    db: Session = Depends(get_db),
    _=Depends(security.exigir_chave_watcher),
):
    """
    Recebe um lote de linhas do relatório Recebíveis (uma linha por parcela,
    mesmo NSU pode se repetir). Concilia por NSU.
    """
    inseridas = 0
    duplicadas = 0
    for pg in batch.registros:
        empresa = _get_or_create_empresa(db, pg.empresa.strip().upper())
        operadora = _get_or_create_operadora(db, pg.operadora.strip())
        registro = models.Pagamento(
            empresa_id=empresa.id,
            operadora_id=operadora.id,
            nsu=pg.nsu,
            parcela=pg.parcela,
            valor_liquido=pg.valor_liquido,
            data_prevista=pg.data_prevista,
            status_relatorio=pg.status_relatorio,
            aba_origem=pg.aba_origem,
            arquivo_origem=pg.arquivo_origem,
            linha_origem=pg.linha_origem,
            chave_dedup=pg.chave_dedup,
        )
        db.add(registro)
        try:
            db.flush()
            inseridas += 1
        except IntegrityError:
            db.rollback()
            duplicadas += 1

    db.commit()
    conciliacao.conciliar_pendencias(db)
    return schemas.IngestResult(recebidas=len(batch.registros), inseridas=inseridas, duplicadas=duplicadas)
