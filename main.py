from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm 
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List 
from pydantic import BaseModel
from sqlalchemy.orm import Session 
from datetime import date
from enum import Enum


from database import engine, Base
from models import TodoDB, UserDB
from auth import (
    get_db, hash_password, verify_password, create_access_token, get_current_user
) 


#Cria as tabelas no banco, se ainda não existirem. Ele não faz nada se a tabela já existir
Base.metadata.create_all(bind=engine)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Priority(str,Enum):
    LOW = "Low Priority"
    MEDIUM = "Medium Priority"
    HIGH = "High Priority"


class UserCreate(BaseModel):
    username: str
    password: str 
    email: str 

class UserOut(BaseModel):
    id: int
    username: str 
    email: str 

    class Config:
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
    existing_username = db.query(UserDB).filter(UserDB.username == user.username).first()
    if existing_username: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário já cadastrado."
        )
    
    existing_email = db.query(UserDB).filter(UserDB.email == user.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já cadastrado"
        )
    
    novo_user = UserDB(
        username=user.username,
        email=user.email,     
        hashed_password=hash_password(user.password)
    )
    db.add(novo_user)
    db.commit()
    db.refresh(novo_user)
    return novo_user


@app.post("/login", response_model=Token)


def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de usuário ou senha incorretos",
            headers={"WWW-Autheticate": "Bearer"},
        )
    
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}
    

@app.get("/todo", response_model=List[Todo])

def get_todos(
    priority: Optional[Priority] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """Essa função diz ao FastAPI para rodar a rota e chamar a função get_db, entregando o seu resultado."""
    
    query = db.query(TodoDB).filter(TodoDB.owner_id == current_user.id)

    if priority is not None:
        query = query.filter(TodoDB.priority == priority.value)

    if search is not None:
        termo = f"%{search}%"
        query = query.filter(
            (TodoDB.title.ilike(termo)) | (TodoDB.description.ilike(termo))
        )

    return query.all() 


@app.post("/create_todo", response_model=Todo)

def create_todo(
    todo: TodoCreate, 
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
    ):
     """Nessa função há o recebimento do Todo, o qual foi validado pelo Pydantic, e é convertido manualmente para um TodoDB antes
     de ser salvo."""

     novo_todo = TodoDB(
         title=todo.title,
         description=todo.description,
         completed=todo.completed,
         priority=todo.priority.value, 
         owner_id=current_user.id 
     )
     db.add(novo_todo)
     db.commit()
     db.refresh(novo_todo) #atualiza o novo_todo e a data, ambos gerados pelo banco
     return novo_todo 

@app.put("/update_todo/{todo_id}", response_model=Todo)

def update_todo(
    todo_id: int, 
    todo: TodoCreate, 
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
    ):
    """Aqui a tarefa criada é identificada pelo seu id e após isso é alterada e atualizada."""

    todo_db = db.query(TodoDB).filter(
        TodoDB.id == todo_id,
        TodoDB.owner_id == current_user.id
        ). first()
    if todo_db is None:
        raise HTTPException(status_code=404,  detail="Todo not found")
    
    todo_db.title = todo.title
    todo_db.description = todo.description
    todo_db.completed = todo.completed
    todo_db.priority = todo.priority.value 
    db.commit()
    db.refresh(todo_db)
    return todo_db


@app.delete("/delete_todo/{todo_id}", response_model=Todo)

def delete_todo(
    todo_id: int, 
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
    ):
    """Nessa função a tarefa criada e/ou alterada anteriormente é deletada do banco de dados."""

    todo_db = db.query(TodoDB).filter(
        TodoDB.id == todo_id,
        TodoDB.owner_id == current_user.id 
        ).first()
    
    if todo_db is None:
        raise HTTPException(status_code=404, detail="Todo not found")

    db.delete(todo_db)
    db.commit()
    return todo_db


@app.patch("/toggle_todo/{todo_id}", response_model=Todo)
def toggle_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """Inverte o status 'completed' de uma tarefa específica do usuário."""
    todo_db = db.query(TodoDB).filter(
        TodoDB.id == todo_id,
        TodoDB.owner_id == current_user.id
    ).first()
    
    if todo_db is None:
        raise HTTPException(status_code=404, detail="Todo not found")
        
    todo_db.completed = not todo_db.completed
    db.commit()
    db.refresh(todo_db)
    return todo_db
