#!/usr/bin/env python3
import requests
import json
import time
import yaml
import paho.mqtt.client as mqtt
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any, Optional

class SterboxClient:
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.session = self._setup_session()
        self.mqtt_client = self._setup_mqtt()
        
        # Przygotowanie zapytań dla każdej sekcji
        self.sections = {}
        for section_name, variables in self.config['variables'].items():
            self.sections[section_name] = {
                'query': self._build_combined_query(variables),
                'variables': variables
            }
        
        self.base_url = f"http://{self.config['sterbox']['url']}/"
        self.auth_url = f"{self.base_url}u7.cgi?q0={self.config['sterbox']['password']}"
        
        # Inicjalizacja liczników błędów dla wszystkich zmiennych
        self.error_counters = {}
        for section in self.config['variables'].values():
            for var in section:
                self.error_counters[var] = 0
                
        self.MAX_RETRIES = 3
        self.auth_retry_delay = 1
        self.rest_delay = self.config['sterbox'].get('rest_delay', 0.1)
        self.debug = self.config.get('debug', False)
        
    def log(self, message: str):
        """Wyświetla wiadomość tylko jeśli debug jest włączony"""
        if self.debug:
            print(message)

    def _load_config(self, config_path: str = None) -> dict:
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)

    def _setup_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _setup_mqtt(self) -> mqtt.Client:
        client = mqtt.Client()
        client.username_pw_set(
            self.config['mqtt']['username'],
            self.config['mqtt']['password']
        )
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        return client

    def _on_connect(self, client, userdata, flags, rc):
        self.log(f"Connected to MQTT broker with result code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.log(f"Disconnected from MQTT broker with result code {rc}")
        if rc != 0:
            self.log("Unexpected disconnection. Attempting to reconnect...")
            self._connect_mqtt()

    def _build_combined_query(self, variables: dict) -> str:
        return ''.join(variables.values())

    def _authenticate(self) -> bool:
        try:
            response = self.session.get(self.auth_url, timeout=5)
            if response.status_code == 200:
                self.log("Successfully authenticated with Sterbox")
                return True
            else:
                self.log(f"Authentication failed with status code: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"Authentication error: {e}")
            return False

    def _wait_for_authentication(self) -> None:
        while True:
            self.log("Attempting to authenticate with Sterbox...")
            if self._authenticate():
                break
            self.log(f"Authentication failed, retrying in {self.auth_retry_delay} seconds...")
            time.sleep(self.auth_retry_delay)

    def _process_value(self, value: str, query: str, varname: str) -> Optional[float]:
        value = value.strip()
        
        if value != 'er':
            self.error_counters[varname] = 0
            
        try:
            if value == 'er':
                self.error_counters[varname] += 1
                if self.error_counters[varname] <= self.MAX_RETRIES:
                    self.log(f"Error value 'er' received for {varname}. Attempt {self.error_counters[varname]} of {self.MAX_RETRIES}")
                    return None
                self.log(f"Skipping variable {varname} after {self.MAX_RETRIES} failed attempts")
                return None
                
            value = value.replace(',', '.')
            if '@gcd' in query:
                return int(float(value))
            return float(value)
            
        except ValueError as e:
            self.error_counters[varname] += 1
            if self.error_counters[varname] <= self.MAX_RETRIES:
                self.log(f"Error processing value '{value}' for {varname}: {e}. Attempt {self.error_counters[varname]} of {self.MAX_RETRIES}")
                return None
            self.log(f"Skipping variable {varname} after {self.MAX_RETRIES} failed attempts")
            return None

    def _parse_response(self, response_text: str, section_vars: dict) -> Optional[Dict[str, Any]]:
        clean_response = response_text.strip('`')
        values = clean_response.split('`')
        
        if len(values) != len(section_vars):
            self.log(f"Warning: Received values count ({len(values)}) doesn't match variables count ({len(section_vars)})")
            return None
        
        data_dict = {}
        for (varname, query), value in zip(section_vars.items(), values):
            processed_value = self._process_value(value, query, varname)
            if processed_value is not None:
                data_dict[varname] = processed_value
                
        return data_dict if data_dict else None

    def _connect_mqtt(self):
        while True:
            try:
                self.mqtt_client.connect(
                    self.config['mqtt']['server'],
                    self.config['mqtt']['port']
                )
                self.mqtt_client.loop_start()
                break
            except Exception as e:
                self.log(f"Failed to connect to MQTT broker: {e}")
                self.log(f"Retrying MQTT connection in {self.auth_retry_delay} seconds...")
                time.sleep(self.auth_retry_delay)

    def _query_all_sections(self) -> Dict[str, Any]:
        """Pobiera dane ze wszystkich sekcji i zwraca spłaszczony słownik"""
        flattened_data = {}
        
        for section_name, section_data in self.sections.items():
            try:
                # Dodaj opóźnienie przed każdym zapytaniem (oprócz pierwszego)
                if flattened_data:  # jeśli nie jest to pierwsze zapytanie
                    time.sleep(self.rest_delay)
                
                # Zmierz czas zapytania
                request_start = time.time()
                
                response = self.session.get(self.base_url + section_data['query'], timeout=5)
                
                request_time = time.time() - request_start
                self.log(f"REST request for {section_name} took {request_time:.3f} seconds")
                
                if response.status_code != 200:
                    self.log(f"Error: HTTP status code {response.status_code}")
                    self._wait_for_authentication()
                    return {}
                    
                data_dict = self._parse_response(response.text, section_data['variables'])
                if data_dict:
                    # Dodaj dane bezpośrednio do głównego słownika zamiast zagnieżdżać
                    flattened_data.update(data_dict)
                    
            except Exception as e:
                self.log(f"Error during data retrieval for section {section_name}: {e}")
                return {}
                
        return flattened_data

    def run(self):
        """Główna zoptymalizowana pętla programu"""
        self.log("Starting program...")
        self._connect_mqtt()
        interval = self.config['sterbox'].get('interval', 1)
        
        self.log(f"Program started. Reading all sections every {interval} seconds...")
        self.log(f"REST delay between sections: {self.rest_delay} seconds")
        
        # Początkowe uwierzytelnienie
        self._wait_for_authentication()

        while True:
            start_time = time.time()
            
            # Pobierz spłaszczone dane
            combined_data = self._query_all_sections()
            
            # Jeśli mamy dane, wyślij je przez MQTT
            if combined_data:
                json_data = json.dumps(combined_data)
                # Publikuj w głównym temacie bez dopisku /all
                self.mqtt_client.publish(self.config['sterbox']['name'], json_data)
                self.log(f"Sent combined data: {json_data}")
            
            # Oblicz czas do następnego odpytania
            elapsed_time = time.time() - start_time
            sleep_time = max(0, interval - elapsed_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

def main():
    client = SterboxClient()
    client.run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"An error occurred: {e}")
