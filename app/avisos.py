# notificaciones web push: el aviso llega al celular aunque la pagina este cerrada
import base64
import json
import logging
import os
import threading

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from .database import BASE_DIR, db, transaccion
from .models import Notificacion, ahora

log = logging.getLogger("ubite.avisos")
CARPETA = os.path.join(BASE_DIR, "instance")
CLAVE_PRIVADA = os.path.join(CARPETA, "vapid_privada.pem")
CONTACTO = os.environ.get("UBITE_CONTACTO", "mailto:cafeteria@ubite.local")


def _claves():
    # las claves VAPID se crean una sola vez y no se suben al repositorio
    if not os.path.exists(CLAVE_PRIVADA):
        os.makedirs(CARPETA, exist_ok=True)
        v = Vapid()
        v.generate_keys()
        v.save_key(CLAVE_PRIVADA)
    return Vapid.from_file(CLAVE_PRIVADA)


def clave_publica():
    publica = _claves().public_key.public_bytes(serialization.Encoding.X962,
                                                serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(publica).rstrip(b"=").decode()


def _enviar(app, id_notificacion, url):
    with app.app_context():
        aviso = db.session.get(Notificacion, id_notificacion)
        pedido = aviso.pedido
        datos = json.dumps({"titulo": f"¡Tu pedido {pedido.codigo} está listo!",
                            "cuerpo": aviso.mensaje, "url": url, "codigo": pedido.codigo})
        try:
            webpush(json.loads(pedido.cliente.suscripcion_push), datos,
                    vapid_private_key=CLAVE_PRIVADA, vapid_claims={"sub": CONTACTO}, timeout=10,
                    ttl=3600, headers={"Urgency": "high"})
            enviado = True
        except (WebPushException, ValueError, KeyError) as e:
            log.warning("no se pudo enviar el aviso de %s: %s", pedido.codigo, e)
            enviado = False
            vencida = isinstance(e, WebPushException) and e.response is not None \
                and e.response.status_code in (404, 410)
        except Exception as e:
            log.warning("error de red enviando el aviso de %s: %s", pedido.codigo, e)
            enviado, vencida = False, False

        with transaccion("resultado_aviso"):
            aviso = db.session.get(Notificacion, id_notificacion)
            aviso.fecha_envio = ahora()
            aviso.estado = "enviada"
            if not enviado:
                # el cliente igual lo ve en la pagina de seguimiento
                aviso.canal = "pagina"
                if vencida:
                    aviso.pedido.cliente.suscripcion_push = None


def enviar_en_segundo_plano(app, id_notificacion, url):
    # la llamada al servicio de push puede tardar, no se hace dentro de la transaccion
    threading.Thread(target=_enviar, args=(app, id_notificacion, url), daemon=True).start()
