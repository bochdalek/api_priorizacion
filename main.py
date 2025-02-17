import ssl
import joblib
import np
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from typing import Literal, List, Optional

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

# Base de datos temporal
no_programables = []

# Definir la estructura de datos esperada para predict_priority
class CaseData(BaseModel):
    id: int
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
    condition_reason: Optional[str] = None  # Motivo por el que es NO PROGRAMABLE

    @validator("last_medication_date")
    def validate_date(cls, v):
        try:
            date_obj = datetime.strptime(v, "%Y-%m-%d")
            if date_obj > datetime.now():
                raise ValueError("La fecha no puede ser en el futuro")
        except ValueError:
            raise ValueError("Formato de fecha inválido, debe ser YYYY-MM-DD")
        return v

def find_patient(patient_id: int):
    """Función para encontrar un paciente en la lista de no programables.""" un paciente en la lista de no programables."""
    return next((p for p in no_programables if p.id == patient_id), None)s if p.id == patient_id), None)

# Endpoint para registrar pacientes como NO PROGRAMABLES
@app.post("/no_programables")
def add_no_programable(patient: CaseData):def add_no_programable(patient: CaseData):
    no_programables.append(patient)
    logging.info(f"🛑 Paciente {patient.id} agregado a NO PROGRAMABLES por: {patient.condition_reason}")gregado a NO PROGRAMABLES por: {patient.condition_reason}")
    return {"message": "Paciente agregado a NO PROGRAMABLES", "patient": patient.dict()} a NO PROGRAMABLES", "patient": patient.dict()}

# Endpoint para marcar a un paciente como programable y recalcular quirófanoss
@app.post("/marcar_programable/{patient_id}").post("/marcar_programable/{patient_id}")
def mark_as_programable(patient_id: int):able(patient_id: int):
    global no_programables
    patient = find_patient(patient_id)patient = find_patient(patient_id)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado en NO PROGRAMABLES")    raise HTTPException(status_code=404, detail="Paciente no encontrado en NO PROGRAMABLES")
    
    no_programables = [p for p in no_programables if p.id != patient_id]
    logging.info(f"✅ Paciente {patient_id} marcado como PROGRAMABLE")    logging.info(f"✅ Paciente {patient_id} marcado como PROGRAMABLE")
    
    # Aquí podemos agregar lógica para reprogramar automáticamente al paciente en quirófanospodemos agregar lógica para reprogramar automáticamente al paciente en quirófanos
    return {"message": "Paciente marcado como PROGRAMABLE y reasignado"}





    return {"message": "API de planificación quirúrgica en funcionamiento"}def root():@app.get("/")@app.get("/")
def root():
    return {"message": "API de planificación quirúrgica en funcionamiento"}
