import os
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from .database import get_db
from . import models

JWT_SECRET = os.getenv("JWT_SECRET", "troque-esta-chave-antes-de-ir-para-producao")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

# Chave separada, fixa, usada só pelo watcher local para autenticar o envio de dados.
# Gere uma chave forte e defina em variável de ambiente no servidor E no watcher.
WATCHER_API_KEY = os.getenv("WATCHER_API_KEY", "defina-uma-chave-forte-aqui")

# Código simples pra impedir que qualquer pessoa na internet se cadastre sozinha.
# Só quem tiver esse código (você passa pra quem precisa usar o sistema) consegue
# criar conta ou redefinir senha. Defina um valor forte em produção.
CODIGO_CONVITE = os.getenv("CODIGO_CONVITE", "defina-um-codigo-aqui")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)


def criar_token(sub: str) -> str:
    expira = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": sub, "exp": expira}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def usuario_atual(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> models.Usuario:
    erro = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida, faça login novamente.")
    if not authorization.startswith("Bearer "):
        raise erro
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        login = payload.get("sub")
    except JWTError:
        raise erro
    usuario = db.query(models.Usuario).filter(models.Usuario.login == login).first()
    if not usuario or not usuario.ativo:
        raise erro
    return usuario


def exigir_chave_watcher(x_watcher_key: str = Header(default="")):
    if x_watcher_key != WATCHER_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave do watcher inválida.")
