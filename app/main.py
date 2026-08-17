import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, SessionLocal
from . import models, security
from .routers import auth, ingest, dashboard

Base.metadata.create_all(bind=engine)


def bootstrap_admin():
    """
    Cria o primeiro usuário automaticamente a partir de variáveis de ambiente,
    caso ainda não exista nenhum usuário no banco. Isso evita precisar de
    acesso a terminal/shell no servidor de hospedagem para cadastrar o
    primeiro login (útil em serviços como Render/Railway no plano gratuito).

    Defina no painel de hospedagem: ADMIN_LOGIN, ADMIN_SENHA (e opcionalmente
    ADMIN_NOME). Depois do primeiro deploy bem-sucedido, essas variáveis podem
    ser removidas com segurança — elas só têm efeito quando o banco está vazio.
    """
    login = os.getenv("ADMIN_LOGIN")
    senha = os.getenv("ADMIN_SENHA")
    if not login or not senha:
        return
    db = SessionLocal()
    try:
        existe_alguem = db.query(models.Usuario).first()
        if existe_alguem:
            return
        usuario = models.Usuario(
            login=login,
            senha_hash=security.hash_senha(senha),
            nome=os.getenv("ADMIN_NOME", login),
        )
        db.add(usuario)
        db.commit()
    finally:
        db.close()


bootstrap_admin()

app = FastAPI(title="Financeiro XBZ — API de Conciliação de Cartões")

# Em produção, troque "*" pelo domínio real do site (ex.: https://financeiro.suaempresa.com.br)
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ingest.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok"}
