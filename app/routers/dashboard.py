from datetime import date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _aplica_filtros(q, db, empresa: Optional[str], data_ini: Optional[date], data_fim: Optional[date]):
    if empresa and empresa != "TODOS":
        q = q.join(models.Empresa).filter(models.Empresa.nome == empresa)
    if data_ini:
        q = q.filter(models.Venda.data_venda >= data_ini)
    if data_fim:
        q = q.filter(models.Venda.data_venda <= data_fim)
    return q


@router.get("/empresas", response_model=List[str])
def listar_empresas(db: Session = Depends(get_db), _=Depends(security.usuario_atual)):
    return [e.nome for e in db.query(models.Empresa).order_by(models.Empresa.nome).all()]


@router.get("/kpis", response_model=List[schemas.KpiOperadora])
def kpis_por_operadora(
    empresa: Optional[str] = Query(default=None),
    data_ini: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(security.usuario_atual),
):
    """Um cartão de KPI por operadora: recebido, a receber, descontado, bruto total."""
    resultado = []
    operadoras = db.query(models.Operadora).order_by(models.Operadora.nome).all()
    for op in operadoras:
        q = db.query(models.Venda).filter(models.Venda.operadora_id == op.id)
        q = _aplica_filtros(q, db, empresa, data_ini, data_fim)
        vendas = q.all()
        if not vendas:
            continue
        recebido = sum(v.valor_liquido for v in vendas if v.status_recebimento == "RECEBIDO")
        a_receber = sum(v.valor_liquido for v in vendas if v.status_recebimento != "RECEBIDO")
        descontado = sum(v.valor_descontado for v in vendas)
        bruto = sum(v.valor_bruto for v in vendas)
        resultado.append(schemas.KpiOperadora(
            operadora=op.nome,
            valor_recebido=round(recebido, 2),
            valor_a_receber=round(a_receber, 2),
            valor_descontado=round(descontado, 2),
            valor_bruto_total=round(bruto, 2),
            qtd_vendas=len(vendas),
        ))
    return resultado


@router.get("/vendas", response_model=List[schemas.VendaOut])
def listar_vendas(
    operadora: Optional[str] = Query(default=None),
    empresa: Optional[str] = Query(default=None),
    status_recebimento: Optional[str] = Query(default=None),
    status_original: Optional[str] = Query(default=None, description="Filtra pelo status original do relatório (ex.: Pago, Cancelado, Expirado). Deixe vazio para trazer tudo."),
    data_ini: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    limite: int = Query(default=500, le=5000),
    db: Session = Depends(get_db),
    _=Depends(security.usuario_atual),
):
    """Lista detalhada — usada no drill-down ao clicar num KPI/operadora."""
    q = db.query(models.Venda)
    if operadora and operadora != "TODOS":
        q = q.join(models.Operadora).filter(models.Operadora.nome == operadora)
    q = _aplica_filtros(q, db, empresa, data_ini, data_fim)
    if status_recebimento and status_recebimento != "TODOS":
        q = q.filter(models.Venda.status_recebimento == status_recebimento)
    if status_original and status_original != "TODOS":
        q = q.filter(models.Venda.status_original == status_original)
    q = q.order_by(models.Venda.data_venda.desc()).limit(limite)

    out = []
    for v in q.all():
        out.append(schemas.VendaOut(
            id=v.id,
            empresa=v.empresa.nome,
            operadora=v.operadora.nome,
            data_venda=v.data_venda,
            data_pagamento=v.data_pagamento,
            data_prevista=v.data_prevista,
            valor_bruto=v.valor_bruto,
            valor_liquido=v.valor_liquido,
            valor_descontado=v.valor_descontado,
            bandeira=v.bandeira,
            modalidade=v.modalidade,
            parcelas=v.parcelas,
            autorizacao=v.autorizacao,
            nsu=v.nsu,
            lote=v.lote,
            status_recebimento=v.status_recebimento,
            confirmado_via=v.confirmado_via,
            status_original=v.status_original,
        ))
    return out


@router.get("/vendas/{venda_id}/parcelas", response_model=List[schemas.ParcelaOut])
def listar_parcelas_da_venda(
    venda_id: int,
    db: Session = Depends(get_db),
    _=Depends(security.usuario_atual),
):
    """
    Para uma venda parcelada: lista as parcelas encontradas no relatório
    Recebíveis (mesmo NSU), com a data prevista de cada uma. Usado no modal
    de detalhe de parcelas na tela de Vendas.
    """
    venda = db.query(models.Venda).filter(models.Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")
    if not venda.nsu:
        return []
    registros = db.query(models.Pagamento).filter(
        models.Pagamento.empresa_id == venda.empresa_id,
        models.Pagamento.nsu == venda.nsu,
    ).order_by(models.Pagamento.parcela).all()
    return [
        schemas.ParcelaOut(
            nsu=p.nsu,
            parcela=p.parcela,
            valor_liquido=p.valor_liquido,
            data_prevista=p.data_prevista,
            status_relatorio=p.status_relatorio,
            status_conciliacao=p.status,
        )
        for p in registros
    ]




@router.get("/programacao", response_model=List[schemas.DiaProgramacao])
def programacao_proximos_dias(
    dias: int = Query(default=15, le=60),
    empresa: Optional[str] = Query(default=None),
    operadora: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(security.usuario_atual),
):
    """
    Quanto está previsto para cair, dia a dia, a partir de hoje — usa
    data_prevista para o que ainda não foi confirmado como recebido, e
    agrupa por empresa para você ver o que cai de cada uma em cada dia.
    """
    hoje = date.today()
    limite = hoje + timedelta(days=dias)

    q = db.query(models.Venda).filter(
        models.Venda.status_recebimento == "A_RECEBER",
        models.Venda.data_prevista >= hoje,
        models.Venda.data_prevista <= limite,
    )
    if operadora and operadora != "TODOS":
        q = q.join(models.Operadora).filter(models.Operadora.nome == operadora)
    if empresa and empresa != "TODOS":
        q = q.join(models.Empresa).filter(models.Empresa.nome == empresa)

    por_dia = {}
    for v in q.all():
        d = v.data_prevista
        if d not in por_dia:
            por_dia[d] = {"valor": 0.0, "qtd": 0, "empresas": {}}
        por_dia[d]["valor"] += v.valor_liquido
        por_dia[d]["qtd"] += 1
        emp_nome = v.empresa.nome
        por_dia[d]["empresas"][emp_nome] = round(por_dia[d]["empresas"].get(emp_nome, 0) + v.valor_liquido, 2)

    resultado = []
    for d in sorted(por_dia.keys()):
        info = por_dia[d]
        resultado.append(schemas.DiaProgramacao(
            data=d,
            valor_previsto=round(info["valor"], 2),
            qtd_vendas=info["qtd"],
            por_empresa=info["empresas"],
        ))
    return resultado


@router.patch("/vendas/{venda_id}/receber", response_model=schemas.VendaOut)
def confirmar_recebimento(
    venda_id: int,
    payload: schemas.ConfirmarRecebimento,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(security.usuario_atual),
):
    """
    Confirma manualmente que uma venda foi recebida (ex.: depois de conferir
    no Ruiz, Futura ou Recebíveis). Marca status RECEBIDO com a data real —
    o dashboard reflete isso automaticamente no próximo carregamento.
    """
    venda = db.query(models.Venda).filter(models.Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")
    venda.data_pagamento = payload.data_pagamento
    venda.status_recebimento = "RECEBIDO" if payload.data_pagamento <= date.today() else "A_RECEBER"
    venda.confirmado_via = "MANUAL"
    if payload.valor_liquido is not None:
        venda.valor_liquido = payload.valor_liquido
        venda.valor_descontado = round(max(venda.valor_bruto - payload.valor_liquido, 0), 2)
    db.add(models.Auditoria(
        usuario_login=usuario.login,
        acao="CONFIRMOU_RECEBIMENTO",
        detalhe=f"venda_id={venda.id} empresa={venda.empresa.nome} valor={payload.valor_liquido or venda.valor_liquido}",
    ))
    db.commit()
    db.refresh(venda)
    return schemas.VendaOut(
        id=venda.id,
        empresa=venda.empresa.nome,
        operadora=venda.operadora.nome,
        data_venda=venda.data_venda,
        data_pagamento=venda.data_pagamento,
        data_prevista=venda.data_prevista,
        valor_bruto=venda.valor_bruto,
        valor_liquido=venda.valor_liquido,
        valor_descontado=venda.valor_descontado,
        bandeira=venda.bandeira,
        modalidade=venda.modalidade,
        parcelas=venda.parcelas,
        autorizacao=venda.autorizacao,
        nsu=venda.nsu,
        lote=venda.lote,
        status_recebimento=venda.status_recebimento,
        confirmado_via=venda.confirmado_via,
        status_original=venda.status_original,
    )


@router.get("/auditoria", response_model=List[schemas.AuditoriaOut])
def listar_auditoria(
    limite: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
    _=Depends(security.usuario_atual),
):
    """
    Histórico de ações (quem fez o quê). Não tem link em destaque na tela —
    é consultado direto pela URL quando precisar checar algo.
    """
    registros = db.query(models.Auditoria).order_by(models.Auditoria.criado_em.desc()).limit(limite).all()
    return registros
