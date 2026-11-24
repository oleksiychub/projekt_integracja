# System B – MAGAZYN.  Start: python magazyn.py  ->  http://127.0.0.1:5002
import system

system.uruchom(nazwa="Magazyn", port=5002, baza="magazyn.db",
               partner="Sklep", partner_url="http://127.0.0.1:5001")
