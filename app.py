import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")


@app.errorhandler(Exception)
def handle_error(e):
    msg = str(e)
    if "429" in msg or "quota" in msg.lower():
        fehler = "⚠️ API-Limit erreicht. Bitte kurz warten und nochmal versuchen."
    elif "401" in msg or "403" in msg or "API_KEY" in msg.upper():
        fehler = "⚠️ API-Key ungültig. Bitte Administrator informieren."
    else:
        fehler = f"⚠️ Fehler: {msg[:200]}"
    return render_template("fehler.html", fehler=fehler), 500

DB_PATH = os.environ.get("DB_PATH", "favoriten.db")


def db_init():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS favoriten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT,
            titel TEXT,
            inhalt TEXT,
            erstellt_am TEXT
        )""")


db_init()


def db_speichern(typ, titel, inhalt):
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO favoriten (typ, titel, inhalt, erstellt_am) VALUES (?,?,?,?)",
            (typ, titel, inhalt, datetime.now().isoformat()),
        )


def db_alle():
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        return con.execute("SELECT * FROM favoriten ORDER BY erstellt_am DESC").fetchall()


def db_loeschen(fav_id):
    with sqlite3.connect(DB_PATH) as con:
        con.execute("DELETE FROM favoriten WHERE id=?", (fav_id,))

SYSTEM_PROMPT = """Du bist ein Assistent für eine Primarlehrerin der 1. Klasse (6-7-jährige Kinder, Schweiz, Lehrplan 21).
Du erstellst altersgerechte, praxisnahe Unterrichtsmaterialien auf Deutsch.
Bei Arbeitsblättern: klare Aufgaben, grosse Schrift, immer Name- und Datumszeile oben.
Formatiere deine Ausgabe übersichtlich mit Markdown."""


def frage_ki(prompt):
    key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={key}"
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2048},
    }
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/themen")
def themen():
    with open("themen.json", encoding="utf-8") as f:
        daten = json.load(f)
    return render_template("themen.html", themen=daten)


@app.route("/favoriten")
def favoriten():
    return render_template("favoriten.html", favoriten=db_alle())


@app.route("/favoriten/speichern", methods=["POST"])
def favorit_speichern():
    db_speichern(
        request.form.get("typ"),
        request.form.get("titel"),
        request.form.get("inhalt"),
    )
    return redirect(url_for("favoriten"))


@app.route("/favoriten/loeschen/<int:fav_id>")
def favorit_loeschen(fav_id):
    db_loeschen(fav_id)
    return redirect(url_for("favoriten"))


@app.route("/arbeitsblatt", methods=["GET", "POST"])
def arbeitsblatt():
    if request.method == "POST":
        fach = request.form.get("fach")
        thema = request.form.get("thema")
        aufgaben = request.form.get("aufgaben", "6")
        schwierigkeit = request.form.get("schwierigkeit", "mittel")
        extras = request.form.get("extras", "")

        prompt = f"""Erstelle ein druckfertiges Arbeitsblatt für die 1. Klasse (Schweiz).

Fach: {fach}
Thema: {thema}
Anzahl Aufgaben: {aufgaben}
Schwierigkeit: {schwierigkeit}
Besonderes: {extras if extras else 'nichts'}

Format:
- Name-Zeile und Datum-Zeile oben
- Klare, einfache Anweisungen (max. 1-2 Sätze pro Aufgabe)
- Altersgerecht für 6-7-Jährige
- Am Ende: Smiley-Bewertung (😊 😐 😔)
- Formatiere es übersichtlich mit Markdown"""

        result = frage_ki(prompt)
        return render_template("arbeitsblatt.html", result=result, form=request.form)
    return render_template("arbeitsblatt.html", result=None)


@app.route("/lektionsplan", methods=["GET", "POST"])
def lektionsplan():
    if request.method == "POST":
        fach = request.form.get("fach")
        thema = request.form.get("thema")
        dauer = request.form.get("dauer", "45")
        lernziele = request.form.get("lernziele", "")

        prompt = f"""Erstelle einen detaillierten Lektionsplan für die 1. Klasse (Schweiz, Lehrplan 21).

Fach: {fach}
Thema: {thema}
Dauer: {dauer} Minuten
Lernziele: {lernziele if lernziele else 'passend zum Thema'}

Struktur:
- **Einstieg** (5-10 Min): Motivation, Vorkenntnisse aktivieren
- **Hauptteil** (Hauptteil der Zeit): Neue Inhalte, Übungen, Aktivitäten
- **Abschluss** (5 Min): Zusammenfassung, Reflexion
- Materialien und Hilfsmittel
- Hinweise zur Differenzierung (für schnellere und langsamere Kinder)"""

        result = frage_ki(prompt)
        return render_template("lektionsplan.html", result=result, form=request.form)
    return render_template("lektionsplan.html", result=None)


@app.route("/wochenplan", methods=["GET", "POST"])
def wochenplan():
    if request.method == "POST":
        kw = request.form.get("kw", "")
        schwerpunkt = request.form.get("schwerpunkt", "")
        faecher = request.form.getlist("faecher")

        prompt = f"""Erstelle einen Wochenplan für eine 1. Klasse (Schweiz).

Kalenderwoche: {kw if kw else 'aktuelle'}
Wochenschwerpunkt: {schwerpunkt if schwerpunkt else 'kein spezieller'}
Fächer: {', '.join(faecher) if faecher else 'Deutsch, Mathe, Sachkunde, Sport, Kreatives Gestalten'}

Erstelle eine übersichtliche Tabelle (Montag-Freitag) mit:
- Lernzielen pro Fach
- Kurzen Aktivitätsbeschreibungen
- Hinweisen zu Hausaufgaben falls sinnvoll"""

        result = frage_ki(prompt)
        return render_template("wochenplan.html", result=result, form=request.form)
    return render_template("wochenplan.html", result=None)


@app.route("/elternbrief", methods=["GET", "POST"])
def elternbrief():
    if request.method == "POST":
        anlass = request.form.get("anlass")
        datum = request.form.get("datum", "")
        details = request.form.get("details", "")
        rueckmeldung = request.form.get("rueckmeldung", "nein")

        prompt = f"""Schreibe einen freundlichen Elternbrief für eine 1. Klasse (Schweiz).

Anlass: {anlass}
Datum/Termin: {datum if datum else 'kein spezifisches Datum'}
Details: {details if details else 'keine weiteren Details'}
Rückmeldung der Eltern nötig: {rueckmeldung}

Format:
- Kurzer, freundlicher Brief (max. 1 Seite)
- Datum und Klasse oben
- Klare, einfache Sprache
- Professionelle Grussformel
- Falls Rückmeldung nötig: Talon/Abschnitt am Ende"""

        result = frage_ki(prompt)
        return render_template("elternbrief.html", result=result, form=request.form)
    return render_template("elternbrief.html", result=None)


@app.route("/aktivitaeten", methods=["GET", "POST"])
def aktivitaeten():
    if request.method == "POST":
        ort = request.form.get("ort", "drinnen")
        thema = request.form.get("thema", "")
        anzahl = request.form.get("anzahl", "5")
        typ = request.form.get("typ", "gemischt")

        prompt = f"""Gib mir {anzahl} kreative Aktivitäts- und Spielideen für eine 1. Klasse (6-7 Jahre, Schweiz).

Ort: {ort}
Thema/Bezug: {thema if thema else 'kein spezielles Thema'}
Art der Aktivität: {typ}

Für jede Idee:
- **Name der Aktivität**
- Kurze Beschreibung (2-3 Sätze)
- Was wird benötigt (Material)
- Dauer ca.
- Lernwert / Ziel"""

        result = frage_ki(prompt)
        return render_template("aktivitaeten.html", result=result, form=request.form)
    return render_template("aktivitaeten.html", result=None)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
