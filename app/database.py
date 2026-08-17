"""
Conexão com o banco de dados.

Em produção, defina a variável de ambiente DATABASE_URL apontando para um
Postgres (ex.: Railway, Render, Supabase, RDS...):

    DATABASE_URL=postgresql+psycopg2://usuario:senha@host:5432/nome_banco

Se DATABASE_URL não for definida, cai para um arquivo SQLite local
(financeiro_xbz.db), útil só para testar o backend na sua máquina.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./financeiro_xbz.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
