from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import numpy as np
import joblib
import os

app = Flask(__name__)

# Configuración de la base de datos MySQL en Railway
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:hTNVEaQnBBWQLUYHDpheXlNLxuwCmScO@autorack.proxy.rlwy.net:54878/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos
db = SQLAlchemy(app)

# Tabla para los datos históricos de los sensores
class HistoricoSensores(db.Model):
    __tablename__ = 'historico_sensores'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(50), nullable=False)
    velocidad = db.Column(db.Integer, nullable=False)
    temperatura = db.Column(db.Integer, nullable=False)
    presion = db.Column(db.Integer, nullable=False)
    combustible = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<HistoricoSensores {self.device_id}>"

# Tabla para los dispositivos IoT
class IoTDevice(db.Model):
    __tablename__ = 'iot_devices'
    device_id = db.Column(db.String(50), primary_key=True)
    velocidad = db.Column(db.Integer, nullable=True)
    temperatura = db.Column(db.Integer, nullable=True)
    presion = db.Column(db.Integer, nullable=True)
    combustible = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<IoTDevice {self.device_id}>"

# Crear las tablas en la base de datos
with app.app_context():
    db.create_all()

# Endpoint para actualizar dispositivos IoT
@app.route('/api/v1/actualizar_dispositivo', methods=['POST'])
def actualizar_dispositivo():
    data = request.json
    if not data or "device_id" not in data:
        return jsonify({"status": "error", "message": "Datos inválidos o faltantes"}), 400

    # Extraer los datos
    device_id = data.get("device_id")
    velocidad = data.get("velocidad")
    temperatura = data.get("temperatura")
    presion = data.get("presion")
    combustible = data.get("combustible")

    # Buscar si el dispositivo ya existe
    dispositivo = IoTDevice.query.get(device_id)

    if dispositivo:
        # Actualizar los datos del dispositivo existente
        dispositivo.velocidad = velocidad
        dispositivo.temperatura = temperatura
        dispositivo.presion = presion
        dispositivo.combustible = combustible
        dispositivo.timestamp = datetime.utcnow()
    else:
        # Crear un nuevo registro para el dispositivo
        dispositivo = IoTDevice(
            device_id=device_id,
            velocidad=velocidad,
            temperatura=temperatura,
            presion=presion,
            combustible=combustible
        )
        db.session.add(dispositivo)

    db.session.commit()
    return jsonify({"status": "success", "message": "Dispositivo actualizado correctamente", "device_id": device_id}), 200

# Endpoint para consultar dispositivos IoT
@app.route('/api/v1/dispositivos', methods=['GET'])
def obtener_dispositivos():
    dispositivos = IoTDevice.query.all()
    resultado = [
        {
            "device_id": dispositivo.device_id,
            "velocidad": dispositivo.velocidad,
            "temperatura": dispositivo.temperatura,
            "presion": dispositivo.presion,
            "combustible": dispositivo.combustible,
            "timestamp": dispositivo.timestamp.isoformat()
        } for dispositivo in dispositivos
    ]
    return jsonify({"status": "success", "data": resultado}), 200

# Función para eliminar registros antiguos
def limpiar_datos_antiguos():
    limite = datetime.utcnow() - timedelta(days=1)
    HistoricoSensores.query.filter(HistoricoSensores.timestamp < limite).delete()
    db.session.commit()
    print("Registros antiguos eliminados")

# Configuración de un trabajo programado para ejecutar cada 24 horas
scheduler = BackgroundScheduler()
scheduler.add_job(func=limpiar_datos_antiguos, trigger="interval", hours=24)
scheduler.start()

# Cerrar el scheduler al terminar la aplicación
@app.teardown_appcontext
def shutdown_session(exception=None):
    scheduler.shutdown()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

