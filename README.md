# Sterbox MQTT Gateway
## Opis projektu

Program służy jako pomost (gateway) pomiędzy urządzeniem Sterbox a systemem MQTT. Umożliwia odczyt danych z urządzenia Sterbox i publikowanie ich do brokera MQTT, co pozwala na integrację z systemami automatyki domowej.

## Wymagania systemowe

- Python 3.6 lub nowszy
- System operacyjny: Debian/Ubuntu
- Dostęp do sieci lokalnej
- Urządzenie Sterbox podłączone do sieci lokalnej
- Broker MQTT (np. Mosquitto)

## Instalacja zależności

1. Zainstaluj Python 3

2. Zainstaluj wymagane biblioteki Python przy pomocy apt:

sudo apt update
sudo apt install python3-pip
sudo apt install python3-requests python3-paho-mqtt python3-yaml

Opcjonalnie, jeśli chcesz uruchamiać skrypt jako usługę systemową, zainstaluj:
sudo apt install python3-systemd

## Konfiguracja

Program konfiguruje się poprzez plik `config.yml`. Oto opis poszczególnych sekcji:

### Konfiguracja MQTT:

mqtt:
  server: "10.1.0.25"    # Adres IP brokera MQTT
  port: 1883             # Port MQTT (domyślnie 1883)
  username: "mqtt"       # Nazwa użytkownika MQTT
  password: "mqtt1234"   # Hasło MQTT


### Konfiguracja Sterbox:

sterbox:
  name: "sterbox2"       # Nazwa urządzenia Sterbox oraz topic
  url: "xxxxxxxxxx"      # Adres IP urządzenia Sterbox
  password: "1234"       # Hasło do urządzenia Sterbox
  interval: 1            # Interwał odczytu danych (w sekundach)


### Ustawienia debugowania:

debug: false             # Wyłączenie (false) lub włączenie (true) informacji debugowania


### Konfiguracja zmiennych:

variables:
  parm1:
    tempk: "@gca?temp_k&"
    stat24dn: "@gcd?stat24dn&"
    stat24up: "@gcd?stat24up&"
  parm2:
    RO21: "@gcd?RO21up&"
    RO22: "@gcd?RO22up&"


## Jak uruchomić

1. Skopiuj plik konfiguracyjny `config.yml` do katalogu z programem
2. Dostosuj parametry w pliku konfiguracyjnym do swojego środowiska
3. Uruchom program komendą:

python3 sterbox_mqtt.py


## Działanie programu

1. Po uruchomieniu program:
   - Nawiązuje połączenie z brokerem MQTT
   - Łączy się z urządzeniem Sterbox
   - Rozpoczyna cykliczne odczytywanie danych według ustawionego interwału

2. Dla każdej skonfigurowanej zmiennej:
   - Odczytuje wartość z urządzenia Sterbox
   - Publikuje odczytaną wartość do MQTT w temacie: `sterbox2/[nazwa_parametru]`

3. W przypadku włączonego debugowania (`debug: true`):
   - Wyświetla informacje o połączeniu
   - Pokazuje odczytane wartości
   - Informuje o publikacji do MQTT

## Rozwiązywanie problemów

1. Problem z połączeniem MQTT:
   - Sprawdź, czy broker MQTT jest uruchomiony
   - Zweryfikuj poprawność adresu IP i portu
   - Sprawdź nazwę użytkownika i hasło

2. Problem z połączeniem Sterbox:
   - Sprawdź, czy urządzenie jest dostępne w sieci (ping)
   - Zweryfikuj poprawność adresu IP
   - Sprawdź hasło do urządzenia

3. Brak odczytów:
   - Włącz tryb debug (`debug: true`)
   - Sprawdź logi programu
   - Zweryfikuj poprawność zdefiniowanych zmiennych

## Wsparcie

W przypadku problemów:
Przejrzyj logi z włączonym trybem debug :)



Automatyczne rozpoznawanie typu zmiennej na podstawie '@gca' lub '@gcd' w zapytaniu
Dla zmiennych cyfrowych (@gcd) zwracane są wartości całkowite (0 lub 1)
Dla zmiennych analogowych (@gca) zwracane są wartości zmiennoprzecinkowe

Program będzie wyświetlać informacje na konsoli tylko wtedy, gdy debug jest ustawione na true. Jedynie krytyczne błędy (np. przerwanie programu przez użytkownika) będą zawsze wyświetlane.


Obsługa wielu sekcji zmiennych w konfiguracji
Każda sekcja jest odpytywana osobno
Po każdym odpytaniu sekcji następuje wysyłka MQTT
Dane z każdej sekcji są wysyłane na osobny topic MQTT (np. sterbox2/zmienna1, sterbox2/zmienna2)
Zachowany został interwał 1s między odpytaniami
Program zachowuje pełną funkcjonalność obsługi błędów i ponownego uwierzytelniania

Program będzie odpytywał sekcje po kolei, wysyłając dane MQTT po każdym udanym odpytaniu, zachowując zadany interwał między odpytaniami.

-------------------

