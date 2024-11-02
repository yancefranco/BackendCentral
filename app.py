from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sklearn.linear_model import LinearRegression
import numpy as np
import joblib
import os

app = Flask(__name__)

# Configuración de la base de datos MySQL en Railway
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:hTNVEaQnBBWQLUYHDpheXlNLxuwCmScO@autorack.proxy.rlwy.net:54878/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos
db = SQLAlchemy(app)

# Modelo de base de datos para los datos de sensores
class SensorData(db.Model):
    __tablename__ = 'sensores'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(50), nullable=False)
    velocidad = db.Column(db.Integer, nullable=False)
    temperatura = db.Column(db.Integer, nullable=False)
    presion = db.Column(db.Integer, nullable=False)
    combustible = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SensorData {self.device_id}>"

# Crear las tablas en la base de datos
with app.app_context():
    db.create_all()

# Entrenamiento y almacenamiento del modelo de IA para analizar el rendimiento post-carrera
def entrenar_modelo_rendimiento():
    # Datos simulados de entrenamiento: [velocidad, temperatura, presión, combustible]
    X = np.array([
        [150, 90, 32, 60],
        [160, 92, 33, 58],
        [155, 89, 31, 55],
        [165, 95, 30, 50],
        [170, 100, 35, 40]
        # Más datos históricos para mejorar el modelo...
    ])
    
    # Puntuación de rendimiento simulada para cada conjunto de datos
    y = np.array([80, 85, 78, 90, 70])  # Ejemplo de puntuación de rendimiento

    # Crear y entrenar el modelo de regresión
    modelo_rendimiento = LinearRegression()
    modelo_rendimiento.fit(X, y)

    # Guardar el modelo entrenado en un archivo
    joblib.dump(modelo_rendimiento, 'modelo_rendimiento.pkl')

# Entrenar el modelo solo si el archivo no existe
if not os.path.exists('modelo_rendimiento.pkl'):
    entrenar_modelo_rendimiento()

# Endpoint para recibir datos desde el edge
@app.route('/api/v1/recibir_datos', methods=['POST'])
def recibir_datos():
    data = request.json
    if not data or "device_id" not in data:
        return jsonify({"status": "error", "message": "Datos inválidos o faltantes"}), 400

    # Extraer los datos del JSON
    device_id = data.get("device_id")
    velocidad = data.get("velocidad")
    temperatura = data.get("temperatura")
    presion = data.get("presion")
    combustible = data.get("combustible")

    # Crear y guardar registro de sensor en la base de datos
    sensor_data = SensorData(
        device_id=device_id,
        velocidad=velocidad,
        temperatura=temperatura,
        presion=presion,
        combustible=combustible
    )
    db.session.add(sensor_data)
    db.session.commit()
    return jsonify({"status": "success", "message": "Datos recibidos y almacenados"}), 200

# Endpoint para análisis de rendimiento post-carrera
@app.route('/api/v1/analizar_rendimiento_post_carrera', methods=['POST'])
def analizar_rendimiento_post_carrera():
    # Cargar el modelo de IA
    modelo_rendimiento = joblib.load('modelo_rendimiento.pkl')

    # Obtener todos los datos de la carrera más reciente
    datos_carrera = SensorData.query.order_by(SensorData.timestamp.asc()).all()

    # Organizar los datos en el formato necesario para el modelo
    X_carrera = np.array([
        [dato.velocidad, dato.temperatura, dato.presion, dato.combustible] for dato in datos_carrera
    ])

    # Calcular el puntaje de rendimiento para cada punto de la carrera
    puntajes = modelo_rendimiento.predict(X_carrera)
    
    # Calcular el puntaje promedio de rendimiento de la carrera
    puntaje_total = np.mean(puntajes)

    # Devolver el puntaje de rendimiento global y detallado
    return jsonify({"status": "success", "puntaje_rendimiento": puntaje_total, "puntajes_detallados": puntajes.tolist()}), 200

# Endpoint para obtener datos históricos de la carrera para graficar en Flutter
@app.route('/api/v1/datos_historicos', methods=['GET'])
def datos_historicos():
    # Obtener todos los registros de la carrera más reciente
    datos_carrera = SensorData.query.order_by(SensorData.timestamp.asc()).all()
    
    # Organizar datos en listas para cada sensor
    datos = {
        "timestamps": [dato.timestamp.isoformat() for dato in datos_carrera],
        "velocidad": [dato.velocidad for dato in datos_carrera],
        "temperatura": [dato.temperatura for dato in datos_carrera],
        "presion": [dato.presion for dato in datos_carrera],
        "combustible": [dato.combustible for dato in datos_carrera]
    }

    return jsonify(datos), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
