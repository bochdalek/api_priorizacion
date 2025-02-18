import ssl
import joblib
import numpy as np
import logging
import bcrypt
import jwt
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# Crear usuario administrador inicial si no existe
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpassword")
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

# Crear la API
app = FastAPI()

# Modelos para autenticación
class User(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Modelos para la planificación quirúrgica
class CaseData(BaseModel):
    urgency: int = Field(..., ge=0, le=5, strict=True)
    time_since_injury: int = Field(..., ge=0, le=4, strict=True)
    functional_impact: int = Field(..., ge=0, le=3, strict=True)
    patient_condition: int = Field(..., ge=0, le=2, strict=True)
    medication: str
    last_medication_date: str
    delay_days: int = Field(..., ge=0, le=6, strict=True)
    surgery_type: int = Field(2, ge=0, le=2, strict=True)
    operating_room: int = Field(1, ge=0, le=2, strict=True)

class SurgeryScheduleRequest(BaseModel):
    scheduled_patients: List[CaseData]
    available_or_morning: int = 2
    available_or_afternoon: int = 1
    max_patients_per_session: int = 2

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
@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    access_token = create_access_token(data={"sub": form_data.username, "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint para registrar un nuevo usuario
@app.post("/register")
def register(user: User):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    users_db[user.email] = {
        "username": user.email.split("@")[0],
        "hashed_password": bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode(),
        "role": "user"
    }
    return {"message": "Usuario registrado exitosamente"}

# Endpoint para convertir un usuario en administrador
@app.post("/make_admin/{email}")
def make_admin(email: str, admin: dict = Depends()):
    if email not in users_db:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    users_db[email]["role"] = "admin"
    return {"message": f"El usuario {email} ahora es administrador"}

# Endpoint de solo administradores
@app.get("/admin-only")
def admin_only(user: dict = Depends()):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: Se requieren permisos de administrador")
    return {"message": "Bienvenido, administrador"}

# Endpoint para la planificación quirúrgica
@app.post("/generate_schedule")
def generate_schedule(request: SurgeryScheduleRequest):
    morning_surgeries = []
    afternoon_surgeries = []
    waiting_list = []

    for patient in request.scheduled_patients:
        if patient.surgery_type == 2:
            if len(afternoon_surgeries) < request.available_or_afternoon * request.max_patients_per_session:
                afternoon_surgeries.append(patient)
            else:
                waiting_list.append(patient)
        else:
            if len(morning_surgeries) < request.available_or_morning * request.max_patients_per_session:
                morning_surgeries.append(patient)
            else:
                waiting_list.append(patient)

    return {
        "morning_surgeries": [p.dict() for p in morning_surgeries],
        "afternoon_surgeries": [p.dict() for p in afternoon_surgeries],
        "waiting_list": [p.dict() for p in waiting_list]
    }

@app.get("/")
def root():
    return {"message": "API de planificación quirúrgica en funcionamiento"}
