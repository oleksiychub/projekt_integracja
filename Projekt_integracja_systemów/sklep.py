# System A – SKLEP.  Start: python sklep.py  ->  http://127.0.0.1:5001
import system

system.uruchom(nazwa="Sklep", port=5001, baza="sklep.db",
               partner="Magazyn", partner_url="http://127.0.0.1:5002")
