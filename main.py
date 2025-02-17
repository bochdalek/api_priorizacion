import ssl
import joblib
import numpy as np
import logging
import bcrypt
import jwt
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging para depuración
logging.basicConfig(level=logging.INFO)

# Asegurar compatibilidad con SSL
ssl._create_default_https_context = ssl._create_unverified_context

# Configuración de autenticación
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Base de datos temporal de usuarios
users_db = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login", scheme_name="Bearer")

# Crear usuario administrador inicial si no existe
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpass")
if ADMIN_EMAIL and ADMIN_PASSWORD and ADMIN_EMAIL not in users_db:
    users_db[ADMIN_EMAIL] = {
        "username": "admin",
        "hashed_password": bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "role": "admin"
    }
    logging.info("✅ Administrador creado automáticamente.")

# Cargar el modelo entrenado con manejo de errores
try:
    model = joblib.load("prioritization_model.pkl")
except FileNotFoundError:
    model = None
    logging.error("⚠️ Error: El archivo prioritization_model.pkl no se encontró. Asegúrate de que el modelo está en la carpeta correcta.")
except Exception as e:
    model = None
    logging.error(f"⚠️ Error al cargar el modelo: {str(e)}")

# Crear la API con configuración de seguridad en Swagger
app = FastAPI(
    title="API de Planificación Quirúrgica",
    description="API para priorización y gestión de cirugías.",
    version="1.0",
    openapi_version="3.0.2",
    swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
)

# Definir OpenAPI para solucionar problemas de referencias

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "/login",
                    "scopes": {}
                }
            }
        },
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    openapi_schema["security"] = [{"bearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Modelos para autenticación
class User(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Función para autenticar usuario
def authenticate_user(email: str, password: str):
    user = users_db.get(email)
    if not user or not bcrypt.checkpw(password.encode(), user["hashed_password"].encode()):
        return None
    return user

# Función para generar token JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Endpoint para login
@app.post("/login", response_model=Token, tags=["Auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    access_token = create_access_token(data={"sub": form_data.username, "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint para registrar un nuevo usuario (siempre como usuario estándar)
@app.post("/register", tags=["Auth"])
def register(user: User):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    users_db[user.email] = {
        "username": user.email.split("@")[0],
        "hashed_password": bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode(),
        "role": "user"
    }
    return {"message": "Usuario registrado exitosamente"}

# Endpoint de prueba
@app.get("/")
def root():
    return {"message": "API de planificación quirúrgica en funcionamiento"}
