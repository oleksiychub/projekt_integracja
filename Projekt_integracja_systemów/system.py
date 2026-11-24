"""
Integracja dwóch systemów: Sklep oraz Magazyn.

Każdy system ma własny serwer (Flask), własną bazę SQLite i własny log.
Zmiana produktu w jednym systemie jest od razu wysyłana do drugiego
przez REST API (POST /api/sync) z tokenem Bearer.
"""
import csv
import io
import json
import logging
import sqlite3

import requests
from flask import Flask, jsonify, redirect, render_template_string, request, url_for

TOKEN = "123"  # wspólny klucz API obu systemów
KONFIG = {}                # uzupełniane w sklep.py / magazyn.py
app = Flask(__name__)
log = logging.getLogger("integracja")


# Baza danych 

def baza(sql, parametry=()):
    """Wykonuje zapytanie SQL i zwraca wynik jako listę słowników."""
    polaczenie = sqlite3.connect(KONFIG["baza"])
    polaczenie.row_factory = sqlite3.Row
    wynik = [dict(wiersz) for wiersz in polaczenie.execute(sql, parametry)]
    polaczenie.commit()
    polaczenie.close()
    return wynik


def zapisz_produkt(p):
    baza("INSERT OR REPLACE INTO produkty VALUES (?, ?, ?, ?)",
         (p["kod"], p["nazwa"], p["cena"], p["ilosc"]))


# Sprawdzanie danych

def sprawdz(dane):
    """Sprawdza dane produktu. Przy złych danych rzuca ValueError."""
    try:
        produkt = {"kod": dane["kod"].strip(), "nazwa": dane["nazwa"].strip(),
                   "cena": float(dane["cena"]), "ilosc": int(dane["ilosc"])}
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError(f"niepoprawne dane produktu: {dane}")
    if not produkt["kod"] or not produkt["nazwa"]:
        raise ValueError(f"pusty kod lub nazwa: {dane}")
    return produkt


# Wysyłanie do drugiego systemu

def wyslij_do_partnera(produkt):
    """Wysyła produkt do drugiego systemu. Zwraca True, jeśli się udało."""
    partner = KONFIG["partner"]
    try:
        odpowiedz = requests.post(KONFIG["partner_url"] + "/api/sync", json=produkt,
                                  headers={"Authorization": TOKEN}, timeout=3)
        odpowiedz.raise_for_status()  # kod błędu (4xx/5xx) -> wyjątek
        log.info(f"WYSŁANO do {partner}: {produkt}")
        return True
    except requests.RequestException as blad:  # partner nie działa / zwrócił błąd
        log.error(f"BŁĄD wysyłania do {partner}: {type(blad).__name__}")
        return False


def zmien_produkt(dane):
    """Zmiana w TYM systemie: sprawdzenie, zapis w bazie, wysłanie do partnera."""
    produkt = sprawdz(dane)
    zapisz_produkt(produkt)
    log.info(f"ZMIANA: {produkt}")
    return wyslij_do_partnera(produkt)


# REST API 

@app.post("/api/sync")
def api_sync():
    """Drugi system przysyła nam zmieniony produkt."""
    if request.headers.get("Authorization") != TOKEN:
        log.warning("ODMOWA DOSTĘPU: brak lub zły token")
        return jsonify({"blad": "brak lub zły token"}), 401
    try:
        produkt = sprawdz(request.get_json(silent=True))
    except ValueError as blad:
        log.warning(f"BŁĘDNE DANE: {blad}")
        return jsonify({"blad": str(blad)}), 400

    zapisz_produkt(produkt)  # zapisujemy, ale NIE odsyłamy – inaczej dane krążyłyby w kółko
    log.info(f"ODEBRANO od {KONFIG['partner']}: {produkt}")
    return jsonify({"status": "ok"})


#Strona 

STRONA = """
<!doctype html>
<meta charset="utf-8">
<title>{{ nazwa }}</title>
<h1>{{ nazwa }}</h1>
<p><b>{{ komunikat }}</b></p>

<table border="1" cellpadding="5">
  <tr><th>Kod</th><th>Nazwa</th><th>Cena</th><th>Ilość</th></tr>
  {% for p in produkty %}
  <tr><td>{{ p.kod }}</td><td>{{ p.nazwa }}</td><td>{{ p.cena }}</td><td>{{ p.ilosc }}</td></tr>
  {% endfor %}
</table>

<h3>Dodaj lub zmień produkt</h3>
<form method="post" action="/zmien">
  Kod <input name="kod" size="5"> Nazwa <input name="nazwa">
  Cena <input name="cena" size="6"> Ilość <input name="ilosc" size="4">
  <button>Zapisz</button>
</form>

<h3>Import z pliku CSV lub JSON</h3>
<form method="post" action="/import" enctype="multipart/form-data">
  <input type="file" name="plik"> <button>Importuj</button>
</form>
"""


@app.get("/")
def strona():
    return render_template_string(STRONA, nazwa=KONFIG["nazwa"],
                                  produkty=baza("SELECT * FROM produkty ORDER BY kod"),
                                  komunikat=request.args.get("komunikat", ""))


@app.post("/zmien")
def strona_zmien():
    try:
        if zmien_produkt(request.form.to_dict()):
            komunikat = "Zapisano i wysłano do partnera."
        else:
            komunikat = "Zapisano, ale partner nie odpowiada (szczegóły w logu)."
    except ValueError as blad:
        komunikat = f"Błąd: {blad}"
    return redirect(url_for("strona", komunikat=komunikat))


@app.post("/import")
def strona_import():
    plik = request.files["plik"]
    try:
        tekst = plik.read().decode("utf-8-sig")
        if plik.filename.endswith(".csv"):
            wiersze = list(csv.DictReader(io.StringIO(tekst)))
        else:
            wiersze = json.loads(tekst)
    except ValueError as blad:  # zły JSON albo złe kodowanie pliku
        log.error(f"IMPORT: nie da się odczytać pliku {plik.filename}: {blad}")
        return redirect(url_for("strona", komunikat=f"Błąd pliku: {blad}"))

    zapisane, pominiete = 0, 0
    for wiersz in wiersze:
        try:
            zmien_produkt(wiersz)
            zapisane += 1
        except ValueError as blad:  # zły wiersz pomijamy, reszta idzie dalej
            pominiete += 1
            log.warning(f"IMPORT: pominięto wiersz: {blad}")
    log.info(f"IMPORT {plik.filename}: zapisano {zapisane}, pominięto {pominiete}")
    return redirect(url_for("strona", komunikat=f"Import: zapisano {zapisane}, pominięto {pominiete}."))


#Uruchomienie

def uruchom(**ustawienia):
    KONFIG.update(ustawienia)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(KONFIG["nazwa"].lower() + ".log", encoding="utf-8"),
                                  logging.StreamHandler()])
    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # ukrywamy techniczne komunikaty Flaska
    baza("CREATE TABLE IF NOT EXISTS produkty "
         "(kod TEXT PRIMARY KEY, nazwa TEXT, cena REAL, ilosc INTEGER)")
    log.info(f"START: {KONFIG['nazwa']} działa na http://127.0.0.1:{KONFIG['port']}")
    app.run(port=KONFIG["port"])
