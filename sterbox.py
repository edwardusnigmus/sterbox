# sterbox_client.py
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
from urllib3.exceptions import ProtocolError
from requests.exceptions import RequestException

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
        self.connection_retry_count = 0
        self.MAX_CONNECTION_RETRIES = self.config['sterbox'].get('max_connection_retries', 5)
        self.connection_retry_delay = self.config['sterbox'].get('connection_retry_delay', 5)
        
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
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _reset_session(self):
        """Resetuje sesję HTTP w przypadku problemów z połączeniem"""
        self.log("Resetting HTTP session...")
        self.session = self._setup_session()
        
    def _check_connection(self) -> bool:
        """Sprawdza połączenie z urządzeniem i próbuje je przywrócić w razie potrzeby"""
        try:
            response = self.session.get(self.base_url, timeout=5)
            if response.status_code == 200:
                self.connection_retry_count = 0
                return True
        except Exception as e:
            self.log(f"Connection check failed: {e}")
            
        if self.connection_retry_count < self.MAX_CONNECTION_RETRIES:
            self.connection_retry_count += 1
            self.log(f"Connection attempt {self.connection_retry_count} of {self.MAX_CONNECTION_RETRIES}")
            self._reset_session()
            time.sleep(self.connection_retry_delay)
            return self._authenticate()
        
        self.log("Max connection retries exceeded")
        return False

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
                self.connection_retry_count = 0
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

    def _handle_connection_error(self, section_name: str, error: Exception) -> bool:
        """Obsługuje błędy połączenia i próbuje je naprawić"""
        self.log(f"Connection error in section {section_name}: {error}")
        
        if isinstance(error, (ProtocolError, RequestException)):
            if self._check_connection():
                self.log("Connection restored successfully")
                return True
            else:
                self.log("Failed to restore connection")
                return False
        return False

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

    def _query_section(self, section_name: str, section_data: dict) -> Optional[Dict[str, Any]]:
        """Pobiera dane z pojedynczej sekcji"""
        try:
            request_start = time.time()
            
            response = self.session.get(self.base_url + section_data['query'], timeout=5)
            
            request_time = time.time() - request_start
            self.log(f"REST request for {section_name} took {request_time:.3f} seconds")
            
            if response.status_code != 200:
                self.log(f"Error: HTTP status code {response.status_code}")
                if self._wait_for_authentication():
                    return None
                return None
                
            data_dict = self._parse_response(response.text, section_data['variables'])
            return data_dict
                
        except (ProtocolError, RequestException) as e:
            if self._handle_connection_error(section_name, e):
                return None
            return None
            
        except Exception as e:
            self.log(f"Error during data retrieval for section {section_name}: {e}")
            return None

    def run(self):
        """Zoptymalizowana główna pętla programu"""
        self.log("Starting program...")
        self._connect_mqtt()
        interval = self.config['sterbox'].get('interval', 1)
        
        self.log(f"Program started. Reading sections with {self.rest_delay}s delay between them")
        self.log(f"Publishing combined data every {interval} seconds")
        
        # Początkowe uwierzytelnienie
        self._wait_for_authentication()

        combined_data = {}
        last_publish_time = time.time()

        while True:
            sections_count = len(self.sections)
            
            # Iteruj przez wszystkie sekcje oprócz ostatniej
            for i, (section_name, section_data) in enumerate(self.sections.items()):
                section_result = self._query_section(section_name, section_data)
                
                if section_result:
                    combined_data.update(section_result)
                    self.log(f"Updated data from section {section_name}: {section_result}")
                
                # Zastosuj rest_delay tylko między sekcjami, nie po ostatniej sekcji
                if i < sections_count - 1 and self.rest_delay > 0:
                    time.sleep(self.rest_delay)
            
            current_time = time.time()
            # Sprawdź, czy minął interval od ostatniej publikacji
            if current_time - last_publish_time >= interval and combined_data:
                json_data = json.dumps(combined_data)
                self.mqtt_client.publish(self.config['sterbox']['name'], json_data)
                self.log(f"Published combined data: {json_data}")
                last_publish_time = current_time
                combined_data = {}  # Wyczyść dane po publikacji
            
            # Oblicz czas do następnej publikacji
            time_to_next_publish = max(0, interval - (time.time() - last_publish_time))
            
            # Czekaj tylko jeśli jest to konieczne
            if time_to_next_publish > 0:
                time.sleep(min(time_to_next_publish, self.rest_delay))

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
