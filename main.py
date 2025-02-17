import ssl
import joblib
import numpy as np
import logging
import bcrypt
import jwt
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel, OAuth2 as OAuth2Model
from fastapi.openapi.models import SecurityScheme as SecuritySchemeModel
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from typing import Literal, List, Dict, Optional
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# Crear usuario administrador inicial si no existe
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpass")
if ADMIN_EMAIL not in users_db:
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
    openapi_tags=[
        {"name": "Auth", "description": "Endpoints de autenticación"},
        {"name": "Admin", "description": "Funciones solo para administradores"},
    ],
    swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
)

app.openapi_schema = {
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        }
    },
    "security": [{"bearerAuth": []}]
}

# Modelo para autenticación
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
        "role": "user"  # Por defecto, todos los nuevos usuarios son estándar
    }
    return {"message": "Usuario registrado exitosamente"}

# Dependencia para obtener usuario autenticado
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = users_db.get(payload.get("sub"))
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# Dependencia para verificar si el usuario es administrador
async def get_admin_user(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: Se requieren permisos de administrador")
    return user

# Endpoint para convertir un usuario en administrador (solo accesible por admins)
@app.post("/make_admin/{email}", tags=["Admin"])
def make_admin(email: str, admin: dict = Depends(get_admin_user)):
    if email not in users_db:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    users_db[email]["role"] = "admin"
    return {"message": f"El usuario {email} ahora es administrador"}

@app.get("/admin-only", tags=["Admin"])
def admin_only(user: dict = Depends(get_admin_user)):
    return {"message": "Bienvenido, administrador"}

@app.get("/")
def root():
    return {"message": "API de planificación quirúrgica en funcionamiento"}
