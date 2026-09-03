# bot.py - Gestione classifiche settimanali, totali e storico
import copy
import html
import logging
import json
import os
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
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
(
    ATTESA_FOTO,
    SELEZIONE_RESET,
    CONFERMA_RESET,
    SELEZIONE_CHIUSURA,
    CONFERMA_CHIUSURA,
) = range(5)

FUSO_ORARIO = ZoneInfo("Europe/Rome")
STORICO_PER_PAGINA = 8

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
def statistiche_vuote():
    return {voce: 0 for voce in VOCI_RESET}


def carica_utenti():
    try:
        with open('utenti.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        utenti_iniziali = ["Andrew", "Hattory", "Luke", "Tiz", "Fae", "Mancius", "Gonzo", "Paco", "Tau", "Elpaso", "Wantox", "Dade", "Matt", "Eurointer", "Modu", "Maurix"]
        salva_utenti(utenti_iniziali)
        return utenti_iniziali


def salva_utenti(utenti):
    percorso_temporaneo = 'utenti.json.tmp'
    with open(percorso_temporaneo, 'w', encoding='utf-8') as f:
        json.dump(sorted(utenti), f, indent=4, ensure_ascii=False)
    os.replace(percorso_temporaneo, 'utenti.json')


def normalizza_blocco_statistiche(blocco, utenti_da_aggiungere=()):
    if not isinstance(blocco, dict):
        blocco = {}

    for nome in utenti_da_aggiungere:
        blocco.setdefault(nome, statistiche_vuote())

    for nome, statistiche in list(blocco.items()):
        if not isinstance(statistiche, dict):
            statistiche = statistiche_vuote()
            blocco[nome] = statistiche
        for voce in VOCI_RESET:
            statistiche.setdefault(voce, 0)
    return blocco


def normalizza_dati(dati):
    """Aggiorna automaticamente il vecchio formato senza perdere i dati esistenti."""
    if not isinstance(dati, dict):
        dati = {}

    utenti = carica_utenti()
    statistiche_correnti = normalizza_blocco_statistiche(
        dati.get("statistiche"), utenti
    )

    statistiche_totali_esistenti = dati.get("statistiche_totali")
    if not isinstance(statistiche_totali_esistenti, dict):
        # Alla prima esecuzione i valori gia presenti diventano il totale iniziale.
        statistiche_totali = copy.deepcopy(statistiche_correnti)
    else:
        statistiche_totali = normalizza_blocco_statistiche(
            statistiche_totali_esistenti, utenti
        )
        # Conserva anche eventuali giocatori non piu presenti nella lista utenti.
        for nome, statistiche in statistiche_correnti.items():
            statistiche_totali.setdefault(nome, copy.deepcopy(statistiche))

    storico = dati.get("storico_settimane")
    if not isinstance(storico, list):
        storico = []

    periodi_correnti = dati.get("periodi_correnti")
    if not isinstance(periodi_correnti, dict):
        periodi_correnti = {}
    for voce in VOCI_RESET:
        periodi_correnti.setdefault(voce, None)

    dati["schema_version"] = 2
    dati["statistiche"] = statistiche_correnti
    dati["statistiche_totali"] = statistiche_totali
    dati["storico_settimane"] = storico
    dati["periodi_correnti"] = periodi_correnti
    return dati


def carica_dati():
    try:
        with open('dati.json', 'r', encoding='utf-8') as f:
            return normalizza_dati(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        utenti = carica_utenti()
        statistiche = {nome: statistiche_vuote() for nome in utenti}
        return normalizza_dati({"statistiche": statistiche})


def salva_dati(dati):
    dati = normalizza_dati(dati)
    percorso_temporaneo = 'dati.json.tmp'
    with open(percorso_temporaneo, 'w', encoding='utf-8') as f:
        json.dump(dati, f, indent=4, ensure_ascii=False)
    os.replace(percorso_temporaneo, 'dati.json')


def adesso_iso():
    return datetime.now(FUSO_ORARIO).isoformat(timespec="seconds")


def formatta_data_iso(valore, con_ora=False):
    if not valore:
        return None
    try:
        data = datetime.fromisoformat(valore)
        formato = "%d/%m/%Y %H:%M" if con_ora else "%d/%m/%Y"
        return data.strftime(formato)
    except (TypeError, ValueError):
        return str(valore)


def etichetta_settimana(settimana):
    numero = settimana.get("numero", "?")
    chiusa_il = formatta_data_iso(
        settimana.get("chiusa_il"), con_ora=True
    ) or "data sconosciuta"
    periodi = settimana.get("periodi", {})
    if not isinstance(periodi, dict):
        periodi = {}
    voci = settimana.get("voci", [])
    inizi_per_voce = [
        periodi.get(voce, {}).get("dal")
        if isinstance(periodi.get(voce), dict)
        else None
        for voce in voci
    ]
    inizi_presenti = {inizio for inizio in inizi_per_voce if inizio}

    if inizi_per_voce and all(inizi_per_voce) and len(inizi_presenti) == 1:
        inizio = formatta_data_iso(next(iter(inizi_presenti)))
        fine = formatta_data_iso(settimana.get("chiusa_il"))
        return f"Settimana {numero} - {inizio} / {fine}"
    if not inizi_presenti:
        return f"Settimana {numero} - fino al {chiusa_il}"
    return f"Chiusura {numero} - {chiusa_il}"


def etichetta_periodo_voce(settimana, voce):
    """Mostra il periodo effettivo della singola statistica archiviata."""
    periodi = settimana.get("periodi", {})
    if not isinstance(periodi, dict):
        periodi = {}
    dettagli = periodi.get(voce, {})
    if not isinstance(dettagli, dict):
        dettagli = {}

    inizio = formatta_data_iso(dettagli.get("dal"), con_ora=True)
    fine = formatta_data_iso(
        dettagli.get("al") or settimana.get("chiusa_il"), con_ora=True
    )
    if inizio and fine:
        return f"Periodo: {inizio} - {fine}"
    if fine:
        return f"Valori accumulati fino al {fine}"
    return "Periodo non disponibile"


def archivia_settimana(dati, selezionate, utenti_attivi, istante=None):
    """Crea una fotografia dei valori correnti e azzera solo la settimana."""
    dati = normalizza_dati(dati)
    istante = istante or adesso_iso()
    selezionate_ordinate = [voce for voce in VOCI_RESET if voce in selezionate]

    numeri_esistenti = [
        settimana.get("numero", 0)
        for settimana in dati["storico_settimane"]
        if isinstance(settimana, dict)
        and isinstance(settimana.get("numero", 0), int)
    ]
    numero = max(numeri_esistenti, default=0) + 1

    fotografia = {}
    for nome in utenti_attivi:
        statistiche = dati["statistiche"].setdefault(nome, statistiche_vuote())
        fotografia[nome] = {
            voce: statistiche.get(voce, 0) for voce in selezionate_ordinate
        }

    periodi = {
        voce: {
            "dal": dati["periodi_correnti"].get(voce),
            "al": istante,
        }
        for voce in selezionate_ordinate
    }

    settimana = {
        "id": uuid4().hex[:12],
        "numero": numero,
        "chiusa_il": istante,
        "voci": selezionate_ordinate,
        "periodi": periodi,
        "statistiche": fotografia,
    }
    dati["storico_settimane"].append(settimana)

    for nome in utenti_attivi:
        statistiche = dati["statistiche"].setdefault(nome, statistiche_vuote())
        for voce in selezionate_ordinate:
            statistiche[voce] = 0

    for voce in selezionate_ordinate:
        dati["periodi_correnti"][voce] = istante

    return settimana


def resetta_definitivamente(dati, selezionate, istante=None):
    """Elimina le voci scelte da settimana corrente, totale e archivio."""
    dati = normalizza_dati(dati)
    istante = istante or adesso_iso()

    for nome_statistiche in ("statistiche", "statistiche_totali"):
        for statistiche in dati[nome_statistiche].values():
            for voce in selezionate:
                statistiche[voce] = 0

    storico_rimanente = []
    for settimana in dati["storico_settimane"]:
        if not isinstance(settimana, dict):
            continue
        settimana["voci"] = [
            voce for voce in settimana.get("voci", []) if voce not in selezionate
        ]
        statistiche_settimana = settimana.get("statistiche", {})
        if not isinstance(statistiche_settimana, dict):
            statistiche_settimana = {}
            settimana["statistiche"] = statistiche_settimana
        for statistiche in statistiche_settimana.values():
            if not isinstance(statistiche, dict):
                continue
            for voce in selezionate:
                statistiche.pop(voce, None)
        periodi = settimana.get("periodi", {})
        if not isinstance(periodi, dict):
            periodi = {}
            settimana["periodi"] = periodi
        for voce in selezionate:
            periodi.pop(voce, None)
        if settimana["voci"]:
            storico_rimanente.append(settimana)
    dati["storico_settimane"] = storico_rimanente

    for voce in selezionate:
        dati["periodi_correnti"][voce] = istante

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
    dati["statistiche"].setdefault(nuovo_utente, statistiche_vuote())
    dati["statistiche_totali"].setdefault(nuovo_utente, statistiche_vuote())
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

def crea_tastiera_selezione(selezionate, prefisso):
    """Crea la tastiera con le voci selezionabili per chiusura o reset."""
    pulsanti_voci = []
    for chiave, etichetta in VOCI_RESET.items():
        stato = "☑️" if chiave in selezionate else "⬜"
        pulsanti_voci.append(
            InlineKeyboardButton(
                f"{stato} {etichetta}",
                callback_data=f"{prefisso}_toggle:{chiave}",
            )
        )

    keyboard = [
        pulsanti_voci[0:2],
        pulsanti_voci[2:4],
        pulsanti_voci[4:6],
        pulsanti_voci[6:7],
        [
            InlineKeyboardButton(
                "☑️ Seleziona tutto", callback_data=f"{prefisso}_select_all"
            ),
            InlineKeyboardButton(
                "⬜ Deseleziona tutto", callback_data=f"{prefisso}_select_none"
            ),
        ],
        [InlineKeyboardButton("➡️ Continua", callback_data=f"{prefisso}_continue")],
        [InlineKeyboardButton("❌ Annulla", callback_data=f"{prefisso}_cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def crea_tastiera_reset(selezionate):
    return crea_tastiera_selezione(selezionate, "reset")


def crea_tastiera_chiusura(selezionate):
    return crea_tastiera_selezione(selezionate, "close")


async def reset_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reset_selection"] = []
    await update.message.reply_text(
        "🗑️ *Reset definitivo*\n\n"
        "Seleziona le voci da eliminare definitivamente dalla settimana "
        "attuale, dai totali e dalle settimane archiviate.\n\n"
        "Per la normale chiusura usa /chiusurasettimanale.",
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
        [
            InlineKeyboardButton(
                "🗑️ Elimina definitivamente", callback_data="reset_confirm"
            )
        ],
        [InlineKeyboardButton("⬅️ Modifica selezione", callback_data="reset_back")],
        [InlineKeyboardButton("❌ Annulla", callback_data="reset_cancel")],
    ]
    await query.edit_message_text(
        "‼️ *Conferma eliminazione definitiva* ‼️\n\n"
        "Queste voci verranno cancellate dalla settimana attuale, "
        "dai totali e da tutto lo storico:\n\n"
        f"{elenco}\n\n"
        "Le altre statistiche resteranno invariate. "
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
        "🗑️ *Reset definitivo*\n\n"
        "Seleziona le voci da eliminare definitivamente dalla settimana "
        "attuale, dai totali e dalle settimane archiviate.",
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
    resetta_definitivamente(dati, selezionate)
    salva_dati(dati)
    elenco = ", ".join(
        etichetta
        for chiave, etichetta in VOCI_RESET.items()
        if chiave in selezionate
    )
    await query.edit_message_text(
        f"✅ Reset definitivo completato: {elenco}.\n"
        "I dati selezionati sono stati rimossi anche dai totali e dallo storico."
    )
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


async def chiusura_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["close_selection"] = []
    await update.message.reply_text(
        "📦 *Chiusura settimanale*\n\n"
        "Seleziona le voci da archiviare e azzerare soltanto nella "
        "settimana attuale. I totali generali resteranno invariati.",
        reply_markup=crea_tastiera_chiusura(set()),
        parse_mode="Markdown",
    )
    return SELEZIONE_CHIUSURA


async def chiusura_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    voce = query.data.split(":", 1)[1]
    if voce not in VOCI_RESET:
        return SELEZIONE_CHIUSURA

    selezionate = set(context.user_data.get("close_selection", []))
    if voce in selezionate:
        selezionate.remove(voce)
    else:
        selezionate.add(voce)
    context.user_data["close_selection"] = list(selezionate)
    await query.edit_message_reply_markup(
        reply_markup=crea_tastiera_chiusura(selezionate)
    )
    return SELEZIONE_CHIUSURA


async def chiusura_select_all(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    selezionate = set(VOCI_RESET)
    context.user_data["close_selection"] = list(selezionate)
    await query.edit_message_reply_markup(
        reply_markup=crea_tastiera_chiusura(selezionate)
    )
    return SELEZIONE_CHIUSURA


async def chiusura_select_none(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["close_selection"] = []
    await query.edit_message_reply_markup(
        reply_markup=crea_tastiera_chiusura(set())
    )
    return SELEZIONE_CHIUSURA


async def chiusura_riepilogo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    selezionate = set(context.user_data.get("close_selection", []))
    if not selezionate:
        await query.answer("Seleziona almeno una voce da archiviare.", show_alert=True)
        return SELEZIONE_CHIUSURA

    await query.answer()
    elenco = "\n".join(
        f"• {etichetta}"
        for chiave, etichetta in VOCI_RESET.items()
        if chiave in selezionate
    )
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Archivia e chiudi settimana", callback_data="close_confirm"
            )
        ],
        [InlineKeyboardButton("⬅️ Modifica selezione", callback_data="close_back")],
        [InlineKeyboardButton("❌ Annulla", callback_data="close_cancel")],
    ]
    await query.edit_message_text(
        "📦 *Conferma chiusura settimanale*\n\n"
        "Verranno archiviate queste voci:\n\n"
        f"{elenco}\n\n"
        "Saranno azzerate soltanto per la nuova settimana. "
        "La classifica totale non verrà modificata.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CONFERMA_CHIUSURA


async def chiusura_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selezionate = set(context.user_data.get("close_selection", []))
    await query.edit_message_text(
        "📦 *Chiusura settimanale*\n\n"
        "Seleziona le voci da archiviare. I totali resteranno invariati.",
        reply_markup=crea_tastiera_chiusura(selezionate),
        parse_mode="Markdown",
    )
    return SELEZIONE_CHIUSURA


async def chiusura_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    selezionate = set(context.user_data.pop("close_selection", []))
    if not selezionate:
        await query.edit_message_text(
            "⚠️ Nessuna voce selezionata. Nessun dato è stato modificato."
        )
        return ConversationHandler.END

    dati = carica_dati()
    settimana = archivia_settimana(dati, selezionate, carica_utenti())
    salva_dati(dati)
    elenco = ", ".join(
        etichetta
        for chiave, etichetta in VOCI_RESET.items()
        if chiave in selezionate
    )
    await query.edit_message_text(
        f"✅ {etichetta_settimana(settimana)} archiviata.\n\n"
        f"Voci chiuse: {elenco}.\n"
        "La settimana attuale riparte da zero per queste voci; "
        "i totali generali sono rimasti invariati."
    )
    return ConversationHandler.END


async def chiusura_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    context.user_data.pop("close_selection", None)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Chiusura settimanale annullata.")
    else:
        await update.message.reply_text("Chiusura settimanale annullata.")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Ciao! Sono il bot per le amichevoli.\n\n"
        "Usa /partita per registrare un risultato, /classifica per consultare "
        "le classifiche e /chiusurasettimanale per archiviare la settimana."
    )

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
    # Ogni risultato alimenta sia la settimana corrente sia il totale generale.
    for nome_blocco in ("statistiche", "statistiche_totali"):
        stats = dati[nome_blocco]
        stats.setdefault(p1, statistiche_vuote())
        stats.setdefault(p2, statistiche_vuote())
        stats[p1]["partite_giocate"] += 1
        stats[p2]["partite_giocate"] += 1
        stats[p1]["gol_fatti"] += gol_p1
        stats[p1]["gol_subiti"] += gol_p2
        stats[p2]["gol_fatti"] += gol_p2
        stats[p2]["gol_subiti"] += gol_p1
        if gol_p1 > gol_p2:
            stats[p1]["vittorie"] += 1
            stats[p1]["punti"] += 3
            stats[p2]["sconfitte"] += 1
        elif gol_p2 > gol_p1:
            stats[p2]["vittorie"] += 1
            stats[p2]["punti"] += 3
            stats[p1]["sconfitte"] += 1
        else:
            stats[p1]["pareggi"] += 1
            stats[p1]["punti"] += 1
            stats[p2]["pareggi"] += 1
    salva_dati(dati)
    await update.message.reply_text("✅ Screenshot ricevuto e partita salvata!")
    return ConversationHandler.END

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear(); await update.message.reply_text("Operazione annullata."); return ConversationHandler.END


def crea_tastiera_periodi_classifica():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 Settimana attuale", callback_data="class_period:current"
                ),
                InlineKeyboardButton(
                    "🏆 Classifica totale", callback_data="class_period:total"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📚 Consulta settimane precedenti",
                    callback_data="class_history_page:0",
                )
            ],
        ]
    )


def crea_tastiera_metriche(ambito, id_settimana=None, disponibili=None):
    disponibili = set(disponibili or VOCI_RESET.keys())
    pulsanti = []
    for chiave, etichetta in VOCI_RESET.items():
        if chiave not in disponibili:
            continue
        if ambito == "week":
            callback = f"class_week_show:{id_settimana}:{chiave}"
        else:
            callback = f"class_show:{ambito}:{chiave}"
        pulsanti.append(InlineKeyboardButton(etichetta, callback_data=callback))

    righe = [pulsanti[indice:indice + 2] for indice in range(0, len(pulsanti), 2)]
    if ambito == "week":
        righe.append(
            [
                InlineKeyboardButton(
                    "⬅️ Settimane precedenti", callback_data="class_history_return"
                )
            ]
        )
    else:
        righe.append(
            [
                InlineKeyboardButton(
                    "⬅️ Tipo di classifica", callback_data="class_periods"
                )
            ]
        )
    return InlineKeyboardMarkup(righe)


def trova_settimana(dati, id_settimana):
    for settimana in dati.get("storico_settimane", []):
        if isinstance(settimana, dict) and settimana.get("id") == id_settimana:
            return settimana
    return None


def genera_testo_classifica(tipo, statistiche, titolo_periodo, utenti=None):
    if tipo not in VOCI_RESET:
        return "⚠️ Tipo di classifica non valido."

    nomi = utenti if utenti is not None else list(statistiche.keys())
    righe = [
        (nome, statistiche[nome])
        for nome in nomi
        if nome in statistiche and isinstance(statistiche[nome], dict)
    ]

    def valore_numerico(elemento):
        valore = elemento[1].get(tipo, 0)
        try:
            return float(valore)
        except (TypeError, ValueError):
            return 0.0

    righe.sort(key=lambda elemento: (-valore_numerico(elemento), str(elemento[0]).casefold()))
    nome_classifica = VOCI_RESET[tipo]
    testo = (
        f"<b>{html.escape(nome_classifica)}</b>\n"
        f"<i>{html.escape(titolo_periodo)}</i>\n\n"
    )
    if not righe:
        return testo + "Nessun dato da mostrare."

    for posizione, (nome, valori) in enumerate(righe, 1):
        valore = valori.get(tipo, 0)
        testo += f"<b>{posizione}. {html.escape(str(nome))}:</b> {valore}\n"
    return testo


async def classifica_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Scegli quale periodo vuoi consultare:",
        reply_markup=crea_tastiera_periodi_classifica(),
    )


async def classifica_periodi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Scegli quale periodo vuoi consultare:",
        reply_markup=crea_tastiera_periodi_classifica(),
    )


async def classifica_scegli_periodo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    ambito = query.data.split(":", 1)[1]
    if ambito not in ("current", "total"):
        await query.edit_message_text("⚠️ Periodo non valido.")
        return
    titolo = "📊 Settimana attuale" if ambito == "current" else "🏆 Totale generale"
    await query.edit_message_text(
        f"{titolo}\n\nScegli la classifica da visualizzare:",
        reply_markup=crea_tastiera_metriche(ambito),
    )


async def mostra_elenco_storico(query, context, pagina):
    dati = carica_dati()
    storico = [
        settimana
        for settimana in dati.get("storico_settimane", [])
        if isinstance(settimana, dict) and settimana.get("id")
    ]
    storico.sort(key=lambda settimana: settimana.get("chiusa_il", ""), reverse=True)

    if not storico:
        await query.edit_message_text(
            "📚 Non ci sono ancora settimane archiviate.\n\n"
            "Usa /chiusurasettimanale al termine della settimana.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Indietro", callback_data="class_periods")]]
            ),
        )
        return

    pagine_totali = (len(storico) + STORICO_PER_PAGINA - 1) // STORICO_PER_PAGINA
    pagina = max(0, min(pagina, pagine_totali - 1))
    context.user_data["class_history_page"] = pagina
    inizio = pagina * STORICO_PER_PAGINA
    settimane_pagina = storico[inizio:inizio + STORICO_PER_PAGINA]

    keyboard = [
        [
            InlineKeyboardButton(
                f"📅 {etichetta_settimana(settimana)}",
                callback_data=f"class_history_select:{settimana['id']}",
            )
        ]
        for settimana in settimane_pagina
    ]
    navigazione = []
    if pagina > 0:
        navigazione.append(
            InlineKeyboardButton(
                "⬅️ Più recenti", callback_data=f"class_history_page:{pagina - 1}"
            )
        )
    if pagina < pagine_totali - 1:
        navigazione.append(
            InlineKeyboardButton(
                "Più vecchie ➡️", callback_data=f"class_history_page:{pagina + 1}"
            )
        )
    if navigazione:
        keyboard.append(navigazione)
    keyboard.append(
        [InlineKeyboardButton("⬅️ Tipo di classifica", callback_data="class_periods")]
    )
    await query.edit_message_text(
        f"📚 Scegli una settimana archiviata ({pagina + 1}/{pagine_totali}):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def classifica_storico_pagina(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    try:
        pagina = int(query.data.rsplit(":", 1)[1])
    except (TypeError, ValueError):
        pagina = 0
    await mostra_elenco_storico(query, context, pagina)


async def classifica_storico_return(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    pagina = context.user_data.get("class_history_page", 0)
    await mostra_elenco_storico(query, context, pagina)


async def classifica_scegli_settimana(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    id_settimana = query.data.split(":", 1)[1]
    settimana = trova_settimana(carica_dati(), id_settimana)
    if not settimana:
        await query.edit_message_text(
            "⚠️ Questa settimana non è più disponibile.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Settimane precedenti",
                            callback_data="class_history_return",
                        )
                    ]
                ]
            ),
        )
        return

    await query.edit_message_text(
        f"📅 {etichetta_settimana(settimana)}\n\n"
        "Scegli la classifica da visualizzare:",
        reply_markup=crea_tastiera_metriche(
            "week", settimana["id"], settimana.get("voci", [])
        ),
    )


async def classifica_mostra_corrente_totale(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    parti = query.data.split(":")
    if len(parti) != 3:
        await query.edit_message_text("⚠️ Richiesta non valida.")
        return
    _, ambito, tipo = parti
    if ambito not in ("current", "total") or tipo not in VOCI_RESET:
        await query.edit_message_text("⚠️ Richiesta non valida.")
        return

    dati = carica_dati()
    chiave_dati = "statistiche" if ambito == "current" else "statistiche_totali"
    titolo = "Settimana attuale" if ambito == "current" else "Totale generale"
    testo = genera_testo_classifica(
        tipo, dati[chiave_dati], titolo, carica_utenti()
    )
    await query.edit_message_text(
        testo,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⬅️ Altre classifiche",
                        callback_data=f"class_period:{ambito}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Scegli periodo", callback_data="class_periods"
                    )
                ],
            ]
        ),
    )


async def classifica_mostra_settimana(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    parti = query.data.split(":")
    if len(parti) != 3:
        await query.edit_message_text("⚠️ Richiesta non valida.")
        return
    _, id_settimana, tipo = parti
    dati = carica_dati()
    settimana = trova_settimana(dati, id_settimana)
    if not settimana or tipo not in settimana.get("voci", []):
        await query.edit_message_text(
            "⚠️ Questa classifica non è più disponibile.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Settimane precedenti",
                            callback_data="class_history_return",
                        )
                    ]
                ]
            ),
        )
        return

    testo = genera_testo_classifica(
        tipo,
        settimana.get("statistiche", {}),
        f"{etichetta_settimana(settimana)}\n"
        f"{etichetta_periodo_voce(settimana, tipo)}",
    )
    await query.edit_message_text(
        testo,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⬅️ Altre classifiche della settimana",
                        callback_data=f"class_history_select:{id_settimana}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📚 Tutte le settimane", callback_data="class_history_return"
                    )
                ],
            ]
        ),
    )


async def classifica_legacy(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Mantiene funzionanti i vecchi pulsanti gia inviati prima dell'aggiornamento."""
    query = update.callback_query
    await query.answer()
    tipo = query.data
    dati = carica_dati()
    testo = genera_testo_classifica(
        tipo, dati["statistiche"], "Settimana attuale", carica_utenti()
    )
    await query.edit_message_text(
        testo,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Scegli periodo", callback_data="class_periods")]]
        ),
    )

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
    conv_chiusura = ConversationHandler(
        entry_points=[
            CommandHandler(
                [
                    "chiusurasettimanale",
                    "chiusura_settimanale",
                    "chiudi_settimana",
                    "chiusura",
                ],
                chiusura_start,
            )
        ],
        states={
            SELEZIONE_CHIUSURA: [
                CallbackQueryHandler(chiusura_toggle, pattern=r'^close_toggle:'),
                CallbackQueryHandler(
                    chiusura_select_all, pattern=r'^close_select_all$'
                ),
                CallbackQueryHandler(
                    chiusura_select_none, pattern=r'^close_select_none$'
                ),
                CallbackQueryHandler(
                    chiusura_riepilogo, pattern=r'^close_continue$'
                ),
                CallbackQueryHandler(chiusura_cancel, pattern=r'^close_cancel$'),
            ],
            CONFERMA_CHIUSURA: [
                CallbackQueryHandler(chiusura_confirm, pattern=r'^close_confirm$'),
                CallbackQueryHandler(chiusura_back, pattern=r'^close_back$'),
                CallbackQueryHandler(chiusura_cancel, pattern=r'^close_cancel$'),
            ],
        },
        fallbacks=[CommandHandler('annulla', chiusura_cancel)],
    )
    application.add_handler(conv_partita)
    application.add_handler(conv_reset)
    application.add_handler(conv_chiusura)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("classifica", classifica_menu))
    application.add_handler(CommandHandler("adduser", adduser))
    application.add_handler(CommandHandler("deluser", deluser))
    application.add_handler(CommandHandler("listusers", listusers))
    application.add_handler(
        CallbackQueryHandler(classifica_periodi, pattern=r'^class_periods$')
    )
    application.add_handler(
        CallbackQueryHandler(
            classifica_scegli_periodo, pattern=r'^class_period:(current|total)$'
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            classifica_storico_pagina, pattern=r'^class_history_page:\d+$'
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            classifica_storico_return, pattern=r'^class_history_return$'
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            classifica_scegli_settimana, pattern=r'^class_history_select:'
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            classifica_mostra_corrente_totale,
            pattern=r'^class_show:(current|total):[a-z_]+$',
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            classifica_mostra_settimana,
            pattern=r'^class_week_show:[a-f0-9]+:[a-z_]+$',
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            classifica_legacy,
            pattern=(
                r'^(punti|vittorie|sconfitte|pareggi|gol_fatti|'
                r'gol_subiti|partite_giocate)$'
            ),
        )
    )

    logging.info("Bot avviato. In ascolto...")
    
    # Questo singolo comando avvia il bot e gestisce tutto internamente.
    application.run_polling()

if __name__ == "__main__":
    main()
