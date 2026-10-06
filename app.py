from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    send_file
)

import socket
import io

from datetime import datetime

from openpyxl import Workbook


app = Flask(__name__)

app.secret_key = "cambia-esta-clave"


TCP_HOST = "127.0.0.1"
TCP_PORT = 5001


# ==========================================
# USUARIO
# ==========================================

USUARIO = "admin"
PASSWORD = "1234"


# ==========================================
# HISTORIAL
# ==========================================

historial = []


# ==========================================
# COMUNICACIÓN TCP
# ==========================================

def tcp_command(command):

    try:

        with socket.create_connection(
            (
                TCP_HOST,
                TCP_PORT
            ),
            timeout=2
        ) as sock:

            sock.sendall(
                (
                    command + "\n"
                ).encode("utf-8")
            )


            return (
                sock.recv(1024)
                .decode("utf-8")
                .strip()
            )


    except Exception as e:

        return (
            f"ERROR,{e}"
        )


# ==========================================
# PÁGINA PRINCIPAL
# ==========================================

@app.route("/")
def index():

    if "usuario" not in session:

        return redirect(
            url_for("login")
        )


    return render_template(
        "index.html",
        usuario=session["usuario"]
    )


# ==========================================
# LOGIN
# ==========================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    error = None


    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )


        if (
            usuario == USUARIO
            and
            password == PASSWORD
        ):

            session["usuario"] = usuario

            return redirect(
                url_for("index")
            )


        error = (
            "Usuario o contraseña "
            "incorrectos."
        )


    return render_template(
        "login.html",
        error=error
    )


# ==========================================
# CERRAR SESIÓN
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ==========================================
# OBTENER RPM
# ==========================================

@app.route("/rpm")
def get_rpm():

    if "usuario" not in session:

        return jsonify({
            "error":
                "No autorizado"
        }), 401


    response = tcp_command(
        "GET"
    )


    if not response.startswith(
        "OK,"
    ):

        return jsonify({
            "error": response
        }), 500


    parts = response.split(",")


    data = {

        "time_ms":
            float(parts[1]),

        "setpoint":
            float(parts[2]),

        "rpm":
            float(parts[3]),

        "pwm":
            float(parts[4]),

        "kp":
            float(parts[5]),

        "ki":
            float(parts[6]),

        "kd":
            float(parts[7])
    }


    historial.append({

        "fecha":
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        **data

    })


    # Máximo de registros
    if len(historial) > 20000:

        del historial[:-20000]


    return jsonify(data)


# ==========================================
# CONTROL DEL MOTOR
# ==========================================

@app.route(
    "/motor",
    methods=["POST"]
)
def motor():

    if "usuario" not in session:

        return jsonify({
            "error":
                "No autorizado"
        }), 401


    data = (
        request
        .get_json(
            silent=True
        )
        or {}
    )


    accion = data.get(
        "accion"
    )


    # --------------------------------------
    # SET RPM
    # --------------------------------------

    if accion == "set":

        rpm = float(
            data.get(
                "rpm",
                0
            )
        )


        rpm = max(
            0,
            min(350, rpm)
        )


        respuesta = tcp_command(
            f"SET {rpm}"
        )


    # --------------------------------------
    # START
    # --------------------------------------

    elif accion == "start":

        respuesta = tcp_command(
            "START"
        )


    # --------------------------------------
    # STOP
    # --------------------------------------

    elif accion == "stop":

        respuesta = tcp_command(
            "STOP"
        )


    else:

        return jsonify({
            "error":
                "Acción no válida"
        }), 400


    return jsonify({
        "respuesta":
            respuesta
    })


# ==========================================
# ACTUALIZAR PID
# ==========================================

@app.route(
    "/pid",
    methods=["POST"]
)
def pid():

    if "usuario" not in session:

        return jsonify({
            "error":
                "No autorizado"
        }), 401


    data = (
        request
        .get_json(
            silent=True
        )
        or {}
    )


    try:

        kp = float(
            data.get("kp")
        )

        ki = float(
            data.get("ki")
        )

        kd = float(
            data.get("kd")
        )


        if (
            kp < 0
            or ki < 0
            or kd < 0
        ):

            raise ValueError


        respuesta = tcp_command(
            f"PID {kp} {ki} {kd}"
        )


        return jsonify({
            "respuesta":
                respuesta
        })


    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "error":
                "Valores PID no válidos"
        }), 400


# ==========================================
# EXPORTAR EXCEL
# ==========================================

@app.route("/exportar")
def exportar():

    if "usuario" not in session:

        return redirect(
            url_for("login")
        )


    wb = Workbook()


    ws = wb.active

    ws.title = "Datos PID"


    # Encabezados
    ws.append([

        "Fecha",

        "Tiempo Arduino (ms)",

        "Setpoint (RPM)",

        "Velocidad (RPM)",

        "PWM",

        "Kp",

        "Ki",

        "Kd"

    ])


    # Datos
    for dato in historial:

        ws.append([

            dato["fecha"],

            dato["time_ms"],

            dato["setpoint"],

            dato["rpm"],

            dato["pwm"],

            dato["kp"],

            dato["ki"],

            dato["kd"]

        ])


    # Ancho de columnas
    anchos = [
        22,
        20,
        18,
        18,
        12,
        12,
        12,
        12
    ]


    for i, ancho in enumerate(
        anchos,
        1
    ):

        ws.column_dimensions[
            chr(64 + i)
        ].width = ancho


    # Crear archivo en memoria
    salida = io.BytesIO()

    wb.save(salida)

    salida.seek(0)


    return send_file(

        salida,

        as_attachment=True,

        download_name=
            "datos_pid_motor.xlsx",

        mimetype=
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    )


# ==========================================
# EJECUTAR
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )

