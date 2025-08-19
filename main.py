from Bot_telegram import *
from tempCodeRunnerFile import *
from config import TOKEN






def main():
    app = Application.builder().token(TOKEN).build()

    # Handlers:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))

    # MUY IMPORTANTE: primero el específico del dominio custom,
    # luego el general (para que los clicks de dominio no caigan en el general)
    app.add_handler(CallbackQueryHandler(custom_domain_callback, pattern=r"^custom:dom:"))
    app.add_handler(CallbackQueryHandler(button_callback))  # general

    # Textos del usuario
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_texto))

    logging.info("✅ Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
