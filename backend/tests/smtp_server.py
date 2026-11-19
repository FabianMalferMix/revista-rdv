"""Un servidor SMTP de mentira, para probar el correo con lo que contesta el servidor.

Escucha en un puerto libre de 127.0.0.1 y habla SMTP con el backend de Django por un socket de
verdad: la prueba no elige la excepción, elige la respuesta, y la excepción la decide smtplib,
como en producción. Cada envío abre una sesión nueva. `script` dice lo que contesta un paso de
la sesión: una cadena, en todas las sesiones; una lista, una respuesta por sesión, hasta que se
acaba. Un paso sin nada escrito sale bien. `unfinished` cuenta las sesiones que no terminaron:
las que el cliente no cerró con QUIT, salvo si el servidor colgó tras rechazar el saludo. Lo pide
la fixture `smtp_server` (backend/conftest.py).
"""

import socketserver
import threading

# Lo que contesta cada paso cuando sale bien. El saludo de EHLO ofrece AUTH PLAIN, que es lo
# que usa smtplib para iniciar sesión, y nada más: ni STARTTLS ni SMTPUTF8.
ACCEPT = {
    "greeting": "220 localhost ESMTP",
    "EHLO": "250-localhost\r\n250 AUTH PLAIN",
    "HELO": "250 localhost",
    "AUTH": "235 2.7.0 Authentication successful",
    "MAIL": "250 2.1.0 OK",
    "RCPT": "250 2.1.5 OK",
    "DATA": "250 2.0.0 OK: queued",
}


class _Session(socketserver.StreamRequestHandler):
    def handle(self):
        server = self.server
        with server.lock:
            server.sessions += 1
            server.unfinished += 1
            replies = {}
            for step, script in server.script.items():
                if isinstance(script, str):
                    replies[step] = script
                elif script:
                    replies[step] = script.pop(0)
        if "EHLO" in replies:
            # Si el servidor no acepta EHLO, smtplib prueba con HELO: el rechazo vale para los dos.
            replies.setdefault("HELO", replies["EHLO"])
        reply = {**ACCEPT, **replies}
        if not reply["greeting"].startswith("220"):
            self.finish_session()
            self.send(reply["greeting"])
            return  # saluda con un rechazo y cuelga
        self.send(reply["greeting"])
        message = None
        for raw in self.rfile:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if message is not None:  # el mensaje, hasta la línea con un punto
                if line != ".":
                    message.append(line)
                    continue
                if reply["DATA"].startswith("250"):
                    server.messages.append("\n".join(message))
                self.send(reply["DATA"])  # después de guardarlo: la prueba lo lee al acabar
                message = None
                continue
            verb, _, argument = line.partition(" ")
            verb = verb.upper()
            if verb == "RCPT":
                server.recipients.append(argument[argument.index("<") + 1 : argument.index(">")])
            if verb == "DATA":
                self.send("354 End data with <CR><LF>.<CR><LF>")
                message = []
            elif verb == "QUIT":
                self.finish_session()
                self.send("221 2.0.0 Bye")
                return
            else:
                self.send(reply.get(verb, "250 2.0.0 OK"))

    def finish_session(self):
        """Da la sesión por terminada antes de la última respuesta: el cliente la espera, así
        que, cuando la prueba mira, la cuenta ya está al día."""
        with self.server.lock:
            self.server.unfinished -= 1

    def send(self, line):
        self.wfile.write(f"{line}\r\n".encode())


class SMTPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Session)
        self.lock = threading.Lock()
        self.script = {}  # paso → su respuesta, o las de las próximas sesiones
        self.sessions = 0  # las conexiones que recibió
        self.unfinished = 0  # las que no terminaron con QUIT ni con el saludo rechazado
        self.recipients = []  # la dirección de cada RCPT, aceptada o no
        self.messages = []  # los mensajes que aceptó, enteros
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def stop(self):
        self.shutdown()
        self.server_close()
