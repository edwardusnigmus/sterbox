v.1.0.2
Główne zmiany w stosunku do poprzedniej wersji:
Zoptymalizowana logika czekania na kolejne zapytania:
Nie ma już zbędnego opóźnienia po ostatniej sekcji
Program czeka tylko minimalny wymagany czas przed następnym cyklem
Zoptymalizowana struktura pętli głównej:
Wcześniejsze sprawdzanie liczby sekcji
Bardziej efektywne zarządzanie czasem między publikacjami

Poprawiona obsługa interwałów:
Precyzyjniejsze obliczanie czasu do następnej publikacji
Minimalizacja opóźnień między cyklami odczytu

Nowe zmienne:
rest_delay - kontroluje czas między pobieraniem kolejnych sekcji danych
interval - kontroluje jak często całość zebranych danych jest publikowana przez MQTT

v.1.0.1

Główne zmiany, które zostały wprowadzone:

W metodzie _query_all_sections zmieniłem sposób zbierania danych - teraz wszystkie wartości są dodawane do jednego płaskiego słownika zamiast tworzenia struktury zagnieżdżonej.
Zmodyfikowałem temat MQTT - teraz dane są publikowane bezpośrednio w temacie głównym (np. "sterbox2") zamiast z dopiskiem "/all".
Zachowałem całą logikę obsługi błędów, retry i pozostałe funkcjonalności.

Teraz, przy konfiguracji z przykładu, dane będą wysyłane w formacie:
```json
{
  "tempk": 22,
  "stat24dn": 0,
  "stat24up": 1,
  "RO21": 0,
  "RO22": 1
}
```
