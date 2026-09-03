# bot.py - Versione Finale Definitiva
import logging
import json
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
TOKEN = "8386637281:AAHB06Ex-vLau4dqU2znuBo3EWp01Smzqq4"
ATTESA_FOTO, SELEZIONE_RESET, CONFERMA_RESET = range(3)

VOCI_RESET = {
    "vittorie": "✅ Vittorie",
    "sconfitte": "❌ Sconfitte",
    "pareggi": "🤝 Pareggi",
    "gol_fatti": "⚽️ Gol fatti",
    "gol_subiti": "🥅 Gol subiti",
    "partite_giocate": "🎮 Partite giocate",
    "punti": "🏆 Punti",
}

# --- FUNZIONI DI GESTIONE FILE ---
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

# --- FUNZIONI DEI COMANDI ---
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

def crea_tastiera_reset(selezionate):
    """Crea la tastiera mostrando con una spunta le voci selezionate."""
    pulsanti_voci = []
    for chiave, etichetta in VOCI_RESET.items():
        stato = "☑️" if chiave in selezionate else "⬜"
        pulsanti_voci.append(
            InlineKeyboardButton(
                f"{stato} {etichetta}",
                callback_data=f"reset_toggle:{chiave}",
            )
        )

    keyboard = [
        pulsanti_voci[0:2],
        pulsanti_voci[2:4],
        pulsanti_voci[4:6],
        pulsanti_voci[6:7],
        [
            InlineKeyboardButton("☑️ Seleziona tutto", callback_data="reset_select_all"),
            InlineKeyboardButton("⬜ Deseleziona tutto", callback_data="reset_select_none"),
        ],
        [InlineKeyboardButton("➡️ Continua", callback_data="reset_continue")],
        [InlineKeyboardButton("❌ Annulla", callback_data="reset_cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def reset_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reset_selection"] = []
    await update.message.reply_text(
        "♻️ *Reset statistiche*\n\n"
        "Seleziona le voci che vuoi azzerare. Le altre resteranno invariate.",
        reply_markup=crea_tastiera_reset(set()),
        parse_mode="Markdown",
    )
    return SELEZIONE_RESET


async def reset_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    voce = query.data.split(":", 1)[1]
    if voce not in VOCI_RESET:
        return SELEZIONE_RESET

    selezionate = set(context.user_data.get("reset_selection", []))
    if voce in selezionate:
        selezionate.remove(voce)
    else:
        selezionate.add(voce)

    context.user_data["reset_selection"] = list(selezionate)
    await query.edit_message_reply_markup(
        reply_markup=crea_tastiera_reset(selezionate)
    )
    return SELEZIONE_RESET


async def reset_select_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    selezionate = set(VOCI_RESET)
    context.user_data["reset_selection"] = list(selezionate)
    await query.edit_message_reply_markup(
        reply_markup=crea_tastiera_reset(selezionate)
    )
    return SELEZIONE_RESET


async def reset_select_none(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data["reset_selection"] = []
    await query.edit_message_reply_markup(
        reply_markup=crea_tastiera_reset(set())
    )
    return SELEZIONE_RESET


async def reset_riepilogo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    selezionate = set(context.user_data.get("reset_selection", []))

    if not selezionate:
        await query.answer("Seleziona almeno una voce da resettare.", show_alert=True)
        return SELEZIONE_RESET

    await query.answer()
    elenco = "\n".join(
        f"• {etichetta}"
        for chiave, etichetta in VOCI_RESET.items()
        if chiave in selezionate
    )
    keyboard = [
        [InlineKeyboardButton("✅ Conferma reset", callback_data="reset_confirm")],
        [InlineKeyboardButton("⬅️ Modifica selezione", callback_data="reset_back")],
        [InlineKeyboardButton("❌ Annulla", callback_data="reset_cancel")],
    ]
    await query.edit_message_text(
        "‼️ *Conferma reset* ‼️\n\n"
        "Verranno azzerate queste voci per tutti gli utenti:\n\n"
        f"{elenco}\n\n"
        "Tutte le altre statistiche resteranno invariate. "
        "L'operazione è *irreversibile*.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CONFERMA_RESET


async def reset_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selezionate = set(context.user_data.get("reset_selection", []))
    await query.edit_message_text(
        "♻️ *Reset statistiche*\n\n"
        "Seleziona le voci che vuoi azzerare. Le altre resteranno invariate.",
        reply_markup=crea_tastiera_reset(selezionate),
        parse_mode="Markdown",
    )
    return SELEZIONE_RESET

async def reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selezionate = set(context.user_data.pop("reset_selection", []))

    if not selezionate:
        await query.edit_message_text("⚠️ Nessuna voce selezionata. Nessun dato è stato modificato.")
        return ConversationHandler.END

    dati = carica_dati()
    utenti_attivi = set(carica_utenti())
    for nome, statistiche in dati.get("statistiche", {}).items():
        if nome not in utenti_attivi:
            continue
        for voce in selezionate:
            statistiche[voce] = 0

    salva_dati(dati)
    elenco = ", ".join(
        etichetta
        for chiave, etichetta in VOCI_RESET.items()
        if chiave in selezionate
    )
    await query.edit_message_text(f"✅ Reset completato: {elenco}.")
    return ConversationHandler.END

async def reset_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("reset_selection", None)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Operazione annullata.")
    else:
        await update.message.reply_text("Operazione annullata.")
    return ConversationHandler.END

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

# --- FUNZIONE PRINCIPALE (Semplificata e Corretta) ---
def main() -> None:
    """Avvia il bot in modalità polling."""
    application = Application.builder().token(TOKEN).build()

    # Registra tutti i gestori (handlers)
    conv_partita = ConversationHandler(
        entry_points=[CommandHandler('partita', partita_start)],
        states={ATTESA_FOTO: [MessageHandler(filters.PHOTO, ricevi_foto)]},
        fallbacks=[CommandHandler('annulla', annulla)],
    )
    conv_reset = ConversationHandler(
        entry_points=[CommandHandler('reset', reset_start)],
        states={
            SELEZIONE_RESET: [
                CallbackQueryHandler(reset_toggle, pattern=r'^reset_toggle:'),
                CallbackQueryHandler(reset_select_all, pattern=r'^reset_select_all$'),
                CallbackQueryHandler(reset_select_none, pattern=r'^reset_select_none$'),
                CallbackQueryHandler(reset_riepilogo, pattern=r'^reset_continue$'),
                CallbackQueryHandler(reset_cancel, pattern=r'^reset_cancel$'),
            ],
            CONFERMA_RESET: [
                CallbackQueryHandler(reset_confirm, pattern=r'^reset_confirm$'),
                CallbackQueryHandler(reset_back, pattern=r'^reset_back$'),
                CallbackQueryHandler(reset_cancel, pattern=r'^reset_cancel$'),
            ],
        },
        fallbacks=[CommandHandler('annulla', reset_cancel)],
    )
    application.add_handler(conv_partita)
    application.add_handler(conv_reset)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("classifica", classifica_menu))
    application.add_handler(CommandHandler("adduser", adduser))
    application.add_handler(CommandHandler("deluser", deluser))
    application.add_handler(CommandHandler("listusers", listusers))
    application.add_handler(CallbackQueryHandler(gestisci_pulsanti_classifica))

    logging.info("Bot avviato. In ascolto...")
    
    # Questo singolo comando avvia il bot e gestisce tutto internamente.
    application.run_polling()

if __name__ == "__main__":
    main()
