import ssl
import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from typing import Literal

# Asegurar compatibilidad con SSL
ssl._create_default_https_context = ssl._create_unverified_context

# Cargar el modelo entrenado con manejo de errores
try:
    model = joblib.load("prioritization_model.pkl")
except FileNotFoundError:
    model = None
    print("⚠️ Error: El archivo prioritization_model.pkl no se encontró. Asegúrate de que el modelo está en la carpeta correcta.")
except Exception as e:
    model = None
    print(f"⚠️ Error al cargar el modelo: {str(e)}")

# Crear la API
app = FastAPI()

# Definir la estructura de datos esperada para predict_priority
class CaseData(BaseModel):
    urgency: int = Field(..., ge=0, le=5)
    time_since_injury: int = Field(..., ge=0, le=4)
    functional_impact: int = Field(..., ge=0, le=3)
    patient_condition: int = Field(..., ge=0, le=2)
    medication: Literal["Ninguna", "Antiagregante", "Anticoagulante", "AAS", "Clopidogrel", "Prasugrel", "Ticagrelor",
                        "Acenocumarol", "Warfarina", "Dabigatrán", "Rivaroxabán", "Apixabán", "Edoxabán"]
    last_medication_date: str
    delay_days: int = Field(..., ge=0, le=6)
    surgery_type: int = Field(2, ge=0, le=2)  # Valor predeterminado
    operating_room: int = Field(1, ge=0, le=2)  # Valor predeterminado

    @validator("last_medication_date")
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Formato de fecha inválido, debe ser YYYY-MM-DD")
        return v

# Definir la estructura de datos esperada para predict_surgery_date
class SurgeryDateRequest(BaseModel):
    medication: Literal["AAS", "Clopidogrel", "Prasugrel", "Ticagrelor",
                        "Acenocumarol", "Warfarina", "Dabigatrán", "Rivaroxabán", "Apixabán", "Edoxabán"]
    last_medication_date: str

    @validator("last_medication_date")
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Formato de fecha inválido, debe ser YYYY-MM-DD")
        return v

# Mapeo de medicamentos a valores numéricos
medication_map = {
    "Ninguna": 0,
    "Antiagregante": 1,
    "Anticoagulante": 2,
    "AAS": 3,
    "Clopidogrel": 4,
    "Prasugrel": 5,
    "Ticagrelor": 6,
    "Acenocumarol": 7,
    "Warfarina": 8,
    "Dabigatrán": 9,
    "Rivaroxabán": 10,
    "Apixabán": 11,
    "Edoxabán": 12
}

# Mapeo de días de suspensión según el medicamento
medication_suspension_days = {
    "AAS": 1,  # En monoterapia, 24h antes
    "Clopidogrel": 5,
    "Prasugrel": 7,
    "Ticagrelor": 5,
    "Acenocumarol": 3,
    "Warfarina": 5,
    "Dabigatrán": 3,
    "Rivaroxabán": 2,
    "Apixabán": 2,
    "Edoxabán": 2,
}

@app.post("/predict_surgery_date")
def predict_surgery_date(request: SurgeryDateRequest):
    try:
        # Determinar días de suspensión necesarios
        suspension_days = medication_suspension_days.get(request.medication, 0)
        
        # Calcular fecha óptima para cirugía
        last_med_date = datetime.strptime(request.last_medication_date, "%Y-%m-%d")
        surgery_date = last_med_date + timedelta(days=suspension_days)
        
        return {"surgery_date": surgery_date.strftime("%Y-%m-%d")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en el cálculo de la fecha de cirugía: {str(e)}")

@app.post("/predict_priority")
def predict_priority(case: CaseData):
    if model is None:
        raise HTTPException(status_code=500, detail="Modelo no encontrado. No se puede predecir prioridad.")
    try:
        medication_value = medication_map.get(case.medication, -1)  # Convertir medicamento a número
        
        # Preparar los datos para el modelo
        input_data = np.array([[case.urgency, case.time_since_injury, case.functional_impact,
                                 case.patient_condition, medication_value, case.delay_days, case.surgery_type, case.operating_room]])
        
        # Obtener predicción de prioridad
        predicted_priority = model.predict(input_data)[0]
        
        # Mapeo inverso para devolver un texto
        priority_map = {3: "Urgente", 2: "Alta", 1: "Media", 0: "Baja"}
        return {"priority": priority_map[predicted_priority]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en la predicción de prioridad: {str(e)}")

@app.get("/")
def root():
    return {"message": "API de planificación quirúrgica en funcionamiento"}