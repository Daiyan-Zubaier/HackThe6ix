import speech_recognition as sr
import time
import serial
import serial.tools.list_ports

def find_arduino_port():
    """Find the Arduino serial port automatically"""
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        # Look for common ESP32 USB-to-Serial chips
        if "CP210" in port.description or "CH340" in port.description or "FTDI" in port.description:
            return port.device
    return None

def recognize_speech(arduino_serial=None):
    # Initialize recognizer
    recognizer = sr.Recognizer()
    
    # Use the default microphone as the audio source
    with sr.Microphone() as source:
        print("Adjusting for ambient noise, please wait...")
        # Adjust for ambient noise
        recognizer.adjust_for_ambient_noise(source, duration=1)
        
        print("Listening... (Speak now)")
        try:
            # Listen for speech input
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            print("Processing speech...")
            
            # Use Google's speech recognition
            text = recognizer.recognize_google(audio)
            
            print("You said: " + text)
            
            # If Arduino is connected, send the text
            if arduino_serial and arduino_serial.is_open:
                print("Sending to Arduino for TTS output...")
                arduino_serial.write((text + '\n').encode())
                
            return text
            
        except sr.WaitTimeoutError:
            print("No speech detected within timeout period")
            return None
        except sr.UnknownValueError:
            print("Could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None

def main():
    print("Speech to Text to Arduino TTS Converter")
    print("---------------------------------------")
    
    # Try to find Arduino port automatically
    arduino_port = find_arduino_port()
    if arduino_port:
        print(f"Arduino found on port: {arduino_port}")
    else:
        print("Arduino not found automatically.")
        arduino_port = input("Please enter Arduino COM port (e.g., COM3 or /dev/ttyUSB0): ")
    
    # Connect to Arduino
    try:
        arduino_serial = serial.Serial(arduino_port, 115200, timeout=1)
        print(f"Connected to Arduino on {arduino_port}")
        # Wait for Arduino to reset after connection
        time.sleep(2)
    except Exception as e:
        print(f"Error connecting to Arduino: {e}")
        print("Running in offline mode (speech recognition only)")
        arduino_serial = None
    
    print("\nThis program will convert your speech to text and send it to the Arduino.")
    print("The Arduino will then convert the text to speech using its TTS module.")
    print("Press Ctrl+C to exit the program.")
    
    try:
        while True:
            print("\n" + "="*50)
            text = recognize_speech(arduino_serial)
            
            if text:
                print(f"Recognized text: {text}")
                if arduino_serial is None:
                    print("(Arduino not connected - text not sent)")
            
            choice = input("\nPress Enter to continue or type 'exit' to quit: ")
            if choice.lower() == 'exit':
                break
                
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    finally:
        # Close the serial connection if it's open
        if 'arduino_serial' in locals() and arduino_serial and arduino_serial.is_open:
            arduino_serial.close()
            print("Arduino connection closed.")

if __name__ == "__main__":
    main() 