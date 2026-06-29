import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session 

#Neste bloco a senha é buscada para iniciar a sessão, mas se não for encontrada, devolve uma mensagem de erro.
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RunTimeError("SECRET_KEY não encontrada no arquivo .env")


#Algoritmo de criptografia usado para gerar assinaturas das chaves/token do JWT.
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 604800

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_db():
    """Abre e fecha uma sessão com o banco de dados - É um "canal de comunicação" """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara e verifica se a senha digitada pelo usuário é igual a senha salva pelo banco de dados"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """A cada chamada nova transforma a senha digitada pelo usuário em um hash novo"""
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    """Essa função devolve um objeto do tipo string, a qual é o token JWT fabricado após o recebimento do username do usuário.
     O token JWT ajuda a provar quem é que está logando"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_SECONDS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
) -> UserDB:
    """Recebe o token enviado pelo usuário e descobre quem é esse usuário. Essa função devolve um objeto do tipo
    UserDB - com id, username e todas as informações definidas anteriormente em sua composição - valida o token,
    extrai o username dele, busca no banco e devolve para a rota usar."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception 
    
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if user is None:
        raise credentials_exception
    
    return user