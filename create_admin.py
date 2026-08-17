"""
Cria (ou redefine a senha de) um usuário do sistema.

Uso, dentro da pasta backend, com o ambiente virtual ativado e as mesmas
variáveis de ambiente do servidor (DATABASE_URL etc.) carregadas:

    python create_admin.py login senha "Nome Completo"

Exemplo:
    python create_admin.py joao "MinhaSenh@Forte123" "João Silva"
"""
import sys
from app.database import SessionLocal, Base, engine
from app import models, security

Base.metadata.create_all(bind=engine)


def main():
    if len(sys.argv) < 3:
        print("Uso: python create_admin.py <login> <senha> [\"Nome\"]")
        sys.exit(1)

    login, senha = sys.argv[1], sys.argv[2]
    nome = sys.argv[3] if len(sys.argv) > 3 else login

    db = SessionLocal()
    usuario = db.query(models.Usuario).filter(models.Usuario.login == login).first()
    if usuario:
        usuario.senha_hash = security.hash_senha(senha)
        usuario.nome = nome
        usuario.ativo = True
        print(f"Senha do usuário '{login}' atualizada.")
    else:
        usuario = models.Usuario(login=login, senha_hash=security.hash_senha(senha), nome=nome)
        db.add(usuario)
        print(f"Usuário '{login}' criado.")
    db.commit()
    db.close()


if __name__ == "__main__":
    main()
