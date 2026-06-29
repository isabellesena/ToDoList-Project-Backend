from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm 
from typing import Optional, List 
from pydantic import BaseModel
from sqlalchemy.orm import Session 
from datetime import date
from enum import Enum


from database import engine, SessionLocal, Base 
from models import TodoDB, UserDB
from auth import (
    get_db, hash_password, verify_password, create_access_token, get_current_user
) 


#Cria as tabelas no banco, se ainda não existirem. Ele não faz nada se a tabela já existir
Base.metadata.create_all(bind=engine)


app = FastAPI()


class Priority(str,Enum):
    LOW = "Low Priority"
    MEDIUM = "Medium Priority"
    HIGH = "High Priority"


class UserCreate(BaseModel):
    username: str
    password: str 


class UserOut(BaseModel):
    username: str
    password: str 

    class COnfig:
        from_attributes = True 


class Token(BaseModel):
    access_token: str
    token_type: str 


#Essa classe define os tópicos disponíveis para serem definidos pelo usuário.
class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: Priority = None 


#Essa classe apresenta os tópicos definidos pelo usuário mais os tópicos fixos devolvidos pela API.
class Todo(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: Priority 
    created_at: date 
    owner_id: int 

    #Essa classe converte o TodoTB para Todo automaticamente.
    class Config:
        from_attributes = True 


@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)


def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.username == user.username).first()
    if existing: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username já cadastrado"
        )
    novo_user = UserDB(
        username=user.username,
        hashed_password=hash_password(user.password)
    )
    db.add(novo_user)
    db.commit()
    db.refresh(novo_user)
    return novo_user

    
def get_db():
    """Essa função abre uma nova sessão com o banco. Entrega a sessão para a rota usar e quando termina, fecha a sessão 
    automaticamente, mesmo se der erro."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/todo", response_model=List[Todo])

def root(
    priority: Optional[Priority] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Essa função diz ao FastAPI para rodar a rota e chamar a função get_db, entregando o seu resultado."""
    
    query = db.query(TodoDB)

    if priority is not None:
        query = query.filter(TodoDB.priority == priority.value)

    if search is not None:
        termo = f"%{search}%"
        query = query.filter(
            (TodoDB.title.ilike(termo)) | (TodoDB.description.ilike(termo))
        )

    return query.all() 


@app.post("/create_todo", response_model=Todo)

def create_todo(todo: TodoCreate, db: Session = Depends(get_db)):
     """Nessa função há o recebimento do Todo, o qual foi validado pelo Pydantic, e é convertido manualmente para um TodoDB antes
     de ser salvo."""

     novo_todo = TodoDB(
         title=todo.title,
         description=todo.description,
         completed=todo.completed,
         priority=todo.priority.value, 
     )
     db.add(novo_todo)
     db.commit()
     db.refresh(novo_todo) #atualiza o novo_todo e a data, ambos gerados pelo banco
     return novo_todo 

@app.put("/update_todo/{todo_id}", response_model=Todo)

def update_todo(todo_id: int, todo: Todo, db: Session = Depends(get_db)):
    """Aqui a tarefa criada é identificada pelo seu id e após isso é alterada e atualizada."""

    todo_db = db.query(TodoDB).filter(TodoDB.id == todo_id). first()
    if todo_db is None:
        raise HTTPException(status_code=404,  detail="Todo not found")
    
    todo_db.title = todo.title
    todo_db.description = todo.description
    todo_db.completed = todo.completed
    db.commit()
    db.refresh(todo_db)
    return todo_db


@app.delete("/delete_todo/{todo_id}", response_model=Todo)

def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    """Nessa função a tarefa criada e/ou alterada anteriormente é deletada do banco de dados."""

    todo_db = db.query(TodoDB).filter(TodoDB.id == todo_id).first()
    if todo_db is None:
        raise HTTPException(status_code=404, detail="Todo not found")

    db.delete(todo_db)
    db.commit()
    return todo_db
