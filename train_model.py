import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib

# Generar datos simulados
np.random.seed(42)
data = {
    "urgency": np.random.randint(0, 6, 1000),
    "time_since_injury": np.random.randint(0, 5, 1000),
    "functional_impact": np.random.randint(0, 4, 1000),
    "patient_condition": np.random.randint(0, 3, 1000),
    "medication": np.random.choice(["Ninguna", "Antiagregante", "Anticoagulante"], 1000),
    "delay_days": np.random.randint(0, 7, 1000),
    "surgery_type": np.random.choice(["Fractura Cerrada", "Fractura Cadera", "Otra Cirugía"], 1000),
    "priority": np.random.choice(["Alta", "Media", "Baja"], 1000),
    "operating_room": np.random.choice(["Mañana", "Tarde", "Reprogramar"], 1000)
}

df = pd.DataFrame(data)

# Mapear variables categóricas a valores numéricos
df["medication"] = df["medication"].map({"Ninguna": 0, "Antiagregante": 1, "Anticoagulante": 2})
df["priority"] = df["priority"].map({"Alta": 2, "Media": 1, "Baja": 0})
df["operating_room"] = df["operating_room"].map({"Mañana": 2, "Tarde": 1, "Reprogramar": 0})
df["surgery_type"] = df["surgery_type"].map({"Fractura Cerrada": 2, "Fractura Cadera": 1, "Otra Cirugía": 0})

# Dividir en características (X) y etiquetas (y)
X = df.drop(columns=["operating_room"])
y = df["operating_room"]

# Separar datos en entrenamiento y prueba
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Entrenar modelo de Machine Learning
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Guardar el modelo entrenado en la ruta correcta
model_path = os.path.join(os.path.dirname(__file__), "prioritization_model.pkl")
joblib.dump(model, model_path)

print("Modelo de planificación quirúrgica entrenado y guardado con éxito en", model_path)
