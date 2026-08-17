"""
Backup extra — exporta todas as vendas do banco para um arquivo Excel datado.

Isso é uma camada de segurança ALÉM do backup automático do banco (Neon já
faz o dele sozinho). A ideia aqui é ter um "retrato" independente, em Excel,
gravado fisicamente na pasta da empresa — útil se um dia você quiser abrir
os dados sem depender de nada online, ou como segunda cópia de segurança.

Como rodar manualmente:
    cd backend
    python backup_export.py

Como agendar para rodar sozinho todo dia (Windows):
    1. Abra o "Agendador de Tarefas" do Windows.
    2. Criar Tarefa Básica → repita diariamente, no horário que quiser
       (ex.: 22h, fora do horário de expediente).
    3. Ação: iniciar um programa.
       Programa: caminho do seu python.exe
       Argumentos: backup_export.py
       Iniciar em: o caminho completo da pasta backend

Variáveis de ambiente usadas (mesmas do backend):
    DATABASE_URL   — de onde puxar os dados (o mesmo Postgres de produção,
                     ou o SQLite local se não tiver definida)
    BACKUP_DIR     — pasta onde salvar os arquivos .xlsx (padrão: ./backups,
                     mas o ideal é apontar para a pasta de rede da empresa,
                     ex.: defina BACKUP_DIR=G:\\FINANCEIRO\\...\\BACKUPS)
    BACKUP_MANTER  — quantos backups antigos manter (padrão: 60 — o resto é
                     apagado automaticamente para não lotar o disco)
"""
import os
from datetime import datetime, timedelta

import pandas as pd

from app.database import SessionLocal
from app import models


def exportar():
    pasta_destino = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(__file__), "backups"))
    os.makedirs(pasta_destino, exist_ok=True)
    manter = int(os.getenv("BACKUP_MANTER", "60"))

    db = SessionLocal()
    try:
        vendas = (
            db.query(models.Venda)
            .join(models.Empresa)
            .join(models.Operadora)
            .order_by(models.Venda.data_venda)
            .all()
        )

        linhas = []
        for v in vendas:
            linhas.append({
                "id": v.id,
                "empresa": v.empresa.nome,
                "operadora": v.operadora.nome,
                "data_venda": v.data_venda,
                "data_prevista": v.data_prevista,
                "data_pagamento": v.data_pagamento,
                "valor_bruto": v.valor_bruto,
                "valor_liquido": v.valor_liquido,
                "valor_descontado": v.valor_descontado,
                "bandeira": v.bandeira,
                "modalidade": v.modalidade,
                "parcelas": v.parcelas,
                "autorizacao": v.autorizacao,
                "nsu": v.nsu,
                "status_recebimento": v.status_recebimento,
                "criado_em": v.criado_em,
            })

        df = pd.DataFrame(linhas)
        agora = datetime.now().strftime("%Y-%m-%d_%Hh%M")
        caminho_arquivo = os.path.join(pasta_destino, f"backup_vendas_{agora}.xlsx")
        df.to_excel(caminho_arquivo, index=False, sheet_name="vendas")
        print(f"✅ Backup salvo: {caminho_arquivo} ({len(df)} linha(s))")

        _rotacionar(pasta_destino, manter)
    finally:
        db.close()


def _rotacionar(pasta, manter):
    """Mantém só os N backups mais recentes, apaga o resto para não lotar o disco."""
    arquivos = [
        os.path.join(pasta, f) for f in os.listdir(pasta)
        if f.startswith("backup_vendas_") and f.endswith(".xlsx")
    ]
    arquivos.sort(key=os.path.getmtime, reverse=True)
    for antigo in arquivos[manter:]:
        try:
            os.remove(antigo)
            print(f"🧹 Backup antigo removido: {os.path.basename(antigo)}")
        except OSError:
            pass


if __name__ == "__main__":
    exportar()
