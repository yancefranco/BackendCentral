from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import mysql.connector
from mysql.connector import Error
import numpy as np
import joblib
import os

app = Flask(__name__)

# Configuración de la base de datos MySQL
DATABASE_CONFIG = {
    'host': 'autorack.proxy.rlwy.net',
    'port': '54878',
    'user': 'root',
    'password': 'hTNVEaQnBBWQLUYHDpheXlNLxuwCmScO',
    'database': 'railway'
}

# Función para conectar a la base de datos
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        return conn
    except Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

# Función para crear las tablas si no existen
def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Tabla usuarios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario VARCHAR(50) UNIQUE NOT NULL,
                    contraseña VARCHAR(255) NOT NULL,
                    nombres VARCHAR(100),
                    apellidos VARCHAR(100),
                    correo VARCHAR(100) UNIQUE,
                    rol ENUM('técnico', 'piloto') NOT NULL
                )
            ''')
            # Tabla historico_sensores
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historico_sensores (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(50) NOT NULL,
                    velocidad INT NOT NULL,
                    temperatura INT NOT NULL,
                    presion INT NOT NULL,
                    combustible INT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Tabla iot_devices
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS iot_devices (
                    device_id VARCHAR(50) PRIMARY KEY,
                    velocidad INT,
                    temperatura INT,
                    presion INT,
                    combustible INT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            # Tabla rendimiento_sensores
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rendimiento_sensores (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(50) NOT NULL,
                    velocidad INT NOT NULL,
                    temperatura INT NOT NULL,
                    presion INT NOT NULL,
                    combustible INT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

             # Tabla intermedia usuario_dispositivos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usuario_dispositivos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NOT NULL,
                    device_id VARCHAR(50) NOT NULL,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                    FOREIGN KEY (device_id) REFERENCES iot_devices(device_id),
                    UNIQUE (usuario_id, device_id) -- Evita duplicados
                )
            ''')
            # Tabla membresias
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS membresias (
                id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT NOT NULL,
        tipo ENUM('premium') NOT NULL DEFAULT 'premium',
        numero_tarjeta VARCHAR(16) NOT NULL,
        fecha_vencimiento DATE NOT NULL,
        cvv VARCHAR(3) NOT NULL,
        nombre_titular VARCHAR(255) NOT NULL,
        fecha_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_fin DATETIME NOT NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        UNIQUE (usuario_id)
                )
            ''')
            

            conn.commit()
            print("Tablas creadas o ya existentes.")
        except Error as e:
            print(f"Error al crear las tablas: {e}")
        finally:
            cursor.close()
            conn.close()

# Inicializar la base de datos
init_db()

# Función para entrenar el modelo de rendimiento
def entrenar_modelo_rendimiento():
    X = np.array([
        [150, 90, 32, 60],
        [160, 92, 33, 58],
        [155, 89, 31, 55],
        [165, 95, 30, 50],
        [170, 100, 35, 40]
    ])
    y = np.array([80, 85, 78, 90, 70])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    modelo_rendimiento = LinearRegression()
    modelo_rendimiento.fit(X_scaled, y)

    joblib.dump(modelo_rendimiento, 'modelo_rendimiento.pkl')
    joblib.dump(scaler, 'scaler.pkl')

if not os.path.exists('modelo_rendimiento.pkl') or not os.path.exists('scaler.pkl'):
    entrenar_modelo_rendimiento()


@app.route('/api/v1/crear_membresia', methods=['POST'])
def crear_membresia():
    from datetime import datetime, timedelta
    data = request.json
    usuario_id = data.get("usuario_id")
    tipo = data.get("tipo", "premium")  # Valor por defecto: 'premium'
    numero_tarjeta = data.get("numero_tarjeta")
    fecha_vencimiento = data.get("fecha_vencimiento")  # Formato: MM/YY
    cvv = data.get("cvv")
    nombre_titular = data.get("nombre_titular")  # Nombre del dueño de la tarjeta

    # Validar datos requeridos
    if not (usuario_id and tipo and numero_tarjeta and fecha_vencimiento and cvv and nombre_titular):
        return jsonify({"error": "Datos incompletos"}), 400

    # Validar tipo de membresía (solo 'premium')
    if tipo != 'premium':
        return jsonify({"error": "Tipo de membresía no válido"}), 400

    # Validar formato de tarjeta y CVV
    if not (len(numero_tarjeta) == 16 and numero_tarjeta.isdigit()):
        return jsonify({"error": "Número de tarjeta no válido"}), 400
    if not (len(cvv) == 3 and cvv.isdigit()):
        return jsonify({"error": "CVV no válido"}), 400

    # Validar fecha de vencimiento en formato MM/YY
    try:
        mes, año = map(int, fecha_vencimiento.split("/"))
        fecha_vencimiento_obj = datetime(year=2000 + año, month=mes, day=1)
        if fecha_vencimiento_obj < datetime.now():
            return jsonify({"error": "La tarjeta está vencida"}), 400
    except (ValueError, IndexError):
        return jsonify({"error": "Formato de fecha de vencimiento no válido. Use MM/YY"}), 400

    # Validar nombre del titular
    if not isinstance(nombre_titular, str) or len(nombre_titular.strip()) == 0:
        return jsonify({"error": "El nombre del titular de la tarjeta es inválido"}), 400

    # Calcular fechas de suscripción
    fecha_inicio = datetime.now()
    fecha_fin = fecha_inicio + timedelta(days=30)  # Suscripción de 1 mes

    # Insertar membresía en la base de datos
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO membresias (usuario_id, tipo, numero_tarjeta, fecha_vencimiento, cvv, nombre_titular, fecha_inicio, fecha_fin)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (usuario_id, tipo, numero_tarjeta, fecha_vencimiento_obj.date(), cvv, nombre_titular, fecha_inicio, fecha_fin))
            conn.commit()
            return jsonify({
                "message": "Membresía premium creada exitosamente",
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin
            }), 201
        except mysql.connector.IntegrityError:
            return jsonify({"error": "El usuario ya tiene una membresía activa"}), 400
        except Error as e:
            print(f"Error al crear membresía: {e}")
            return jsonify({"error": "Error al crear la membresía"}), 500
        finally:
            cursor.close()
            conn.close()
    else:
        return jsonify({"error": "Error de conexión con la base de datos"}), 500
    
import logging

logging.basicConfig(filename='app.log', filemode='a', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@app.route('/api/v1/verificar_membresia/<int:usuario_id>', methods=['GET'])
def verificar_membresia(usuario_id):
    logging.info(f'Inicio de verificación de membresía para el usuario {usuario_id}')
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            logging.info('Consulta a la base de datos para verificar membresía')
            cursor.execute("""
                SELECT tipo, fecha_inicio, fecha_fin, nombre_titular
                FROM membresias
                WHERE usuario_id = %s AND fecha_fin > NOW()
            """, (usuario_id,))
            membresia = cursor.fetchone()

            if membresia:
                logging.info('Membresía activa encontrada')
                return jsonify({
                    "message": "El usuario tiene una membresía activa",
                    "membresia": membresia
                }), 200
            else:
                logging.info('No se encontró membresía activa')
                return jsonify({
                    "message": "El usuario no tiene una membresía activa"
                }), 404
        except Error as e:
            logging.error(f'Error al verificar membresía: {e}')
            return jsonify({"error": "Error al verificar la membresía"}), 500
        finally:
            cursor.close()
            conn.close()
    else:
        logging.error('Error de conexión con la base de datos')
        return jsonify({"error": "Error de conexión con la base de datos"}), 500
# Ruta para registrar un usuario
@app.route('/registrarte', methods=['POST'])
def registrarte():
    data = request.json
    usuario = data.get('usuario')
    contraseña = generate_password_hash(data.get('contraseña'))  # Encriptar la contraseña
    nombres = data.get('nombres')
    apellidos = data.get('apellidos')
    correo = data.get('correo')
    rol = data.get('rol')

    if rol not in ['técnico', 'piloto']:
        return jsonify({"error": "El rol debe ser 'técnico' o 'piloto'"}), 400

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO usuarios (usuario, contraseña, nombres, apellidos, correo, rol)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (usuario, contraseña, nombres, apellidos, correo, rol))
            conn.commit()
            return jsonify({"mensaje": "Usuario registrado exitosamente"}), 201
        except mysql.connector.IntegrityError:
            conn.rollback()
            return jsonify({"error": "El usuario o correo ya existe"}), 400
        finally:
            cursor.close()
            conn.close()
    else:
        return jsonify({"error": "Error de conexión con la base de datos"}), 500



# Ruta para iniciar sesión
@app.route('/iniciar_sesion', methods=['POST'])
def iniciar_sesion():
    data = request.json
    usuario = data.get('usuario')
    contraseña = data.get('contraseña')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM usuarios WHERE usuario = %s', (usuario,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['contraseña'], contraseña):
            return jsonify({
                "mensaje": "Inicio de sesión exitoso",
                "rol": user['rol'],
                "usuarioId": user['id']  # Asegúrate de que 'id' es el nombre correcto del campo en tu base de datos
            }), 200
        else:
            return jsonify({"error": "Usuario o contraseña incorrectos"}), 401
    else:
        return jsonify({"error": "Error de conexión con la base de datos"}), 500

# Ruta para obtener el perfil del usuario utilizando el ID
@app.route('/perfil/<int:id>', methods=['GET'])
def perfil(id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Consulta al usuario por su ID
            cursor.execute('''
                SELECT id, usuario, nombres, apellidos, correo, rol 
                FROM usuarios 
                WHERE id = %s
            ''', (id,))
            user = cursor.fetchone()

            if user:
                return jsonify(user), 200
            else:
                return jsonify({"error": "Usuario no encontrado"}), 404
        except Error as e:
            print(f"Error al ejecutar la consulta: {e}")
            return jsonify({"error": "Error al obtener el perfil del usuario"}), 500
        finally:
            cursor.close()
            conn.close()
    else:
        return jsonify({"error": "Error de conexión con la base de datos"}), 500


# Endpoint para asociar un dispositivo a un usuario
@app.route('/api/v1/asociar_dispositivo', methods=['POST'])
def asociar_dispositivo():
    data = request.json
    usuario_id = data.get("usuario_id")
    device_id = data.get("device_id")

    if not usuario_id or not device_id:
        return jsonify({"error": "Datos incompletos"}), 400

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO usuario_dispositivos (usuario_id, device_id)
                VALUES (%s, %s)
            """, (usuario_id, device_id))
            conn.commit()
            return jsonify({"message": "Dispositivo asociado exitosamente"}), 201
        except mysql.connector.IntegrityError:
            return jsonify({"error": "El dispositivo ya está asociado al usuario"}), 400
        except Error as e:
            print(f"Error al asociar dispositivo: {e}")
            return jsonify({"error": "Error al asociar el dispositivo"}), 500
        finally:
            cursor.close()
            conn.close()
    else:
        return jsonify({"error": "Error de conexión con la base de datos"}), 500

# Endpoint para obtener dispositivos asociados a un usuario
@app.route('/api/v1/usuario/<int:usuario_id>/dispositivos', methods=['GET'])
def obtener_dispositivos_usuario(usuario_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT d.device_id, d.velocidad, d.temperatura, d.presion, d.combustible, d.timestamp
                FROM iot_devices d
                INNER JOIN usuario_dispositivos ud ON d.device_id = ud.device_id
                WHERE ud.usuario_id = %s
            """, (usuario_id,))
            dispositivos = cursor.fetchall()
            return jsonify({"status": "success", "dispositivos": dispositivos}), 200
        except Error as e:
            print(f"Error al obtener dispositivos: {e}")
            return jsonify({"error": "Error al obtener dispositivos"}), 500
        finally:
            cursor.close()
            conn.close()
    else:
        return jsonify({"error": "Error de conexión con la base de datos"}), 500
   

@app.route('/api/v1/recibir_datos', methods=['POST'])
def recibir_datos():
    data = request.json
    if not data or "device_id" not in data:
        return jsonify({"status": "error", "message": "Datos inválidos o faltantes"}), 400

    device_id = data.get("device_id")
    velocidad = data.get("velocidad")
    temperatura = data.get("temperatura")
    presion = data.get("presion")
    combustible = data.get("combustible")
    timestamp = datetime.utcnow()

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO historico_sensores (device_id, velocidad, temperatura, presion, combustible, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (device_id, velocidad, temperatura, presion, combustible, timestamp))
            cursor.execute("""
                INSERT INTO rendimiento_sensores (device_id, velocidad, temperatura, presion, combustible, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (device_id, velocidad, temperatura, presion, combustible, timestamp))
            cursor.execute("""
                INSERT INTO iot_devices (device_id, velocidad, temperatura, presion, combustible, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE velocidad=%s, temperatura=%s, presion=%s, combustible=%s, timestamp=%s
            """, (device_id, velocidad, temperatura, presion, combustible, timestamp,
                  velocidad, temperatura, presion, combustible, timestamp))
            conn.commit()
        except Error as e:
            print(f"Error al ejecutar la consulta: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    return jsonify({"status": "success", "message": "Datos recibidos y almacenados correctamente"}), 200

@app.route('/api/v1/dispositivos', methods=['GET'])
def obtener_dispositivos():
    conn = get_db_connection()
    dispositivos = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM iot_devices")
            dispositivos = cursor.fetchall()
        except Error as e:
            print(f"Error al ejecutar la consulta: {e}")
        finally:
            cursor.close()
            conn.close()

    return jsonify({"status": "success", "data": dispositivos}), 200

@app.route('/api/v1/analizar_rendimiento_post_carrera', methods=['POST'])
def analizar_rendimiento_post_carrera():
    device_id = request.json.get("device_id")
    if not device_id:
        return jsonify({"status": "error", "message": "Se requiere device_id"}), 400

    modelo_rendimiento = joblib.load('modelo_rendimiento.pkl')
    scaler = joblib.load('scaler.pkl')

    conn = get_db_connection()
    datos_carrera = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT velocidad, temperatura, presion, combustible
                FROM rendimiento_sensores
                WHERE device_id = %s
                ORDER BY timestamp ASC
            """, (device_id,))
            datos_carrera = cursor.fetchall()
        except Error as e:
            print(f"Error al ejecutar la consulta: {e}")
        finally:
            cursor.close()
            conn.close()

    if not datos_carrera:
        return jsonify({"status": "error", "message": "No hay datos para el dispositivo"}), 404

    X_carrera = np.array([[d['velocidad'], d['temperatura'], d['presion'], d['combustible']] for d in datos_carrera])
    X_carrera_scaled = scaler.transform(X_carrera)
    puntajes = modelo_rendimiento.predict(X_carrera_scaled)
    puntaje_total = np.mean(puntajes)

    return jsonify({"status": "success", "puntaje_rendimiento": puntaje_total, "puntajes_detallados": puntajes.tolist()}), 200

@app.route('/api/v1/datos_historicos', methods=['GET'])
def datos_historicos():
    device_id = request.args.get("device_id")
    if not device_id:
        return jsonify({"status": "error", "message": "Se requiere device_id"}), 400

    conn = get_db_connection()
    datos_carrera = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT velocidad, temperatura, presion, combustible, timestamp
                FROM historico_sensores
                WHERE device_id = %s
                ORDER BY timestamp ASC
            """, (device_id,))
            datos_carrera = cursor.fetchall()
        except Error as e:
            print(f"Error al ejecutar la consulta: {e}")
        finally:
            cursor.close()
            conn.close()

    return jsonify({"status": "success", "data": datos_carrera}), 200

# Scheduler para limpiar datos antiguos
def limpiar_datos_antiguos():
    limite = datetime.utcnow() - timedelta(days=1)
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM historico_sensores WHERE timestamp < %s", (limite,))
            cursor.execute("DELETE FROM rendimiento_sensores WHERE timestamp < %s", (limite,))
            conn.commit()
            print("Datos antiguos eliminados correctamente.")
        except Error as e:
            print(f"Error al eliminar datos antiguos: {e}")
        finally:
            cursor.close()
            conn.close()
    else:
        print("Error al conectar con la base de datos para eliminar datos antiguos.")

scheduler = BackgroundScheduler()
try:
    scheduler.add_job(func=limpiar_datos_antiguos, trigger="interval", hours=24)
    scheduler.start()
    print("Scheduler iniciado correctamente.")
except Exception as e:
    print(f"Error al iniciar el scheduler: {e}")

@app.teardown_appcontext
def shutdown_session(exception=None):
    try:
        if scheduler.running:
            scheduler.shutdown()
            print("Scheduler detenido correctamente.")
        else:
            print("Scheduler ya estaba detenido.")
    except Exception as e:
        print(f"Error al intentar cerrar el scheduler: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
