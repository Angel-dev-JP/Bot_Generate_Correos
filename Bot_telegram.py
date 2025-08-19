# bot_mail_tm.py
import os
import json
import random
from config import TOKEN, API_BASE, DATA_FILE
import logging
import requests
import secrets
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes
)


logging.basicConfig(level=logging.INFO)

# ================== PERSISTENCIA ==================
def _migrar_estructura(data: dict) -> dict:
    """
    Asegura que cada user_id tenga una LISTA de correos.
    Si encuentra el formato viejo (dict con address/password), lo convierte.
    """
    cambiado = False
    for uid, val in list(data.items()):
        if isinstance(val, dict) and "address" in val and "password" in val:
            data[uid] = [val]
            cambiado = True
        elif val is None:
            data[uid] = []
            cambiado = True
        elif isinstance(val, list):
            # normal
            pass
        else:
            # Cualquier otra cosa rara -> lista vacía
            data[uid] = []
            cambiado = True
    if cambiado:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass
    return data

def cargar_emails():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    return _migrar_estructura(data)

def guardar_emails(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def asegurar_lista_usuario(emails: dict, user_id: str):
    if user_id not in emails or not isinstance(emails[user_id], list):
        emails[user_id] = []

# ================== CORREO / API MAIL.TM ==================
def generar_nombre_usuario():
    nombres = ["user", "test", "bot", "mail", "temp"]
    return random.choice(nombres) + str(random.randint(1000, 9999))

def generar_password():
    return secrets.token_hex(4)  # 8 chars

def obtener_dominios():
    try:
        resp = requests.get(f"{API_BASE}/domains?page=1", timeout=15)
        if resp.status_code == 200:
            return resp.json().get("hydra:member", [])
    except Exception as e:
        logging.error(f"Error al obtener dominios: {e}")
    return []

def crear_email_custom(usuario, dominio, password):
    try:
        payload = {"address": f"{usuario}@{dominio}", "password": password}
        resp = requests.post(f"{API_BASE}/accounts", json=payload, timeout=20)
        if resp.status_code == 201:
            return payload["address"]
        elif resp.status_code == 422:
            # ya existe o inválido
            return None
        else:
            logging.error(f"crear_email_custom resp={resp.status_code} body={resp.text}")
            return None
    except Exception as e:
        logging.error(f"Error creando email: {e}")
        return None

def obtener_mensajes(address, password):
    try:
        login = requests.post(f"{API_BASE}/token", json={"address": address, "password": password}, timeout=15)
        if login.status_code != 200:
            return [], None
        token = login.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/messages", headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("hydra:member", []), token
    except Exception as e:
        logging.error(f"Error obteniendo mensajes: {e}")
    return [], None

def obtener_mensaje_detalle(id_mensaje, token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/messages/{id_mensaje}", headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logging.error(f"Error obteniendo detalle mensaje: {e}")
    return {}

# ================== HELPERS UI ==================
def kb_correos_por_indice(lista, prefix):
    # Botones como: [ address ] -> callback_data="prefix:<idx>"
    filas = []
    for i, e in enumerate(lista):
        label = e.get("address", f"correo_{i}")
        filas.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{i}")])
    return InlineKeyboardMarkup(filas)

# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [
        [InlineKeyboardButton("📩 Crear correo", callback_data="crear_correo")],
        [InlineKeyboardButton("✨ Crear custom", callback_data="crear_custom")],
        [InlineKeyboardButton("✏️ Renombrar correo", callback_data="renombrar")],
        [InlineKeyboardButton("🗑 Eliminar correo", callback_data="eliminar")],
        [InlineKeyboardButton("📬 Mis correos", callback_data="mis_correos")],
        [InlineKeyboardButton("📥 Ver bandeja", callback_data="ver_bandeja")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="info")]
    ]
    await update.message.reply_text(
        "👋 Bienvenido a tu bot de correos temporales.\n\n"
        "Elige una opción del menú:",
        reply_markup=InlineKeyboardMarkup(botones)
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Este bot genera correos temporales usando *mail.tm*",
        parse_mode="Markdown"
    )

# ---------- CALLBACK ESPECÍFICO: DOMINIO CUSTOM ----------
async def custom_domain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # ej: "custom:dom:example.com"
    user_id = str(query.from_user.id)

    emails = cargar_emails()
    asegurar_lista_usuario(emails, user_id)

    if data.startswith("custom:dom:"):
        dominio = data.split(":", 2)[2]
        nombre = context.user_data.get("custom_nombre")
        if not nombre:
            await query.message.reply_text("⚠️ Primero escribe un nombre con '✨ Crear custom'.")
            return

        password = generar_password()
        email = crear_email_custom(nombre, dominio, password)
        if email:
            emails[user_id].append({"address": email, "password": password})
            guardar_emails(emails)
            await query.message.reply_text(
                f"✅ Correo personalizado creado:\n📧 `{email}`\n🔑 `{password}`",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text("⚠️ Ese correo ya existe o el nombre no es válido. Prueba otro.")
        # limpiar nombre temporal
        context.user_data.pop("custom_nombre", None)

# ---------- CALLBACK GENERAL ----------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)

    emails = cargar_emails()
    asegurar_lista_usuario(emails, user_id)

    # 📩 Crear correo aleatorio
    if data == "crear_correo":
        dominios = obtener_dominios()
        if not dominios:
            await query.message.reply_text("❌ No se pudieron obtener dominios.")
            return
        dom = random.choice(dominios).get("domain")
        if not dom:
            await query.message.reply_text("❌ Respuesta de dominios inválida.")
            return
        usuario = generar_nombre_usuario()
        password = generar_password()
        email = crear_email_custom(usuario, dom, password)
        if email:
            emails[user_id].append({"address": email, "password": password})
            guardar_emails(emails)
            await query.message.reply_text(f"✅ Correo creado: `{email}`\n🔑 Contraseña: `{password}`", parse_mode="Markdown")
        else:
            await query.message.reply_text("⚠️ Ese correo ya existe o no se pudo crear. Intenta de nuevo.")

    # ✨ Crear custom → pide nombre primero
    elif data == "crear_custom":
        context.user_data["esperando_nombre_custom"] = True
        await query.message.reply_text("✏️ Escribe el nombre de tu correo (solo el nombre, sin @dominio):", parse_mode="Markdown")

    # 📬 Mis correos
    elif data == "mis_correos":
        if not emails[user_id]:
            await query.message.reply_text("⚠️ Aún no tienes correos creados.")
        else:
            texto = "📬 Tus correos actuales:\n\n"
            for e in emails[user_id]:
                texto += f"📧 `{e['address']}`\n"
            await query.message.reply_text(texto, parse_mode="Markdown")

    # 📥 Ver bandeja
    elif data == "ver_bandeja":
        if not emails[user_id]:
            await query.message.reply_text("⚠️ No tienes correos activos.")
            return
        await query.message.reply_text("📥 Elige un correo para revisar:", reply_markup=kb_correos_por_indice(emails[user_id], "inbox"))

    elif data.startswith("inbox:"):
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.message.reply_text("❌ Selección inválida.")
            return
        if idx < 0 or idx >= len(emails[user_id]):
            await query.message.reply_text("❌ Correo no encontrado.")
            return
        correo = emails[user_id][idx]["address"]
        password = emails[user_id][idx]["password"]

        mensajes, token = obtener_mensajes(correo, password)
        if not token:
            await query.message.reply_text("❌ Error al iniciar sesión con tu correo.")
            return

        if not mensajes:
            await query.message.reply_text(f"📭 Bandeja de `{correo}` vacía.", parse_mode="Markdown")
        else:
            texto = f"📥 **Bandeja de {correo}:**\n\n"
            for m in mensajes[:5]:
                remitente = m.get("from", {}).get("address", "Desconocido")
                asunto = m.get("subject", "Sin asunto")
                detalle = obtener_mensaje_detalle(m.get("id"), token)
                cuerpo = detalle.get("text", "(sin contenido)") if detalle else "(sin contenido)"
                texto += f"🔹 *De:* {remitente}\n*Asunto:* {asunto}\n📜 *Mensaje:* {cuerpo[:200]}...\n\n"
            await query.message.reply_text(texto, parse_mode="Markdown")

    # 🗑 Eliminar correo
    elif data == "eliminar":
        if not emails[user_id]:
            await query.message.reply_text("⚠️ No tienes correos para eliminar.")
            return
        await query.message.reply_text("🗑 Elige el correo que quieres eliminar:", reply_markup=kb_correos_por_indice(emails[user_id], "del"))

    elif data.startswith("del:"):
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.message.reply_text("❌ Selección inválida.")
            return
        if idx < 0 or idx >= len(emails[user_id]):
            await query.message.reply_text("❌ Correo no encontrado.")
            return
        correo = emails[user_id][idx]["address"]
        # elimina por índice
        del emails[user_id][idx]
        guardar_emails(emails)
        await query.message.reply_text(f"🗑 Correo eliminado: `{correo}`", parse_mode="Markdown")

    # ✏️ Renombrar correo
    elif data == "renombrar":
        if not emails[user_id]:
            await query.message.reply_text("⚠️ No tienes correos para renombrar.")
            return
        await query.message.reply_text("✏️ Elige el correo que quieres renombrar:", reply_markup=kb_correos_por_indice(emails[user_id], "ren"))

    elif data.startswith("ren:"):
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.message.reply_text("❌ Selección inválida.")
            return
        if idx < 0 or idx >= len(emails[user_id]):
            await query.message.reply_text("❌ Correo no encontrado.")
            return
        context.user_data["ren_index"] = idx
        context.user_data["esperando_rename"] = True
        correo = emails[user_id][idx]["address"]
        await query.message.reply_text(f"✏️ Escribe el nuevo *nombre de usuario* para `{correo}` (solo la parte antes de @):", parse_mode="Markdown")

    # ℹ️ Info
    elif data == "info":
        await query.message.reply_text(
            "ℹ️ Este bot te permite crear correos temporales con *mail.tm*.\n\n"
            "📩 Crear correo → Genera un email aleatorio\n"
            "✨ Crear custom → Escribes nombre y eliges dominio\n"
            "📬 Mis correos → Lista tus correos creados\n"
            "📥 Ver bandeja → Revisa tus mensajes\n"
            "✏️ Renombrar correo → Cambia el nombre (mismo dominio)\n"
            "🗑 Eliminar correo → Elimina el correo que elijas",
            parse_mode="Markdown"
        )

# =============== HANDLER DE MENSAJES (texto) ==================
async def manejar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    emails = cargar_emails()
    asegurar_lista_usuario(emails, user_id)

    # Crear custom: usuario escribió el nombre
    if context.user_data.get("esperando_nombre_custom"):
        nombre = update.message.text.strip().lower()
        if not nombre or "@" in nombre or " " in nombre:
            await update.message.reply_text("❗ Nombre inválido. Escribe solo la parte antes de '@', sin espacios.")
            return

        context.user_data["custom_nombre"] = nombre
        context.user_data["esperando_nombre_custom"] = False

        dominios = obtener_dominios()
        if not dominios:
            await update.message.reply_text("❌ No se pudieron obtener dominios.")
            return

        # Mostrar dominios como botones específicos
        filas = []
        for dom in dominios:
            d = dom.get("domain")
            if not d:
                continue
            filas.append([InlineKeyboardButton(d, callback_data=f"custom:dom:{d}")])

        await update.message.reply_text(
            f"🌐 Ahora elige un dominio para `{nombre}`:",
            reply_markup=InlineKeyboardMarkup(filas),
            parse_mode="Markdown"
        )
        return

    # Renombrar: usuario escribió nuevo nombre
    if context.user_data.get("esperando_rename"):
        nuevo_usuario = update.message.text.strip().lower()
        if not nuevo_usuario or "@" in nuevo_usuario or " " in nuevo_usuario:
            await update.message.reply_text("❗ Nombre inválido. Escribe solo la parte antes de '@', sin espacios.")
            return

        idx = context.user_data.get("ren_index")
        if idx is None or idx < 0 or idx >= len(emails[user_id]):
            await update.message.reply_text("❌ No encuentro el correo a renombrar. Intenta de nuevo.")
            context.user_data["esperando_rename"] = False
            context.user_data.pop("ren_index", None)
            return

        old = emails[user_id][idx]
        old_correo = old["address"]
        dominio = old_correo.split("@", 1)[1]

        password = generar_password()
        nuevo_correo = crear_email_custom(nuevo_usuario, dominio, password)

        if nuevo_correo:
            # Reemplazamos el registro en el mismo índice
            emails[user_id][idx] = {"address": nuevo_correo, "password": password}
            guardar_emails(emails)
            await update.message.reply_text(
                f"✅ Correo renombrado:\nAntes: `{old_correo}`\nAhora: `{nuevo_correo}`\n🔑 `{password}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Ese nombre ya está en uso o es inválido. Prueba otro.")

        context.user_data["esperando_rename"] = False
        context.user_data.pop("ren_index", None)
        return

# ================== MAIN ==================
