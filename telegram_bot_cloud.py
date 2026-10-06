"""
Bot de Telegram para gestionar notas rápidas y finanzas personales
Desarrollado por Alejandro - Versión Cloud
"""

import sqlite3
import os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== CONFIGURACIÓN ==========
TOKEN = os.getenv("TELEGRAM_TOKEN")  # Obtener del entorno (Railway)
DATABASE = "asistente.db"

if not TOKEN:
    raise ValueError("❌ ERROR: No se encontró TELEGRAM_TOKEN en las variables de entorno")

# Estados de conversación
NOTA_CONTENT, GASTO_AMOUNT, GASTO_CATEGORY, GASTO_TYPE = range(4)

# ========== BASE DE DATOS ==========
def init_db():
    """Crear las tablas necesarias"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Tabla de notas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY,
            usuario_id INTEGER,
            contenido TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabla de gastos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY,
            usuario_id INTEGER,
            monto REAL,
            categoria TEXT,
            tipo TEXT,
            descripcion TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Base de datos inicializada")

# ========== FUNCIONES DE NOTAS ==========
def guardar_nota(usuario_id, contenido):
    """Guardar una nota rápida en la BD"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notas (usuario_id, contenido) VALUES (?, ?)",
        (usuario_id, contenido)
    )
    conn.commit()
    conn.close()

def obtener_notas(usuario_id, dias=7):
    """Obtener notas de los últimos N días"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    fecha_limite = datetime.now() - timedelta(days=dias)
    cursor.execute("""
        SELECT contenido, fecha FROM notas 
        WHERE usuario_id = ? AND fecha > ?
        ORDER BY fecha DESC
    """, (usuario_id, fecha_limite))
    notas = cursor.fetchall()
    conn.close()
    return notas

# ========== FUNCIONES DE GASTOS ==========
def guardar_gasto(usuario_id, monto, categoria, tipo, descripcion=""):
    """Guardar un gasto en la BD"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO gastos (usuario_id, monto, categoria, tipo, descripcion) 
        VALUES (?, ?, ?, ?, ?)
    """, (usuario_id, monto, categoria, tipo, descripcion))
    conn.commit()
    conn.close()

def obtener_resumen(usuario_id, dias=30):
    """Obtener resumen de gastos por categoría"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    fecha_limite = datetime.now() - timedelta(days=dias)
    
    cursor.execute("""
        SELECT tipo, categoria, SUM(monto) as total, COUNT(*) as cantidad
        FROM gastos 
        WHERE usuario_id = ? AND fecha > ?
        GROUP BY tipo, categoria
        ORDER BY total DESC
    """, (usuario_id, fecha_limite))
    
    resumen = cursor.fetchall()
    conn.close()
    return resumen

def obtener_total_gastos(usuario_id, dias=30):
    """Obtener total de gastos"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    fecha_limite = datetime.now() - timedelta(dias=dias)
    cursor.execute("""
        SELECT SUM(monto) FROM gastos 
        WHERE usuario_id = ? AND fecha > ?
    """, (usuario_id, fecha_limite))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado[0] else 0

# ========== COMANDOS DEL BOT ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Mensaje de bienvenida"""
    usuario = update.effective_user
    mensaje = f"""
👋 ¡Hola {usuario.first_name}!

Soy tu asistente personal en Telegram. Puedo ayudarte con:

📝 *Notas rápidas*
💰 *Gestión de gastos*
📊 *Resumen financiero*

Comandos disponibles:
/nota - Crear una nota rápida
/gasto - Registrar un gasto
/resumen - Ver resumen de gastos (últimos 30 días)
/notas - Ver mis notas recientes
/ayuda - Ver más información

¿Por dónde empezamos? 😊
    """
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ayuda - Información detallada"""
    mensaje = """
📚 *GUÍA DE USO*

*📝 NOTAS RÁPIDAS*
/nota - Crear una nota
/notas - Ver últimas 7 notas

Ejemplo: 
`/nota Llamar al proveedor mañana a las 3pm`

*💰 GASTOS*
/gasto - Registrar un gasto nuevo
/resumen - Ver gastos de los últimos 30 días

Ejemplo:
Tipo: personal o negocio
Categoría: comida, transporte, servicios, etc.
Monto: 25.50

*📊 REPORTES*
/resumen - Desglose por categoría y tipo

¿Necesitas más ayuda? ¡Simplemente escribe /start!
    """
    await update.message.reply_text(mensaje, parse_mode="Markdown")

# ========== CONVERSACIÓN: NOTA ==========
async def nota_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Iniciar creación de nota"""
    await update.message.reply_text(
        "📝 *Nueva Nota*\n\nEscribe el contenido de tu nota:",
        parse_mode="Markdown"
    )
    return NOTA_CONTENT

async def nota_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesar contenido de la nota"""
    usuario_id = update.effective_user.id
    contenido = update.message.text
    
    guardar_nota(usuario_id, contenido)
    await update.message.reply_text(
        "✅ Nota guardada exitosamente!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def nota_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancelar creación de nota"""
    await update.message.reply_text("❌ Nota cancelada")
    return ConversationHandler.END

# ========== CONVERSACIÓN: GASTO ==========
async def gasto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Iniciar registro de gasto"""
    teclado = [["Personal", "Negocio"]]
    reply_markup = ReplyKeyboardMarkup(teclado, one_time_keyboard=True)
    await update.message.reply_text(
        "💰 *Nuevo Gasto*\n\n¿Es gasto personal o del negocio?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return GASTO_TYPE

async def gasto_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesar tipo de gasto"""
    context.user_data["tipo_gasto"] = update.message.text.lower()
    await update.message.reply_text(
        "¿En qué categoría? (comida, transporte, servicios, productos, otro)",
        parse_mode="Markdown"
    )
    return GASTO_CATEGORY

async def gasto_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesar categoría"""
    context.user_data["categoria_gasto"] = update.message.text.lower()
    await update.message.reply_text(
        "¿Cuál es el monto? (ej: 25.50)",
        parse_mode="Markdown"
    )
    return GASTO_AMOUNT

async def gasto_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesar monto y guardar gasto"""
    usuario_id = update.effective_user.id
    try:
        monto = float(update.message.text)
        tipo = context.user_data["tipo_gasto"]
        categoria = context.user_data["categoria_gasto"]
        
        guardar_gasto(usuario_id, monto, categoria, tipo)
        await update.message.reply_text(
            f"✅ Gasto de ${monto} guardado en {categoria} ({tipo})",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Error: Ingresa un número válido")
        return GASTO_AMOUNT
    
    return ConversationHandler.END

async def gasto_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancelar registro de gasto"""
    await update.message.reply_text("❌ Gasto cancelado")
    return ConversationHandler.END

# ========== COMANDOS: VER DATOS ==========
async def ver_notas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver notas recientes"""
    usuario_id = update.effective_user.id
    notas = obtener_notas(usuario_id, dias=7)
    
    if not notas:
        await update.message.reply_text("📭 No tienes notas en los últimos 7 días")
        return
    
    mensaje = "📝 *Tus Notas Recientes (últimos 7 días):*\n\n"
    for i, (contenido, fecha) in enumerate(notas, 1):
        mensaje += f"{i}. {contenido}\n   _{fecha}_\n\n"
    
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver resumen de gastos"""
    usuario_id = update.effective_user.id
    resumen_data = obtener_resumen(usuario_id, dias=30)
    total = obtener_total_gastos(usuario_id, dias=30)
    
    if not resumen_data:
        await update.message.reply_text("📊 No tienes gastos registrados en los últimos 30 días")
        return
    
    mensaje = f"📊 *Resumen de Gastos (últimos 30 días):*\n\n"
    mensaje += f"💰 *Total: ${total:.2f}*\n\n"
    
    for tipo, categoria, monto, cantidad in resumen_data:
        mensaje += f"{tipo.title()}\n"
        mensaje += f"  • {categoria}: ${monto:.2f} ({cantidad} gasto(s))\n"
    
    await update.message.reply_text(mensaje, parse_mode="Markdown")

# ========== MAIN ==========
def main():
    """Función principal - Iniciar el bot"""
    
    # Inicializar BD
    init_db()
    
    # Crear aplicación
    app = Application.builder().token(TOKEN).build()
    
    # Comandos simples
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("notas", ver_notas))
    app.add_handler(CommandHandler("resumen", resumen))
    
    # Conversación: Nota
    nota_handler = ConversationHandler(
        entry_points=[CommandHandler("nota", nota_start)],
        states={
            NOTA_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, nota_content)],
        },
        fallbacks=[CommandHandler("cancelar", nota_cancel)],
    )
    app.add_handler(nota_handler)
    
    # Conversación: Gasto
    gasto_handler = ConversationHandler(
        entry_points=[CommandHandler("gasto", gasto_start)],
        states={
            GASTO_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gasto_type)],
            GASTO_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, gasto_category)],
            GASTO_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, gasto_amount)],
        },
        fallbacks=[CommandHandler("cancelar", gasto_cancel)],
    )
    app.add_handler(gasto_handler)
    
    # Iniciar bot
    logger.info("🤖 Bot iniciado en la nube...")
    app.run_polling()

if __name__ == "__main__":
    main()
