import logging
import json
import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- CONFIGURAZIONE ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8386637281:AAHB06Ex-vLau4dqU2znuBo3EWp01Smzqq4")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ATTESA_FOTO, CONFERMA_RESET = range(2)

# --- FUNZIONI DI GESTIONE FILE (invariate) ---
def carica_utenti():
    try:
        with open('utenti.json', 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        utenti_iniziali = ["Andrew", "Hattory", "Luke", "Tiz", "Fae", "Mancius", "Gonzo", "Paco", "Tau", "Elpaso", "Wantox", "Dade", "Matt", "Eurointer", "Modu", "Maurix"]
        with open('utenti.json', 'w') as f: json.dump(utenti_iniziali, f, indent=4)
        return utenti_iniziali

def salva_utenti(utenti):
    with open('utenti.json', 'w') as f: json.dump(sorted(utenti), f, indent=4)

def carica_dati():
    try:
        with open('dati.json', 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        utenti = carica_utenti()
        statistiche = {n: {"vittorie": 0, "sconfitte": 0, "pareggi": 0, "gol_fatti": 0, "gol_subiti": 0, "partite_giocate": 0, "punti": 0} for n in utenti}
        return {"statistiche": statistiche}

def salva_dati(dati):
    with open('dati.json', 'w') as f: json.dump(dati, f, indent=4)

# --- TUTTE LE FUNZIONI DEI COMANDI (adduser, deluser, reset, partita, classifica, etc.) ---
# (Queste funzioni sono corrette e rimangono identiche)
async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    utenti = carica_utenti()
    messaggio = "👤 *Lista Utenti Registrati:*\n\n" + "\n".join(f"- `{nome}`" for nome in utenti)
    await update.message.reply_text(messaggio, parse_mode='Markdown')

async def adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args: await update.message.reply_text("⚠️ Errore: Devi specificare un nome.\nEsempio: `/adduser Pippo`"); return
    nuovo_utente = context.args[0]
    utenti = carica_utenti()
    if nuovo_utente in utenti: await update.message.reply_text(f"⚠️ `{nuovo_utente}` è già presente nella lista."); return
    utenti.append(nuovo_utente)
    salva_utenti(utenti)
    dati = carica_dati()
    if nuovo_utente not in dati["statistiche"]:
        dati["statistiche"][nuovo_utente] = {"vittorie": 0, "sconfitte": 0, "pareggi": 0, "gol_fatti": 0, "gol_subiti": 0, "partite_giocate": 0, "punti": 0}
        salva_dati(dati)
    await update.message.reply_text(f"✅ Utente `{nuovo_utente}` aggiunto con successo!")

async def deluser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args: await update.message.reply_text("⚠️ Errore: Devi specificare un nome.\nEsempio: `/deluser Pippo`"); return
    utente_da_rimuovere = context.args[0]
    utenti = carica_utenti()
    if utente_da_rimuovere not in utenti: await update.message.reply_text(f"⚠️ Utente `{utente_da_rimuovere}` non trovato."); return
    utenti.remove(utente_da_rimuovere)
    salva_utenti(utenti)
    await update.message.reply_text(f"🗑️ Utente `{utente_da_rimuovere}` rimosso con successo.")

async def reset_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[InlineKeyboardButton("✅ SÌ, RESETTA TUTTO", callback_data='reset_confirm'), InlineKeyboardButton("❌ NO, ANNULLA", callback_data='reset_cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("‼️ *ATTENZIONE* ‼️\n\nSei sicuro di voler cancellare TUTTE le statistiche? L'operazione è *irreversibile*.", reply_markup=reply_markup, parse_mode='Markdown')
    return CONFERMA_RESET

async def reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    utenti = carica_utenti()
    statistiche = {n: {"vittorie": 0, "sconfitte": 0, "pareggi": 0, "gol_fatti": 0, "gol_subiti": 0, "partite_giocate": 0, "punti": 0} for n in utenti}
    salva_dati({"statistiche": statistiche})
    await query.edit_message_text(" resettato con successo."); return ConversationHandler.END

async def reset_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); await query.edit_message_text("Operazione annullata."); return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Ciao! Sono il bot per le amichevoli. Usa /partita o /classifica.')

async def partita_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        testo_completo = " ".join(context.args)
        parti = [p.strip() for p in testo_completo.split(',')]
        player1, player2, risultato = parti[0], parti[1], parti[2]
        gol_p1, gol_p2 = map(int, risultato.split('-'))
        if player1 not in carica_utenti() or player2 not in carica_utenti():
            await update.message.reply_text(f"⚠️ Errore: Uno dei due nomi (`{player1}` o `{player2}`) non è corretto. Usa /listusers per vedere i nomi validi.")
            return ConversationHandler.END
        context.user_data['partita_info'] = {'player1': player1, 'player2': player2, 'gol_p1': gol_p1, 'gol_p2': gol_p2}
        await update.message.reply_text("Dati registrati. Invia lo screenshot per confermare.")
        return ATTESA_FOTO
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Formato errato! Usa:\n`/partita Player1, Player2, Gol1-Gol2`", parse_mode='Markdown')
        return ConversationHandler.END

async def ricevi_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    partita_info = context.user_data.pop('partita_info')
    p1, p2, gol_p1, gol_p2 = partita_info['player1'], partita_info['player2'], partita_info['gol_p1'], partita_info['gol_p2']
    dati = carica_dati()
    stats = dati["statistiche"]
    stats[p1]["partite_giocate"] += 1; stats[p2]["partite_giocate"] += 1
    stats[p1]["gol_fatti"] += gol_p1; stats[p1]["gol_subiti"] += gol_p2
    stats[p2]["gol_fatti"] += gol_p2; stats[p2]["gol_subiti"] += gol_p1
    if gol_p1 > gol_p2: stats[p1]["vittorie"] += 1; stats[p1]["punti"] += 3; stats[p2]["sconfitte"] += 1
    elif gol_p2 > gol_p1: stats[p2]["vittorie"] += 1; stats[p2]["punti"] += 3; stats[p1]["sconfitte"] += 1
    else: stats[p1]["pareggi"] += 1; stats[p1]["punti"] += 1; stats[p2]["pareggi"] += 1
    salva_dati(dati)
    await update.message.reply_text("✅ Screenshot ricevuto e partita salvata!")
    return ConversationHandler.END

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear(); await update.message.reply_text("Operazione annullata."); return ConversationHandler.END

async def classifica_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("🏆 Punti", callback_data='punti'), InlineKeyboardButton("✅ Vittorie", callback_data='vittorie')], [InlineKeyboardButton("❌ Sconfitte", callback_data='sconfitte'), InlineKeyboardButton("🤝 Pareggi", callback_data='pareggi')], [InlineKeyboardButton("⚽️ Gol Fatti", callback_data='gol_fatti'), InlineKeyboardButton("🥅 Gol Subiti", callback_data='gol_subiti')], [InlineKeyboardButton("🎮 Partite Giocate", callback_data='partite_giocate')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Scegli la classifica da visualizzare:', reply_markup=reply_markup)

async def gestisci_pulsanti_classifica(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer()
    tipo_classifica = query.data; dati = carica_dati(); utenti_attivi = carica_utenti()
    statistiche_filtrate = {utente: dati["statistiche"][utente] for utente in utenti_attivi if utente in dati["statistiche"]}
    classifica_ordinata = sorted(statistiche_filtrate.items(), key=lambda item: item[1][tipo_classifica], reverse=True)
    nome_classifica_ita = tipo_classifica.replace('_', ' ').title()
    testo_risposta = f"--- *Classifica {nome_classifica_ita}* ---\n\n"
    if not classifica_ordinata: testo_risposta += "Nessun dato da mostrare."
    else:
        for i, (player, stats) in enumerate(classifica_ordinata, 1):
            testo_risposta += f"*{i}. {player}:* {stats[tipo_classifica]}\n"
    await query.edit_message_text(text=testo_risposta, parse_mode='Markdown')

# --- NUOVA STRUTTURA DI AVVIO ---

# 1. Inizializza l'applicazione del bot e l'app web Flask
application = Application.builder().token(TOKEN).build()
app = Flask(__name__)

# 2. Registra tutti i gestori di comandi (handlers)
conv_partita = ConversationHandler(entry_points=[CommandHandler('partita', partita_start)], states={ATTESA_FOTO: [MessageHandler(filters.PHOTO, ricevi_foto)]}, fallbacks=[CommandHandler('annulla', annulla)])
conv_reset = ConversationHandler(entry_points=[CommandHandler('reset', reset_start)], states={CONFERMA_RESET: [CallbackQueryHandler(reset_confirm, pattern='^reset_confirm$'), CallbackQueryHandler(reset_cancel, pattern='^reset_cancel$')]}, fallbacks=[CommandHandler('annulla', reset_cancel)])
application.add_handler(conv_partita)
application.add_handler(conv_reset)
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("classifica", classifica_menu))
application.add_handler(CommandHandler("adduser", adduser))
application.add_handler(CommandHandler("deluser", deluser))
application.add_handler(CommandHandler("listusers", listusers))
application.add_handler(CallbackQueryHandler(gestisci_pulsanti_classifica))

# 3. Esegui la configurazione asincrona UNA SOLA VOLTA all'avvio
# Questo blocco ora viene eseguito quando Gunicorn importa il file.
async def setup():
    await application.initialize()
    if WEBHOOK_URL:
        await application.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
        logging.info(f"Webhook impostato su {WEBHOOK_URL}")

# Eseguiamo la funzione di setup
asyncio.run(setup())

# 4. Definisci le rotte web per Flask
@app.route("/")
def index():
    return "Bot is running!"

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(), application.bot)
    await application.process_update(update)
    return {"ok": True}