import logging
import socket
import hashlib
import struct

_LOGGER = logging.getLogger(__name__)

class SSCPClient:
    #----------------------------------------------------------------
    def __init__(self, host, port, username, password, sscp_addres,name_plc):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password  
        self.sscp_address = int(sscp_addres, 16)  # Převedeme z HEX stringu na integer
        self.name_plc = name_plc        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.loggedin = False


    #----------------------------------------------------------------
    def connect(self):
        _LOGGER.debug("Connecting to SSCP server at %s:%d with SSCP address %d", self.host, self.port, self.sscp_address)
        self.socket.connect((self.host, self.port))
        self.connected = True
        _LOGGER.debug("Connected to SSCP server at %s:%d", self.host, self.port)


    #----------------------------------------------------------------
    def login(self):
        if not self.connected:
            raise Exception("Not connected to SSCP server.")
        
        _LOGGER.debug("Attempting to log in to SSCP server with SSCP address %d", self.sscp_address)
        username_bytes = self.username.encode('utf-8')
        password_hash = hashlib.md5(self.password.encode('utf-8')).digest()
        
        data_lenght = 6 + (len(username_bytes)) + (len(password_hash)) 
        _LOGGER.debug("Délka dat %d", data_lenght)
        frame = bytearray()
        frame.extend((self.sscp_address).to_bytes(1, 'big'))                #1
        frame.extend(b'\x01\x00')  # Login function ID                      #2  
        frame.extend((data_lenght).to_bytes(2, 'big'))  # Data length       #1
        frame.extend(b'\x17')  # Protocol version                           #1  6
        frame.extend(b'\x28\x00')  # Max data size                          #2  5
        frame.extend(len(username_bytes).to_bytes(1, 'big'))                #1  3  
        frame.extend(username_bytes)                                            
        frame.extend((len(password_hash)).to_bytes(1, 'big'))               #1  2
        frame.extend(password_hash)
        frame.extend(b'\x00')  # Přidáno SSCP ProxyID                       #1

        _LOGGER.debug("frame %s", frame.hex())

        self.socket.sendall(frame)
        response = self.socket.recv(1024)

        _LOGGER.debug("response frame %s", response.hex())
        
        if response[1:3] == b'\x81\x00':  # Successful login
            _LOGGER.info("Login successful.")
            self.loggedin = True
        else:
            _LOGGER.error("Login failed.")
            raise Exception("Login failed.")


    #----------------------------------------------------------------    
    def logout(self):
        self.ensure_connected()
        _LOGGER.debug("Attempting to log out from SSCP server with SSCP address %d", self.sscp_address)
        frame = bytearray()
        frame.extend((self.sscp_address).to_bytes(1, 'big'))
        frame.extend(b'\x01\x01')  # Logout function ID
        frame.extend(b'\x00\x00')  # Data length function 0 bytes
        _LOGGER.info("Logout successful.")


    #----------------------------------------------------------------
    def create_read_variables_request(self, uid_type, variables=[]):
        """
        Vytvoří rámec pro čtení proměnných v SSCP protokolu.
        Rámec obsahuje:
        - 01: SSCP adresa (1 byte)
        - 0500: Příkaz (2 byte)
        - Délka dat (2 byte)
        - Flags (1 byte)
        - UID (4 byte)
        - Offset (4 byte, pokud offset != 0)
        - Length (4 byte, pokud offset != 0)
        """
        # Inicializace rámce s adresou
        frame = bytearray()
        frame.extend((self.sscp_address).to_bytes(1, 'big'))  # SSCP adresa (1 byte)

        # Přidání příkazu (2 byte)
        frame.extend(struct.pack(">H", 0x0500))  # Příkaz čtení (0500)

        # Sestavení datové části
        data = bytearray()
        for variable in variables:
            uid = variable["uid"]  # UID (4 byte)
            offset = variable.get("offset", 0)  # Offset (4 byte, pokud přítomen)
            length = variable.get("length", 0)  # Length (4 byte, pokud přítomen)

            # Nastavení flags
            flags = 0x00
            if offset != 0:
                flags = 0x80  # Bit 4 (offset a length přítomné)

            # Přidání flags (1 byte)
            data.append(flags)

            # Přidání UID (4 byte)
            data.extend(struct.pack(">I", uid))  # UID jako 4 byte

            # Přidání offset (4 byte) a length (4 byte), pokud offset != 0
            if flags & 0x80:  # Pokud jsou offset a length přítomné
                data.extend(struct.pack(">I", offset))  # Offset jako 4 byte
                data.extend(struct.pack(">I", length))  # Length jako 4 byte

        # Výpočet délky dat (2 byte)
        data_length = len(data)
        if data_length > 65535:
            raise ValueError("Data length exceeds 2 byte limit")

        # Přidání délky dat (2 byte)
        frame.extend(struct.pack(">H", data_length))

        # Přidání datové části
        frame.extend(data)

        return frame

    #----------------------------------------------------------------
    def read_variable(self, uid, offset, length,type):   
        self.ensure_connected()
        try:                 
            _LOGGER.debug("Reading variable with UID %d", uid)
            _LOGGER.debug("Reading variable with offset %d", offset)
            _LOGGER.debug("Reading variable with length %d", length)
            _LOGGER.debug("Reading variable with type %s", type)
            _LOGGER.debug("SSCP Address: %s", self.sscp_address)
            # Vytvoření rámce pro čtení proměnné
            variables = [{'uid': uid, 'offset': offset, 'length': length}]
            frame = self.create_read_variables_request(0,variables=variables) 
            _LOGGER.debug("frame %s", frame.hex())
            # Odešleme rámce pro čtení proměnné
            self.socket.sendall(frame)
            # Přečteme odpověď pro čtení proměnné
            response_frame = self.socket.recv(1024)
            _LOGGER.debug("respframe %s", response_frame.hex())
            # Zpracujeme odpověď pro čtení proměnné a vrátíme hodnotu
            value = self.parse_response(response_frame,"read_variables",type)

            return value
        except BrokenPipeError:
            _LOGGER.error("Broken pipe detected. Attempting to reconnect.")
            self.reconnect()
            return self.read_variable(uid, offset, length, type)

    #----------------------------------------------------------------
    def write_variable(self, uid, value, offset=0, length=0, type_data="BYTE"):
        self.ensure_connected()
        try:
            """
            Zapíše hodnotu do proměnné na PLC.
            """
            _LOGGER.debug("Writing value %s to variable with UID %d", value, uid)

            # Inicializace rámce
            frame = bytearray()
            frame.extend((self.sscp_address).to_bytes(1, 'big'))  # Adresa PLC (1 byte)
            frame.extend(b'\x05\x10')  # Funkce zápisu (2 byte)

            # Nastavení flags
            flags = 0x00
            if offset > 0:
                flags |= 0x80  # Offset and Length fields are present

            # Přidání UID, offset, length a datové části
            data = bytearray()
            data.append(flags)  # Flags (1 byte)
            data.append(0x01)  # Počet proměnných (pro jednoduchost 1)
            data.extend(uid.to_bytes(4, 'big'))  # UID (4 byte)
            if flags & 0x80:
                data.extend(offset.to_bytes(4, 'big'))  # Offset (4 byte)
                data.extend(length.to_bytes(4, 'big'))  # Length (4 byte)

            # Přidání hodnoty podle typu
            if type_data.upper() == "BOOL":
                data.extend((1 if value else 0).to_bytes(1, 'big'))
            elif type_data.upper() == "BYTE":
                data.extend(int(value).to_bytes(1, 'big'))
            elif type_data.upper() == "WORD":
                data.extend(int(value).to_bytes(2, 'big', signed=False))
            elif type_data.upper() == "INT":
                data.extend(int(value).to_bytes(2, 'big', signed=True))
            elif type_data.upper() == "UINT":
                data.extend(int(value).to_bytes(2, 'big', signed=False))
            elif type_data.upper() == "DINT":
                data.extend(int(value).to_bytes(4, 'big', signed=True))
            elif type_data.upper() == "UDINT":
                data.extend(int(value).to_bytes(4, 'big', signed=False))
            elif type_data.upper() == "LINT":
                data.extend(int(value).to_bytes(8, 'big', signed=True))
            elif type_data.upper() == "REAL":
                data.extend(struct.pack(">f", float(value)))  # Float (4 byte)
            elif type_data.upper() == "LREAL":
                data.extend(struct.pack(">d", float(value)))  # Double (8 byte)
            else:
                raise ValueError(f"Unsupported type: {type_data}")

            # Výpočet délky dat
            data_length = len(data)
            if data_length > 65535:
                raise ValueError("Data length exceeds 2 byte limit")

            # Přidání délky dat do rámce (2 byte)
            frame.extend(struct.pack(">H", data_length))

            # Přidání dat do rámce
            frame.extend(data)

            _LOGGER.debug("Write frame: %s", frame.hex())

            # Odeslání rámce
            self.socket.sendall(frame)

            # Příjem odpovědi
            response = self.socket.recv(1024)
            _LOGGER.debug("Response frame: %s", response.hex())

            # Kontrola odpovědi
            if response[1:3] == b'\x85\x10':  # Úspěšný zápis
                _LOGGER.info("Write operation successful.")
            elif response[1:3] == b'\xc5\x10':  # Chyba při zápisu
                _LOGGER.error("Write operation failed.")
                raise Exception("Write operation failed.")
            else:
                _LOGGER.error("Unexpected function code in response: %s", response[1:3].hex())
                raise Exception("Unexpected function code in response.")
        except BrokenPipeError:
            _LOGGER.error("Broken pipe detected. Attempting to reconnect.")
            self.reconnect()
            return self.write_variable(uid, value, offset, length, type_data)
        except Exception as e:
            _LOGGER.error("Failed to write variable: %s", e)
            raise

    #----------------------------------------------------------------
    def parse_response(self, response, from_code, type_data=None):
        """
        Parsuje odpověď z protokolu SSCP pro různé funkce a datové typy.
        """
        _LOGGER.debug("Parsing response for function %s", from_code)
        _LOGGER.debug("Response raw data: %s", response.hex())

        # Ověření adresy
        if response[0] != self.sscp_address:
            _LOGGER.debug("Response address mismatch: Expected %s, got %s",
                        self.sscp_address, response[0])
            raise Exception("Response address mismatch")

        # Funkční kód
        function_code = response[1:3]

        match from_code:
            case "read_variables":
                if function_code == b'\x85\x00':  # Úspěšné čtení
                    _LOGGER.debug("Read operation successful")
                elif function_code == b'\xc5\x00':  # Chyba při čtení
                    _LOGGER.error("Read operation failed")
                    raise Exception("Read operation failed")
                else:
                    _LOGGER.error("Unexpected function code for read_variables: %s", function_code.hex())
                    raise Exception("Unexpected function code for read_variables")

                # Získání dat
                data_length = int.from_bytes(response[3:5], byteorder='big')
                raw_data = response[5:]
                if len(raw_data) != data_length:
                    _LOGGER.error("Mismatch between declared data length (%d) and actual length (%d)",
                                data_length, len(raw_data))
                    raise Exception("Data length mismatch")

                # Parsování dat podle typu
                value = self._parse_data(raw_data, type_data)
                return value

            case _:  # Neznámá funkce
                _LOGGER.error("Unknown function code: %s", function_code.hex())
                raise Exception("Unknown function code")

        return None

    def _parse_data(self, raw_data, type_data):
        """
        Parsuje data podle specifikovaného typu.
        """
        if type_data is not None:
            type_data = type_data.upper()  # Převod na velká písmena

        if type_data == "BOOL":
            if len(raw_data) != 1:
                raise ValueError("BOOL type expects 1 byte")
            return raw_data[0] != 0

        elif type_data == "BYTE":
            if len(raw_data) != 1:
                raise ValueError("BYTE type expects 1 byte")
            return raw_data[0]

        elif type_data == "WORD":
            if len(raw_data) != 2:
                raise ValueError("WORD type expects 2 bytes")
            return int.from_bytes(raw_data, byteorder="big", signed=False)

        elif type_data == "INT":
            if len(raw_data) != 2:
                raise ValueError("INT type expects 2 bytes")
            return int.from_bytes(raw_data, byteorder="big", signed=True)

        elif type_data == "UINT":
            if len(raw_data) != 2:
                raise ValueError("UINT type expects 2 bytes")
            return int.from_bytes(raw_data, byteorder="big", signed=False)

        elif type_data == "DINT":
            if len(raw_data) != 4:
                raise ValueError("DINT type expects 4 bytes")
            return int.from_bytes(raw_data, byteorder="big", signed=True)

        elif type_data == "UDINT":
            if len(raw_data) != 4:
                raise ValueError("UDINT type expects 4 bytes")
            return int.from_bytes(raw_data, byteorder="big", signed=False)

        elif type_data == "LINT":
            if len(raw_data) != 8:
                raise ValueError("LINT type expects 8 bytes")
            return int.from_bytes(raw_data, byteorder="big", signed=True)

        elif type_data == "REAL":
            if len(raw_data) != 4:
                raise ValueError("REAL type expects 4 bytes")
            return struct.unpack(">f", raw_data)[0]  # Float (4 byte)

        elif type_data == "LREAL":
            if len(raw_data) != 8:
                raise ValueError("LREAL type expects 8 bytes")
            return struct.unpack(">d", raw_data)[0]  # Double (8 byte)

        else:
            raise ValueError(f"Unsupported type: {type_data}")

    #----------------------------------------------------------------                
    def disconnect(self):
        if self.connected:
            _LOGGER.debug("Disconnecting from SSCP server")
            self.socket.close()
            self.connected = False
            _LOGGER.info("Disconnected from SSCP server")

    def reconnect(self):
        """Znovu se připojí k serveru."""
        try:
            self.disconnect()
            self.connect()
            self.login()
            _LOGGER.info("Reconnected to SSCP server.")
        except Exception as e:
            _LOGGER.error("Failed to reconnect: %s", e)
            raise
    
    def ensure_connected(self):
        """Zkontroluje, zda je spojení aktivní. Pokud není, pokusí se znovu připojit."""
        if not self.connected or not self.loggedin:
            _LOGGER.warning("Socket is not connected. Reconnecting...")
            self.reconnect()
    def reconnect(self):
        """Znovu připojí klienta k SSCP serveru."""
        try:
            _LOGGER.warning("Attempting to reconnect to SSCP server...")

            # Zavření stávajícího spojení, pokud je otevřené
            if self.connected:
                try:
                    self.socket.close()
                    _LOGGER.info("Existing connection closed.")
                except Exception as e:
                    _LOGGER.warning("Error while closing socket: %s", e)

            # Vytvoření nového socketu
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connected = False
            self.loggedin = False

            # Opětovné připojení
            self.connect()

            # Opětovné přihlášení
            self.login()

            _LOGGER.info("Reconnected to SSCP server successfully.")
        except Exception as e:
            _LOGGER.error("Failed to reconnect to SSCP server: %s", e)
            raise Exception("Reconnection failed") from e