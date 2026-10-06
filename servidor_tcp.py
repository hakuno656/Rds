#!/usr/bin/env python3

import socket
import threading
import time
import serial


SERIAL_PORT = "/dev/ttyACM0"
BAUDRATE = 9600

TCP_HOST = "127.0.0.1"
TCP_PORT = 5001


latest = {
    "time_ms": 0,
    "setpoint": 0.0,
    "rpm": 0.0,
    "pwm": 0.0,
    "kp": 1.16,
    "ki": 0.75,
    "kd": 0.0001
}


lock = threading.Lock()


# ==========================================
# LEER DATOS DEL ARDUINO
# ==========================================

def serial_reader(ser):

    global latest

    while True:

        try:

            line = (
                ser.readline()
                .decode(
                    "utf-8",
                    errors="ignore"
                )
                .strip()
            )

            if not line:
                continue


            if line.startswith("DATA,"):

                parts = line.split(",")


                if len(parts) >= 8:

                    with lock:

                        latest = {
                            "time_ms":
                                int(float(parts[1])),

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


            else:

                print(
                    "[Arduino]",
                    line
                )


        except serial.SerialException as e:

            print(
                "Error de comunicación:",
                e
            )

            time.sleep(1)


        except Exception as e:

            print(
                "Error:",
                e
            )


# ==========================================
# ENVIAR COMANDO AL ARDUINO
# ==========================================

def send_command(
    ser,
    command
):

    command = (
        command.strip()
        + "\n"
    )

    ser.write(
        command.encode("utf-8")
    )

    ser.flush()


# ==========================================
# CLIENTE TCP
# ==========================================

def client_handler(
    conn,
    addr,
    ser
):

    try:

        data = (
            conn.recv(1024)
            .decode("utf-8")
            .strip()
        )


        if not data:
            return


        # Solicitar datos
        if data == "GET":

            with lock:

                response = (
                    f"OK,"
                    f"{latest['time_ms']},"
                    f"{latest['setpoint']},"
                    f"{latest['rpm']},"
                    f"{latest['pwm']},"
                    f"{latest['kp']},"
                    f"{latest['ki']},"
                    f"{latest['kd']}\n"
                )

            conn.sendall(
                response.encode(
                    "utf-8"
                )
            )

            return


        # Velocidad
        if data.startswith("SET "):

            send_command(
                ser,
                data
            )

            conn.sendall(
                b"OK\n"
            )

            return


        # Arrancar
        if data == "START":

            send_command(
                ser,
                data
            )

            conn.sendall(
                b"OK\n"
            )

            return


        # Detener
        if data == "STOP":

            send_command(
                ser,
                data
            )

            conn.sendall(
                b"OK\n"
            )

            return


        # PID
        if data.startswith("PID "):

            send_command(
                ser,
                data
            )

            conn.sendall(
                b"OK\n"
            )

            return


        conn.sendall(
            b"ERROR,comando no reconocido\n"
        )


    except Exception as e:

        print(
            "Cliente:",
            e
        )


    finally:

        conn.close()


# ==========================================
# SERVIDOR
# ==========================================

def main():

    print(
        "Abriendo Arduino en",
        SERIAL_PORT
    )


    ser = serial.Serial(
        SERIAL_PORT,
        BAUDRATE,
        timeout=1
    )


    time.sleep(2)

    ser.reset_input_buffer()


    hilo_serial = threading.Thread(
        target=serial_reader,
        args=(ser,),
        daemon=True
    )

    hilo_serial.start()


    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )


    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )


    server.bind(
        (
            TCP_HOST,
            TCP_PORT
        )
    )


    server.listen(10)


    print(
        f"Servidor TCP activo en "
        f"{TCP_HOST}:{TCP_PORT}"
    )

    print(
        "Esperando conexiones..."
    )


    try:

        while True:

            conn, addr = (
                server.accept()
            )


            hilo = threading.Thread(
                target=client_handler,
                args=(
                    conn,
                    addr,
                    ser
                ),
                daemon=True
            )

            hilo.start()


    except KeyboardInterrupt:

        print(
            "\nServidor detenido."
        )


    finally:

        server.close()
        ser.close()


if __name__ == "__main__":
    main()
