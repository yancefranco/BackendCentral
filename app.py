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

# Tabla para los datos de rendimiento post-carrera
class RendimientoSensores(db.Model):
    __tablename__ = 'rendimiento_sensores'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(50), nullable=False)
    velocidad = db.Column(db.Integer, nullable=False)
    temperatura = db.Column(db.Integer, nullable=False)
    presion = db.Column(db.Integer, nullable=False)
    combustible = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<RendimientoSensores {self.device_id}>"

# Crear las tablas en la base de datos
with app.app_context():
    db.create_all()

# Función para entrenar el modelo de rendimiento y escalar los datos
def entrenar_modelo_rendimiento():
    # Datos de entrenamiento simulados: [velocidad, temperatura, presión, combustible]
    X = np.array([
        [150, 90, 32, 60],
        [160, 92, 33, 58],
        [155, 89, 31, 55],
        [165, 95, 30, 50],
        [170, 100, 35, 40]
    ])
    
    # Puntuación de rendimiento simulada
    y = np.array([80, 85, 78, 90, 70])

    # Escalar los datos
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Entrenar el modelo de regresión lineal
    modelo_rendimiento = LinearRegression()
    modelo_rendimiento.fit(X_scaled, y)

    # Guardar el modelo y el escalador en archivos
    joblib.dump(modelo_rendimiento, 'modelo_rendimiento.pkl')
    joblib.dump(scaler, 'scaler.pkl')

# Entrenar el modelo si no está ya guardado
if not os.path.exists('modelo_rendimiento.pkl') or not os.path.exists('scaler.pkl'):
    entrenar_modelo_rendimiento()

# Endpoint para recibir datos y guardarlos en ambas tablas
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

    # Guardar en la tabla de datos históricos
    historico = HistoricoSensores(
        device_id=device_id,
        velocidad=velocidad,
        temperatura=temperatura,
        presion=presion,
        combustible=combustible
    )
    db.session.add(historico)

    # Guardar en la tabla de rendimiento
    rendimiento = RendimientoSensores(
        device_id=device_id,
        velocidad=velocidad,
        temperatura=temperatura,
        presion=presion,
        combustible=combustible
    )
    db.session.add(rendimiento)

    # Guardar los cambios en la base de datos
    db.session.commit()
    return jsonify({"status": "success", "message": "Datos recibidos y almacenados en ambas tablas"}), 200

# Endpoint para análisis de rendimiento post-carrera filtrado por device_id
@app.route('/api/v1/analizar_rendimiento_post_carrera', methods=['POST'])
def analizar_rendimiento_post_carrera():
    device_id = request.json.get("device_id")
    if not device_id:
        return jsonify({"status": "error", "message": "Se requiere device_id"}), 400

    # Cargar el modelo y el escalador
    modelo_rendimiento = joblib.load('modelo_rendimiento.pkl')
    scaler = joblib.load('scaler.pkl')

    # Obtener datos del dispositivo específico de la tabla de rendimiento
    datos_carrera = RendimientoSensores.query.filter_by(device_id=device_id).order_by(RendimientoSensores.timestamp.asc()).all()
    if not datos_carrera:
        return jsonify({"status": "error", "message": "No hay datos para el dispositivo"}), 404

    # Organizar los datos en el formato necesario para el modelo
    X_carrera = np.array([
        [dato.velocidad, dato.temperatura, dato.presion, dato.combustible] for dato in datos_carrera
    ])

    # Escalar los datos antes de predecir
    X_carrera_scaled = scaler.transform(X_carrera)
    puntajes = modelo_rendimiento.predict(X_carrera_scaled)
    
    # Calcular el puntaje promedio de rendimiento de la carrera
    puntaje_total = np.mean(puntajes)

    # Devolver el puntaje de rendimiento global y detallado
    return jsonify({"status": "success", "puntaje_rendimiento": puntaje_total, "puntajes_detallados": puntajes.tolist()}), 200

# Endpoint para obtener datos históricos filtrados por device_id
@app.route('/api/v1/datos_historicos', methods=['GET'])
def datos_historicos():
    device_id = request.args.get("device_id")
    if not device_id:
        return jsonify({"status": "error", "message": "Se requiere device_id"}), 400

    # Obtener registros del dispositivo específico de la tabla de datos históricos
    datos_carrera = HistoricoSensores.query.filter_by(device_id=device_id).order_by(HistoricoSensores.timestamp.asc()).all()
    if not datos_carrera:
        return jsonify({"status": "error", "message": "No hay datos para el dispositivo"}), 404

    # Organizar datos en listas para cada sensor
    datos = {
        "timestamps": [dato.timestamp.isoformat() for dato in datos_carrera],
        "velocidad": [dato.velocidad for dato in datos_carrera],
        "temperatura": [dato.temperatura for dato in datos_carrera],
        "presion": [dato.presion for dato in datos_carrera],
        "combustible": [dato.combustible for dato in datos_carrera]
    }

    return jsonify(datos), 200

# Función para eliminar registros antiguos
def limpiar_datos_antiguos():
    limite = datetime.utcnow() - timedelta(days=1)
    HistoricoSensores.query.filter(HistoricoSensores.timestamp < limite).delete()
    RendimientoSensores.query.filter(RendimientoSensores.timestamp < limite).delete()
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
