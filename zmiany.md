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
