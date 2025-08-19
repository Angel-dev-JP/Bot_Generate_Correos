from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [
        [InlineKeyboardButton("📩 Crear correo", callback_data="crear_correo")],
        [InlineKeyboardButton("✨ Crear custom", callback_data="crear_custom")],
        [InlineKeyboardButton("🌐 Elegir dominio", callback_data="elegir_dominio")],
        [InlineKeyboardButton("✏️ Renombrar correo", callback_data="renombrar")],
        [InlineKeyboardButton("🗑 Eliminar correo", callback_data="eliminar")],
        [InlineKeyboardButton("📬 Mis correos", callback_data="mis_correos")],
        [InlineKeyboardButton("📥 Ver bandeja", callback_data="ver_bandeja")]
    ]
    await update.message.reply_text(
        "👋 Bienvenido a tu bot de correos temporales.\n\n"
        "Elige una opción del menú:",
        reply_markup=InlineKeyboardMarkup(botones)
    )