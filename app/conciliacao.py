"""
Motor de conciliação — porta a lógica do seu app antigo (normalizar_texto /
padronizar_chave / conciliacao_automatica) para o backend.

Regra de bate/não-bate:
- Mesma empresa, mesma data e mesmo valor (arredondado a 2 casas) são
  obrigatórios sempre.
- Se o registro do Ruiz/Futura é PIX (aparece "PIX" na bandeira), ele bate
  com a MODALIDADE da venda (não a bandeira) — igual ao seu app original.
- Caso contrário, bandeira bate com bandeira e modalidade bate com
  modalidade, ambos "padronizados" (maiúsculo, sem acento, sem espaço/
  pontuação, MASTERCARD normalizado para MASTER).

Nunca apaga nada — só liga (seta venda_id) e marca status. Uma venda já
RECEBIDA não é reavaliada.
"""
import unicodedata

from . import models


def padronizar(txt) -> str:
    if not txt:
        return ""
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode("ascii")
    t = t.strip().upper()
    for ch in (" ", "-", ".", "/", "_"):
        t = t.replace(ch, "")
    t = t.replace("MASTERCARD", "MASTER")
    return t


def conciliar_pendencias(db) -> dict:
    """Roda uma passada de conciliação sobre tudo que ainda está pendente."""
    vinculos_ruiz = 0
    vinculos_futura = 0

    # ===== RUIZ =====
    ruiz_pendentes = db.query(models.Ruiz).filter(models.Ruiz.venda_id.is_(None)).all()
    for r in ruiz_pendentes:
        venda_encontrada = None

        # Plano A: casar direto pelo lote, quando o relatório de vendas já o traz
        # (bem mais confiável que data+valor+bandeira).
        if r.lote:
            venda_encontrada = db.query(models.Venda).filter(
                models.Venda.empresa_id == r.empresa_id,
                models.Venda.lote == r.lote,
                models.Venda.status_recebimento != "RECEBIDO",
            ).first()

        # Plano B: data + valor + bandeira/modalidade (regra especial de PIX).
        if not venda_encontrada:
            band_r = padronizar(r.bandeira)
            mod_r = padronizar(r.modalidade)
            eh_pix_ruiz = "PIX" in band_r
            valor_r = round(r.valor, 2)

            candidatos = db.query(models.Venda).filter(
                models.Venda.empresa_id == r.empresa_id,
                models.Venda.data_venda == r.emissao,
                models.Venda.status_recebimento != "RECEBIDO",
            ).all()

            for v in candidatos:
                if round(v.valor_bruto, 2) != valor_r:
                    continue
                band_v = padronizar(v.bandeira)
                mod_v = padronizar(v.modalidade)
                bate = (band_r == mod_v) if eh_pix_ruiz else (band_r == band_v and mod_r == mod_v)
                if bate:
                    venda_encontrada = v
                    break

        if venda_encontrada:
            r.venda_id = venda_encontrada.id
            r.status = "CONCILIADO"
            venda_encontrada.status_recebimento = "RECEBIDO"
            venda_encontrada.data_pagamento = r.emissao
            venda_encontrada.confirmado_via = "RUIZ"
            if r.lote and not venda_encontrada.lote:
                venda_encontrada.lote = r.lote
            vinculos_ruiz += 1

    # ===== FUTURA =====
    futura_pendentes = db.query(models.Futura).filter(models.Futura.venda_id.is_(None)).all()
    for f in futura_pendentes:
        band_f = padronizar(f.bandeira)
        mod_f = padronizar(f.modalidade)
        eh_pix_f = "PIX" in band_f
        valor_f = round(f.valor, 2)

        candidatos = db.query(models.Venda).filter(
            models.Venda.empresa_id == f.empresa_id,
            models.Venda.data_venda == f.emissao,
            models.Venda.status_recebimento != "RECEBIDO",
        ).all()

        for v in candidatos:
            if round(v.valor_bruto, 2) != valor_f:
                continue
            band_v = padronizar(v.bandeira)
            mod_v = padronizar(v.modalidade)
            eh_pix_v = "PIX" in mod_v
            bate = (eh_pix_f and eh_pix_v) or (band_f == band_v and mod_f == mod_v)
            if bate:
                f.venda_id = v.id
                f.status = "CONCILIADO"
                v.status_recebimento = "RECEBIDO"
                v.data_pagamento = f.emissao
                v.confirmado_via = "FUTURA"
                vinculos_futura += 1
                break

    # ===== PIX ===== (concilia pelo VALOR LÍQUIDO da venda, não o bruto)
    pix_pendentes = db.query(models.Pix).filter(models.Pix.venda_id.is_(None)).all()
    vinculos_pix = 0
    for p in pix_pendentes:
        valor_p = round(p.valor, 2)
        candidatos = db.query(models.Venda).filter(
            models.Venda.empresa_id == p.empresa_id,
            models.Venda.status_recebimento != "RECEBIDO",
        ).all()
        for v in candidatos:
            if round(v.valor_liquido, 2) != valor_p:
                continue
            if p.nsu and v.nsu and p.nsu != v.nsu:
                continue
            p.venda_id = v.id
            p.status = "CONCILIADO"
            v.status_recebimento = "RECEBIDO"
            v.data_pagamento = p.data
            v.confirmado_via = "PIX"
            vinculos_pix += 1
            break

    # ===== PAGAMENTOS (Recebíveis) ===== (concilia pelo NSU — é o vínculo mais
    # confiável nesse relatório, já que o valor vem fatiado por parcela)
    pagamentos_pendentes = db.query(models.Pagamento).filter(
        models.Pagamento.venda_id.is_(None), models.Pagamento.nsu.isnot(None)
    ).all()
    vinculos_pagamentos = 0
    for pg in pagamentos_pendentes:
        venda_encontrada = db.query(models.Venda).filter(
            models.Venda.empresa_id == pg.empresa_id,
            models.Venda.nsu == pg.nsu,
        ).first()
        if venda_encontrada:
            pg.venda_id = venda_encontrada.id
            pg.status = "CONCILIADO"
            if venda_encontrada.status_recebimento != "RECEBIDO":
                venda_encontrada.status_recebimento = "RECEBIDO"
                if pg.data_prevista:
                    venda_encontrada.data_pagamento = pg.data_prevista
                venda_encontrada.confirmado_via = "RECEBIVEIS"
            vinculos_pagamentos += 1

    db.commit()
    return {"ruiz": vinculos_ruiz, "futura": vinculos_futura, "pix": vinculos_pix, "pagamentos": vinculos_pagamentos}
