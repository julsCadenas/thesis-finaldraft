import numpy as np
import requests
import time
import os
from dotenv import load_dotenv

# load environmental variables
load_dotenv()

client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
thing_id = os.getenv('THING_ID')
# base_url = os.getenv('BASE_URL')
property_id_send = os.getenv('PROPERTY_ID_SEND_SMS')
property_id_receipt = os.getenv('PROPERTY_ID_RECIPIENT')
property_id_message = os.getenv('PROPERTY_ID_MESSAGE')
token_url = os.getenv('TOKEN_URL')
# cloud_api_url = os.getenv('CLOUD_API_URL')

# known temperature values for pixel values (for calibration)
# knownTemperature = np.array([0, 10, 20, 30, 32, 34, 35, 35.5, 36, 36.6, 37, 37.5, 38, 38.5, 39, 39.5, 40])
# pixelValues = np.array([0, 30, 100, 150, 200, 210, 220, 230, 240, 250, 260, 270, 280, 290, 300, 310, 320])

last_activation_time = 0

# function to load known temperatures from a txt file
def loadKnownTemperatures(filePath):
    try:
        with open(filePath, 'r') as file:
            return np.array([float(line.strip()) for line in file if line.strip()])
    except FileNotFoundError:
        print(f"File not found: {filePath}")
        return None

# function to load pixel values from a txt file
def loadPixelValues(filePath):
    try:
        with open(filePath, 'r') as file:
            return np.array([float(line.strip()) for line in file if line.strip()])
    except FileNotFoundError:
        print(f"File not found: {filePath}")
        return None

# Load known temperatures and pixel values from their respective files
knownTemperature = loadKnownTemperatures('known_temps.txt')
pixelValues = loadPixelValues('pixel_values.txt')

if knownTemperature is not None:
    print("Loaded knownTemperature:", knownTemperature)
else:
    print("Error loading known temperatures.")

if pixelValues is not None:
    print("Loaded pixelValues:", pixelValues)
else:
    print("Error loading pixel values.")
class AccessToken:
    def __init__(self):
        self.token = None
        self.expires_at = 0  # Unix timestamp

    def is_expired(self):
        return time.time() >= self.expires_at

    def set_token(self, token, expires_in):
        self.token = token
        self.expires_at = time.time() + expires_in

# Instantiate the AccessToken class
access_token_manager = AccessToken()

# numpy interpolation function to convert pixel value to temperature based on the calibration
def pixelToTemperature(pixelValue):
    return np.interp(pixelValue, pixelValues, knownTemperature)

# function/formula to calculate distance and effectively identify isolation
def euclideanDistance(point1, point2):
    return np.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

# get Arduino IoT cloud access token
def get_access_token():
    if access_token_manager.is_expired():
        data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'audience': 'https://api2.arduino.cc/iot'
        }
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_info = response.json()
            access_token_manager.set_token(token_info['access_token'], token_info['expires_in'])
            print("New Access Token:", access_token_manager.token)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching access token: {e}")
            return None
    return access_token_manager.token

def update_property(property_id, value):
    token = get_access_token()
    if not token:
        print("No access token available. Exiting.")
        return

    url = f"https://api2.arduino.cc/iot/v2/things/{thing_id}/properties/{property_id}/publish"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    data = {
        "value": value
    }

    response = requests.put(url, headers=headers, json=data)

    if response.status_code == 200:
        print(f"Property {property_id} updated successfully.")
    else:
        print(f"Failed to update property {property_id}. Status code: {response.status_code}")
        print(response.text)

last_sms_time = 0

# Function to send an SMS by updating the variables in the Cloud
def send_sms(recipient_number, message):
    global last_sms_time
    current_time = time.time()
    
    # Check if enough time has passed since the last SMS
    if current_time - last_sms_time < 30:
        print("SMS cooldown active. Please wait before sending another SMS.")
        return
    
    # Update recipient number and message in IoT Cloud
    print(recipient_number)
    update_property(property_id_receipt, recipient_number)
    update_property(property_id_message, message)

    # Trigger the SMS sending by setting the sendSMS property to True
    update_property(property_id_send, True)
    print("SMS send triggered!")
    
    last_sms_time = current_time

# buzzer activation
# def update_buzzer(state):
#     access_token = get_access_token()
#     url = f'{base_url}/things/{thing_id}/properties/{property_id}/publish'
#     data = {'value': state}
#     headers = {
#         'Authorization': f'Bearer {access_token}',
#         'Content-Type': 'application/json'
#     }
#     try:
#         response = requests.put(url, headers=headers, json=data)
#         response.raise_for_status()
#         print(f"Buzzer {'activated' if state else 'deactivated'}!")
#     except requests.exceptions.RequestException as e:
#         print(f"Error updating buzzer: {e}")

# def activate_buzzer():
#     update_buzzer(True)  # Activate the buzzer
#     time.sleep(3)  # Keep the buzzer on for 3 seconds
#     update_buzzer(False)  # Deactivate the buzzer

def control_relay(arduino, command):
    global last_activation_time
    current_time = time.time()  # Get the current time in seconds

    # Check if enough time has passed since the last activation
    if current_time - last_activation_time < 30:
        print("Relay is in cooldown. Please wait before sending another command.")
        return
    
    if arduino is None:
        print("Arduino connection is not established.")
        return

    if command == '1':
        arduino.write(b'1\n')  # Send 'ON' command to Arduino
        print("Relay is turned ON")
        last_activation_time = current_time  # Update the last activation time
    elif command == '0':
        arduino.write(b'0\n')  # Send 'OFF' command to Arduino
        print("Relay is turned OFF")
        last_activation_time = current_time  # Update the last activation time
    else:
        print("Invalid input. Please enter 1 to turn ON or 0 to turn OFF.")

# def send_sms(arduino, message, phoneNumber):
#     if message and phoneNumber:
#         command = f"SMS:{phoneNumber}:{message}\n"
#         arduino.write(command.encode())  # Send the SMS command to Arduino
#         print(f"Sent SMS to {phoneNumber}: {message}")
#     else:
#         print("Message cannot be empty.")
