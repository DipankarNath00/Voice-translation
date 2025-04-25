from flask import Flask, after_this_request, render_template, request, jsonify, send_file, abort
import speech_recognition as sr
from gtts import gTTS
import os
import uuid
from deep_translator import GoogleTranslator
from cryptography.fernet import Fernet, InvalidToken
import smtplib
import requests
import time
from threading import Thread

app = Flask(__name__)

# Ensure the correct folder for audio files
audio_folder = os.path.join(os.getcwd(), 'translator', 'audio')
if not os.path.exists(audio_folder):
    os.makedirs(audio_folder)

app.config['UPLOAD_FOLDER'] = audio_folder

# Language map including Indian and overseas languages
language_map = {
    'Hindi': 'hi',
    'Bengali': 'bn',
    'Tamil': 'ta',
    'Telugu': 'te',
    'Gujarati': 'gu',
    'Marathi': 'mr',
    'Kannada': 'kn',
    'Malayalam': 'ml',
    'Punjabi': 'pa',
    'Odia': 'or',
    'Urdu': 'ur',
    'French': 'fr',
    'Spanish': 'es',
    'German': 'de',
    'Italian': 'it',
    'Russian': 'ru',
    'Chinese (Simplified)': 'zh-CN',
    'Japanese': 'ja',
    'Korean': 'ko',
    'Arabic': 'ar',
    'Portuguese': 'pt',
}

def get_location():
    try:
        res = requests.get("https://ipinfo.io").json()
        return f"Location: {res.get('city')}, {res.get('region')}, {res.get('country')}"
    except Exception:
        return "Location not available."

def async_send_email(location_info):
    def send():
        sender_email = "projectworkgroup51@gmail.com"
        receiver_email = "er.dipayanlodh@gmail.com"
        password = "obpy txyg ywzl ieqd"
        subject = "Military Mode Activated"
        body = f"Military Mode Alert!\n\n{location_info}"

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, password)
                message = f"Subject: {subject}\n\n{body}"
                server.sendmail(sender_email, receiver_email, message)
        except Exception as e:
            print(f"Email failed: {e}")
    Thread(target=send).start()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/translate')
def translate_page():
    return render_template('translate.html')

@app.route('/translate', methods=['POST'])
def translate():
    data = request.get_json()
    language = data.get('language', 'Hindi')
    military = data.get('military', False)
    enc_key = data.get('encKey', '')
    dec_key = data.get('decKey', '')
    cipher = None

    if military:
        if not enc_key or not dec_key:
            return jsonify({"error": "Encryption and Decryption keys are required."}), 400
        if enc_key != dec_key:
            return jsonify({"error": "Encryption and Decryption keys do not match."}), 400
        try:
            cipher = Fernet(enc_key.encode())
            location_info = get_location()
            async_send_email(location_info)
        except Exception:
            return jsonify({"error": "Invalid encryption key."}), 400

    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        try:
            print("Listening...")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            english_text = recognizer.recognize_google(audio).lower()
        except Exception:
            return jsonify({"error": "Speech not recognized."}), 400

    try:
        target_lang_code = language_map.get(language, 'hi')
        translated = GoogleTranslator(source='en', target=target_lang_code).translate(english_text)

        unique_filename = str(uuid.uuid4()) + ".mp3"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        tts = gTTS(text=translated, lang=target_lang_code)
        tts.save(file_path)

        # Auto-delete the file after a short period even if user doesn't play
        def delete_later(path):
            time.sleep(30)  # Auto-delete after 30s
            try:
                if os.path.exists(path):
                    os.remove(path)
                    print(f"[Auto-delete] Deleted file: {path}")
            except Exception as e:
                print(f"[Auto-delete] Error: {e}")

        Thread(target=delete_later, args=(file_path,)).start()

        if military and cipher:
            with open(file_path, "rb") as f:
                raw_data = f.read()
            encrypted = cipher.encrypt(raw_data)
            encrypted_file_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp_encrypted.dat")
            with open(encrypted_file_path, "wb") as ef:
                ef.write(encrypted)

            decrypted = cipher.decrypt(encrypted)
            with open(file_path, "wb") as df:
                df.write(decrypted)

            os.remove(encrypted_file_path)

    except InvalidToken:
        return jsonify({"error": "Decryption failed."}), 400
    except Exception as e:
        return jsonify({"error": f"Translation/audio failed: {str(e)}"}), 500

    return jsonify({
        "message": f"Translated to {language}",
        "original": english_text,
        "translated": translated,
        "audio": f"/play/{unique_filename}"
    })

@app.route('/play/<filename>')
def play(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        return abort(404, description="Audio file not found")

    @after_this_request
    def remove_file(response):
        def delete():
            time.sleep(5)  # Short buffer to allow audio playback
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted file after playback: {file_path}")
            except Exception as e:
                print(f"Error deleting file: {e}")
        Thread(target=delete).start()
        return response

    return send_file(file_path, mimetype="audio/mp3")

if __name__ == '__main__':
    app.run(debug=True)
