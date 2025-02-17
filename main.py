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
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional, List
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

# Agregar seguridad de autorización con JWT en Swagger

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

# Endpoint para login
@app.post("/login", response_model=Token, tags=["Auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or not bcrypt.checkpw(form_data.password.encode(), user["hashed_password"].encode()):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    access_token = jwt.encode({"sub": form_data.username, "role": user["role"]}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint para registrar un nuevo usuario
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

# Endpoint para convertir un usuario en administrador (solo accesible por admins)
@app.post("/make_admin/{email}", tags=["Admin"], dependencies=[Depends(oauth2_scheme)])
def make_admin(email: str):
    if email not in users_db:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    users_db[email]["role"] = "admin"
    return {"message": f"El usuario {email} ahora es administrador"}

# Endpoint para acceder solo como administrador
@app.get("/admin-only", tags=["Admin"], dependencies=[Depends(oauth2_scheme)])
def admin_only():
    return {"message": "Bienvenido, administrador"}

# Endpoint de planificación quirúrgica
@app.post("/generate_schedule")
def generate_schedule(request: List[dict]):
    return {"message": "Generación de planificación en desarrollo", "data": request}

# Endpoint de prueba
@app.get("/")
def root():
    return {"message": "API de planificación quirúrgica en funcionamiento"}
