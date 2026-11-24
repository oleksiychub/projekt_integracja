# Integracja systemów: Sklep i Magazyn 

Dwie aplikacje – **Sklep** i **Magazyn** – mają własne serwery, własne bazy SQLite i własne logi.
Zmiana produktu w jednej aplikacji jest od razu wysyłana do drugiej przez REST API.

## Uruchomienie

pip install -r requirements.txt

python sklep.py      # terminal 1  ->  http://127.0.0.1:5001

python magazyn.py    # terminal 2  ->  http://127.0.0.1:5002

## Sprawdzenie złych tokenów i dannych

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5002/api/sync

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5002/api/sync -Headers @{Authorization="Bearer 123"} -ContentType "application/json" -Body '{"kod": "X1"}'
