import ssl
import joblib
import numpy as np
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from typing import Literal, List, Dict, Optional

# Configurar logging para depuración
logging.basicConfig(level=logging.INFO)

# Asegurar compatibilidad con SSL
ssl._create_default_https_context = ssl._create_unverified_context

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

# Definir la estructura de datos esperada para predict_priority
class CaseData(BaseModel):
    urgency: int = Field(..., ge=0, le=5, strict=True)
    time_since_injury: int = Field(..., ge=0, le=4, strict=True)
    functional_impact: int = Field(..., ge=0, le=3, strict=True)
    patient_condition: int = Field(..., ge=0, le=2, strict=True)
    medication: Literal["Ninguna", "Antiagregante", "Anticoagulante", "AAS", "Clopidogrel", "Prasugrel", "Ticagrelor",
                        "Acenocumarol", "Warfarina", "Dabigatrán", "Rivaroxabán", "Apixabán", "Edoxabán"]
    last_medication_date: str
    delay_days: int = Field(..., ge=0, le=6, strict=True)
    surgery_type: int = Field(2, ge=0, le=2, strict=True)  # Valor predeterminado
    operating_room: int = Field(1, ge=0, le=2, strict=True)  # Valor predeterminado

    @validator("last_medication_date")
    def validate_date(cls, v):
        try:
            date_obj = datetime.strptime(v, "%Y-%m-%d")
            if date_obj > datetime.now():
                raise ValueError("La fecha no puede ser en el futuro")
        except ValueError:
            raise ValueError("Formato de fecha inválido, debe ser YYYY-MM-DD")
        return v

# Definir la estructura de datos esperada para la programación quirúrgica
class SurgeryScheduleRequest(BaseModel):
    scheduled_patients: List[CaseData]
    available_or_morning: int = 2
    available_or_afternoon: int = 1
    max_patients_per_session: int = 2

@app.post("/generate_schedule")
def generate_schedule(request: SurgeryScheduleRequest):
    try:
        morning_surgeries = []
        afternoon_surgeries = []
        waiting_list = []

        logging.info(f"📋 Iniciando asignación de quirófanos: {len(request.scheduled_patients)} pacientes recibidos.")

        # Separar pacientes en función del tipo de cirugía y prioridad
        for patient in request.scheduled_patients:
            if patient.surgery_type == 2:  # Fracturas de cadera
                if len(afternoon_surgeries) < request.available_or_afternoon * request.max_patients_per_session:
                    afternoon_surgeries.append(patient)
                else:
                    waiting_list.append(patient)
            else:
                if len(morning_surgeries) < request.available_or_morning * request.max_patients_per_session:
                    morning_surgeries.append(patient)
                else:
                    waiting_list.append(patient)

        logging.info(f"✅ Asignación completada: {len(morning_surgeries)} en la mañana, {len(afternoon_surgeries)} en la tarde.")
        logging.info(f"⏳ Pacientes en lista de espera: {len(waiting_list)}")

        return {
            "morning_surgeries": [p.dict() for p in morning_surgeries],
            "afternoon_surgeries": [p.dict() for p in afternoon_surgeries],
            "waiting_list": [p.dict() for p in waiting_list]
        }
    except Exception as e:
        logging.error(f"❌ Error en la asignación de quirófanos: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error en la generación de la programación: {str(e)}")

@app.get("/")
def root():
    return {"message": "API de planificación quirúrgica en funcionamiento"}