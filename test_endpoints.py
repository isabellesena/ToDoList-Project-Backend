import unittest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Certifica-se de que a SECRET_KEY está definida antes de importar a app
os.environ["SECRET_KEY"] = "test_secret_key_1234567890_test_secret_key"

from database import Base
from main import app, Priority
from auth import get_db, hash_password
from models import UserDB, TodoDB

# Configura o banco de dados de teste (arquivo SQLite temporário)
TEST_DB_FILE = "./test_todos.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Sobrescreve a dependência get_db do FastAPI
app.dependency_overrides[get_db] = override_get_db

class TestTodoAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Garante que o arquivo do banco de teste antigo não exista
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        # Cria as tabelas no banco de dados de teste
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        # Remove o arquivo do banco de teste no fim
        if os.path.exists(TEST_DB_FILE):
            try:
                os.remove(TEST_DB_FILE)
            except PermissionError:
                pass

    def setUp(self):
        # Limpa os dados das tabelas antes de cada teste para isolamento total
        db = TestingSessionLocal()
        db.query(TodoDB).delete()
        db.query(UserDB).delete()
        db.commit()
        db.close()

    def test_toggle_todo_status(self):
        # 1. Registrar um usuário de teste
        register_payload = {
            "username": "testuser",
            "password": "testpassword",
            "email": "test@example.com"
        }
        res_reg = self.client.post("/register", json=register_payload)
        self.assertEqual(res_reg.status_code, 201)

        # 2. Fazer login para obter o token JWT
        login_data = {
            "username": "testuser",
            "password": "testpassword"
        }
        res_login = self.client.post("/login", data=login_data)
        self.assertEqual(res_login.status_code, 200)
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Criar uma tarefa (inicialmente completed=False)
        todo_payload = {
            "title": "Minha Tarefa",
            "description": "Uma descrição de teste",
            "completed": False,
            "priority": "Medium Priority"
        }
        res_create = self.client.post("/create_todo", json=todo_payload, headers=headers)
        self.assertEqual(res_create.status_code, 200)
        todo_data = res_create.json()
        todo_id = todo_data["id"]
        self.assertFalse(todo_data["completed"])

        # 4. Alternar status (Toggle) de False para True
        res_toggle_1 = self.client.patch(f"/toggle_todo/{todo_id}", headers=headers)
        self.assertEqual(res_toggle_1.status_code, 200)
        todo_data_updated_1 = res_toggle_1.json()
        self.assertTrue(todo_data_updated_1["completed"])

        # 5. Alternar status (Toggle) de True para False
        res_toggle_2 = self.client.patch(f"/toggle_todo/{todo_id}", headers=headers)
        self.assertEqual(res_toggle_2.status_code, 200)
        todo_data_updated_2 = res_toggle_2.json()
        self.assertFalse(todo_data_updated_2["completed"])

    def test_toggle_non_existent_todo(self):
        # Registrar e logar usuário para obter headers
        register_payload = {
            "username": "testuser2",
            "password": "testpassword2",
            "email": "test2@example.com"
        }
        self.client.post("/register", json=register_payload)
        res_login = self.client.post("/login", data={"username": "testuser2", "password": "testpassword2"})
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Tentar alternar o status de um ID inexistente (9999)
        res_toggle = self.client.patch("/toggle_todo/9999", headers=headers)
        self.assertEqual(res_toggle.status_code, 404)
        self.assertEqual(res_toggle.json()["detail"], "Todo not found")

    def test_toggle_other_user_todo(self):
        # Criar Usuário A e obter token
        self.client.post("/register", json={"username": "userA", "password": "passwordA", "email": "a@example.com"})
        res_login_a = self.client.post("/login", data={"username": "userA", "password": "passwordA"})
        token_a = res_login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Criar Usuário B e obter token
        self.client.post("/register", json={"username": "userB", "password": "passwordB", "email": "b@example.com"})
        res_login_b = self.client.post("/login", data={"username": "userB", "password": "passwordB"})
        token_b = res_login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Usuário A cria um todo
        todo_payload = {
            "title": "Todo do Usuário A",
            "description": "Privado",
            "completed": False,
            "priority": "Low Priority"
        }
        res_create = self.client.post("/create_todo", json=todo_payload, headers=headers_a)
        todo_id = res_create.json()["id"]

        # Usuário B tenta alternar o status do todo do Usuário A
        res_toggle = self.client.patch(f"/toggle_todo/{todo_id}", headers=headers_b)
        self.assertEqual(res_toggle.status_code, 404)
        self.assertEqual(res_toggle.json()["detail"], "Todo not found")

if __name__ == "__main__":
    unittest.main()
