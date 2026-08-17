from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _registrar(db: Session, usuario_login: str, acao: str, detalhe: str = None):
    db.add(models.Auditoria(usuario_login=usuario_login, acao=acao, detalhe=detalhe))
    db.commit()


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    login_normalizado = payload.login.strip().lower()
    usuario = db.query(models.Usuario).filter(func.lower(models.Usuario.login) == login_normalizado).first()
    if not usuario or not usuario.ativo or not security.verificar_senha(payload.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Login ou senha incorretos.")
    token = security.criar_token(usuario.login)
    _registrar(db, usuario.login, "LOGIN")
    return schemas.TokenResponse(access_token=token, nome=usuario.nome or usuario.login)


@router.post("/cadastro", response_model=schemas.TokenResponse)
def cadastro(payload: schemas.CadastroRequest, db: Session = Depends(get_db)):
    """
    Cria uma conta nova OU redefine a senha de uma conta que já existe (mesmo
    endpoint serve pros dois casos — é o "esqueci minha senha" sem burocracia:
    a pessoa só cadastra de novo com o mesmo login e uma senha nova).
    Sempre exige o código de convite, pra ninguém de fora se cadastrar sozinho.
    """
    if payload.codigo_convite != security.CODIGO_CONVITE:
        raise HTTPException(status_code=403, detail="Código de convite inválido.")
    if payload.senha != payload.confirmar_senha:
        raise HTTPException(status_code=400, detail="As senhas não coincidem.")
    if len(payload.senha) < 4:
        raise HTTPException(status_code=400, detail="Escolha uma senha com pelo menos 4 caracteres.")

    login_normalizado = payload.login.strip().lower()
    if not login_normalizado:
        raise HTTPException(status_code=400, detail="Informe um login.")

    usuario = db.query(models.Usuario).filter(func.lower(models.Usuario.login) == login_normalizado).first()
    if usuario:
        usuario.senha_hash = security.hash_senha(payload.senha)
        if payload.nome:
            usuario.nome = payload.nome
        usuario.ativo = True
        acao = "REDEFINIU_SENHA"
    else:
        usuario = models.Usuario(
            login=login_normalizado,
            senha_hash=security.hash_senha(payload.senha),
            nome=payload.nome or login_normalizado,
        )
        db.add(usuario)
        acao = "CADASTRO"

    db.commit()
    db.refresh(usuario)
    token = security.criar_token(usuario.login)
    _registrar(db, usuario.login, acao)
    return schemas.TokenResponse(access_token=token, nome=usuario.nome or usuario.login)
