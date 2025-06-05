from flask import Flask, after_this_request, render_template, request, jsonify, send_file, abort, redirect, url_for, flash
import speech_recognition as sr
from gtts import gTTS
import os
import uuid
from deep_translator import GoogleTranslator
import requests
import time
from threading import Thread
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField, FileField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from flask_wtf.file import FileAllowed
from dotenv import load_dotenv, find_dotenv
from datetime import datetime
from werkzeug.utils import secure_filename
import bcrypt
from security import init_app
from google.cloud import texttospeech
from routes.security_routes import security_bp
from cryptography.fernet import InvalidToken
import json
from flask_migrate import Migrate
from supabase import create_client, Client
import smtplib

# --- NEW Imports --- 
from google.cloud import speech
from google.cloud import translate_v2 as translate # Use v2 for simplicity

import yt_dlp
from yt_dlp.utils import DownloadError
from pydub import AudioSegment # <-- Import pydub

# --- Load .env --- 
print("--- Attempting to load .env file ---")
# Use find_dotenv() to explicitly locate the file and check existence
dotenv_path = find_dotenv()
if dotenv_path:
    print(f"--- Found .env file at: {dotenv_path} ---")
    # Load verbosely, override existing vars if needed
    loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True)
    print(f"--- load_dotenv() returned: {loaded} ---")
else:
    print("--- WARNING: .env file not found! --- ")

# --- Explicitly Check Environment Variables --- 
db_url_from_env = os.getenv('DATABASE_URL')
print(f"--- Value of os.getenv('DATABASE_URL'): {db_url_from_env} ---")
gcp_creds_from_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
print(f"--- Value of os.getenv('GOOGLE_APPLICATION_CREDENTIALS'): {gcp_creds_from_env} ---")
gcs_bucket_from_env = os.getenv('GCS_BUCKET_NAME')
print(f"--- Value of os.getenv('GCS_BUCKET_NAME'): {gcs_bucket_from_env} ---")


# --- Language Map ---
# Define supported languages (code -> name)
language_map = {
    # Indian Languages
    'hi-IN': 'Hindi',
    'bn-IN': 'Bengali',
    'ta-IN': 'Tamil',
    'te-IN': 'Telugu',
    'mr-IN': 'Marathi',
    'gu-IN': 'Gujarati',
    'kn-IN': 'Kannada',
    'ml-IN': 'Malayalam',
    'pa-IN': 'Punjabi',
    'or-IN': 'Odia',
    'as-IN': 'Assamese',
    'ur-IN': 'Urdu',
    # International Languages
    'en-US': 'English',
    'es-ES': 'Spanish',
    'fr-FR': 'French',
    'de-DE': 'German',
    'it-IT': 'Italian',
    'pt-BR': 'Portuguese',
    'nl-NL': 'Dutch',
    'ru-RU': 'Russian',
    'ja-JP': 'Japanese',
    'ko-KR': 'Korean',
    'zh-CN': 'Chinese',
    'ar-SA': 'Arabic'
}

# --- Import the new YouTube processing function ---
from youtube_feature import process_youtube_video

# --- Load .env --- 
print("--- Attempting to load .env file ---")
# Use find_dotenv() to explicitly locate the file and check existence
dotenv_path = find_dotenv()
if dotenv_path:
    print(f"--- Found .env file at: {dotenv_path} ---")
    # Load verbosely, override existing vars if needed
    loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True)
    print(f"--- load_dotenv() returned: {loaded} ---")
else:
    print("--- WARNING: .env file not found! --- ")

# --- Explicitly Check DATABASE_URL --- 
db_url_from_env = os.getenv('DATABASE_URL')
print(f"--- Value of os.getenv('DATABASE_URL'): {db_url_from_env} ---")

gcp_creds_from_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
print(f"--- Value of os.getenv('GOOGLE_APPLICATION_CREDENTIALS'): {gcp_creds_from_env} ---")


# --- GCS Bucket Configuration ---
GCS_BUCKET_NAME_FROM_ENV = os.getenv('GCS_BUCKET_NAME')
print(f"--- Value of os.getenv('GCS_BUCKET_NAME'): {GCS_BUCKET_NAME_FROM_ENV} ---")

# --- TTS Timeout Configuration ---


# --- App Initialization and Configuration ---
app = Flask(__name__, instance_relative_config=True)

# Set secret key for CSRF protection
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-please-change-in-production')

# Set GCS bucket name and verify configuration
app.config['GCS_BUCKET_NAME'] = os.getenv('GCS_BUCKET_NAME')
if not app.config['GCS_BUCKET_NAME']:
    print("Warning: GCS_BUCKET_NAME not set in environment variables")
else:
    print(f"GCS Bucket Name configured: {app.config['GCS_BUCKET_NAME']}")

# Verify Google Cloud credentials
gcp_credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if not gcp_credentials_path:
    print("Warning: GOOGLE_APPLICATION_CREDENTIALS not set in environment variables")
elif not os.path.exists(gcp_credentials_path):
    print(f"Warning: Google Cloud credentials file not found at {gcp_credentials_path}")
else:
    print(f"Google Cloud credentials found at: {gcp_credentials_path}")

# --- Supabase Configuration ---
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
if not supabase_url or not supabase_key:
    print("Warning: Supabase configuration incomplete")
else:
    print("Supabase configuration verified")
supabase: Client = create_client(supabase_url, supabase_key)

# --- Initialize Login Manager ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Initialize Google Cloud Services ---
speech_client = speech.SpeechClient()
translate_client = translate.Client()

# --- Initialize TTS Clients ---


# --- Initialize YouTube Processing ---
yt_dlp.utils.std_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# --- Add Security Headers ---
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# --- Context Processor ---
@app.context_processor
def inject_now():
    return {'datetime': datetime}


# --- Main Execution ---
if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true',
            host=os.environ.get('FLASK_RUN_HOST', '127.0.0.1'),
            port=int(os.environ.get('FLASK_RUN_PORT', 5000)))

# --- Audio Folder Setup ---
audio_folder = os.path.join(os.getcwd(), 'audio')
if not os.path.exists(audio_folder):
    os.makedirs(audio_folder)
app.config['UPLOAD_FOLDER'] = audio_folder

# Using the existing language map defined earlier in the file

# --- Initialize API Clients ---
speech_client = speech.SpeechClient()
translate_client = translate.Client()

# --- Initialize TTS Clients ---
tts_client = texttospeech.TextToSpeechClient()

# --- User Class ---
class User(UserMixin):
    def __init__(self, id, email, is_admin=False):
        self.id = str(id)  # Convert UUID to string for Flask-Login
        self.email = email
        self.is_admin = is_admin

    @staticmethod
    def get(user_id):
        try:
            response = supabase.table('users').select('*').eq('id', user_id).execute()
            if response.data:
                user_data = response.data[0]
                return User(
                    id=user_data['id'],
                    email=user_data['email'],
                    is_admin=user_data.get('is_admin', False)
                )
        except Exception as e:
            print(f"Error fetching user: {e}")
        return None

    @staticmethod
    def get_by_email(email):
        try:
            response = supabase.table('users').select('*').eq('email', email).execute()
            if response.data:
                user_data = response.data[0]
                return User(
                    id=user_data['id'],
                    email=user_data['email'],
                    is_admin=user_data.get('is_admin', False)
                )
        except Exception as e:
            print(f"Error fetching user by email: {e}")
        return None

    def set_password(self, password):
        try:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            supabase.table('users').update({'password_hash': hashed_password}).eq('id', self.id).execute()
        except Exception as e:
            print(f"Error setting password: {e}")

    def check_password(self, password):
        try:
            response = supabase.table('users').select('password_hash').eq('id', self.id).execute()
            if response.data:
                stored_hash = response.data[0]['password_hash']
                return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        except Exception as e:
            print(f"Error checking password: {e}")
        return False

# --- User Loader Callback ---
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Forms ---

# --- YouTube Form ---
class YouTubeForm(FlaskForm):
    video_url = StringField('YouTube Video URL', validators=[DataRequired()])
    source_language = SelectField('Source Language', 
        choices=[(code, name) for code, name in language_map.items()],
        validators=[DataRequired(message='Please select a source language')]
    )
    target_language = SelectField('Target Language', 
        choices=[(code, name) for code, name in language_map.items()],
        validators=[DataRequired(message='Please select a target language')]
    )
    submit = SubmitField('Process Video')

    def __init__(self, *args, **kwargs):
        super(YouTubeForm, self).__init__(*args, **kwargs)
        # Set choices for both fields
        self.source_language.choices = [(code, name) for code, name in language_map.items()]
        self.target_language.choices = [(code, name) for code, name in language_map.items()]

# --- Upload Form ---
class UploadForm(FlaskForm):
    audio_file = FileField('Audio File', validators=[
        DataRequired(message='Please select an audio file'),
        FileAllowed(['webm', 'mp3', 'wav'], message='Only WebM, MP3, and WAV audio files are allowed')
    ])
    source_language = SelectField('Source Language', 
        choices=[(code, name) for code, name in language_map.items()],
        validators=[DataRequired(message='Please select a source language')]
    )
    target_languages = SelectMultipleField('Target Languages', 
        choices=[(code, name) for code, name in language_map.items()],
        validators=[DataRequired(message='Please select at least one target language')]
    )
    submit = SubmitField('Translate')

    def __init__(self, *args, **kwargs):
        super(UploadForm, self).__init__(*args, **kwargs)
        # Set choices for both fields using language codes as values
        self.source_language.choices = [(code, name) for code, name in language_map.items()]
        self.target_languages.choices = [(code, name) for code, name in language_map.items()]

# --- Forms ---
class SignupForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Sign Up')

    def validate_email(self, email):
        try:
            response = supabase.table('users').select('*').eq('email', email.data).execute()
            if response.data:
                raise ValidationError('That email is already taken. Please choose a different one.')
        except Exception as e:
            print(f"Error checking email: {e}")
            raise ValidationError('Error checking email availability. Please try again.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long.')
    ])
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='New passwords must match.')
    ])
    submit = SubmitField('Change Password')

# --- Routes ---

# --- YouTube Video Processing Route ---
@app.route('/youtube', methods=['GET', 'POST'])
@login_required
def youtube():
    form = YouTubeForm()
    if form.validate_on_submit():
        video_url = form.video_url.data
        source_lang = form.source_language.data
        target_lang = form.target_language.data

        try:
            # Validate YouTube URL
            if not video_url.startswith('https://www.youtube.com/') and not video_url.startswith('https://youtu.be/'):
                raise ValueError("Invalid YouTube URL format")

            # Process the video
            original_transcript, tts_audio_filename, translated_text, error_message = process_youtube_video(
                youtube_url=video_url,
                source_lang_code=source_lang,
                target_lang_code=target_lang,
                speech_client=speech_client,
                upload_folder=app.config['UPLOAD_FOLDER']
            )

            if error_message:
                app.logger.error(f"Error from process_youtube_video: {error_message}")
                return jsonify({'success': False, 'error': error_message})
            
            if not original_transcript or not tts_audio_filename or not translated_text:
                app.logger.error("Processing returned incomplete data")
                return jsonify({'success': False, 'error': "Processing failed to return all required information."})

            # Save to history with language names
            source_lang_name = language_map.get(source_lang, source_lang)
            target_lang_name = language_map.get(target_lang, target_lang)
            
            # Save to Supabase
            save_translation_history(
                user_id=current_user.id,
                source_lang_code=source_lang,
                target_lang_name=target_lang_name,
                original_text=original_transcript,
                translated_text=translated_text
            )
            
            app.logger.info(f"Saved YouTube translation to history for user {current_user.id}")
            
            return jsonify({
                'success': True,
                'original_text': original_transcript,
                'translated_text': translated_text,
                'audio_url': url_for('play', filename=tts_audio_filename)
            })
        except ValueError as e:
            app.logger.error(f"YouTube processing ValueError: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})
        except Exception as e:
            app.logger.error(f"An unexpected error occurred in /youtube route: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': "An unexpected server error occurred. Please try again."})

    return render_template('youtube.html', form=form)

# --- Routes ---
@app.route('/')
def home():
    # Render home page, potentially show different content if logged in
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('translate_page'))
    form = SignupForm()
    if form.validate_on_submit():
        try:
            # Check if user already exists
            existing_user = User.get_by_email(form.email.data)
            if existing_user:
                flash('Email already registered. Please login instead.', 'danger')
                return redirect(url_for('login'))

            # Create new user
            hashed_password = bcrypt.hashpw(form.password.data.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_data = {
                'email': form.email.data,
                'password_hash': hashed_password,
                'is_admin': False
            }
            result = supabase.table('users').insert(user_data).execute()
            
            if result.data:
                user = User(
                    id=result.data[0]['id'],
                    email=result.data[0]['email'],
                    is_admin=result.data[0].get('is_admin', False)
                )
                login_user(user)
                flash('Your account has been created! You are now logged in.', 'success')
                return redirect(url_for('translate_page'))
            else:
                flash('Error creating account. Please try again.', 'danger')
        except Exception as e:
            flash(f'An error occurred during sign up: {e}', 'danger')
    return render_template('signup.html', title='Sign Up', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('translate_page'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_email(form.email.data)
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required # Ensure user is logged in to log out
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/translate', methods=['GET'])
@login_required
def translate_page():
    form = UploadForm()
    # Convert language map to JSON for JavaScript
    all_language_names_json = json.dumps(list(language_map.values()))
    return render_template('translate.html', 
                         form=form,
                         language_map=language_map, 
                         all_language_names_json=all_language_names_json,
                         title="Translate")

@app.route('/upload_translate', methods=['POST'])
@login_required
def upload_translate():
    form = UploadForm()
    if not form.validate():
        # Log validation errors for debugging
        app.logger.error(f"Form validation errors: {form.errors}")
        return jsonify({"error": f"Form validation failed: {form.errors}"}), 400
    
    file = form.audio_file.data
    if not file:
        return jsonify({"error": "No audio file selected."}), 400
    
    # Get form data using form object
    source_lang_code = form.source_language.data
    target_lang_codes = form.target_languages.data  # This is already a list from SelectMultipleField
    
    # Validate languages
    if not source_lang_code or not target_lang_codes:
        return jsonify({"error": "Source and target languages are required."}), 400
    
    # Create upload path
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"upload_{uuid.uuid4().hex}.webm")
    
    # Initialize variables
    transcript = None
    detected_language_code = None
    tts_file_path: str | None = None
    resampled_path: str | None = None
    all_results = []

    try:
        # 1. Save Uploaded WebM File
        try:
            file.save(upload_path)
            app.logger.info(f"User {current_user.email} - Saved uploaded audio to {upload_path}")
        except Exception as e:
            app.logger.error(f"User {current_user.email} - Failed to save uploaded file: {e}")
            if upload_path and os.path.exists(upload_path): 
                try: os.remove(upload_path)
                except: pass
            return jsonify({"error": "Failed to save uploaded audio file."}), 500

        # 2. Resample Audio & Speech-to-Text (Google Cloud)
        print(f"User {current_user.email} - Processing audio file: {upload_path} with Google Speech API")
        try:
            # --- Resample Audio using pydub --- 
            print(f"User {current_user.email} - Loading uploaded file for resampling...")
            try: 
                audio = AudioSegment.from_file(upload_path) 
            except Exception as pydub_err:
                print(f"Pydub direct load failed ({pydub_err}), trying with explicit format 'webm'...")
                audio = AudioSegment.from_file(upload_path, format="webm")
                
            target_sample_rate = 48000
            print(f"User {current_user.email} - Resampling audio to {target_sample_rate} Hz...")
            resampled_audio = audio.set_frame_rate(target_sample_rate)
            
            flac_filename = f"resampled_{uuid.uuid4().hex}.flac"
            resampled_path = os.path.join(app.config['UPLOAD_FOLDER'], flac_filename)
            print(f"User {current_user.email} - Exporting resampled audio to {resampled_path}...")
            resampled_audio.export(resampled_path, format="flac", parameters=["-ac", "1"])
            print(f"User {current_user.email} - Resampling complete.")
            
            with open(resampled_path, "rb") as audio_file_content:
                content = audio_file_content.read()

            audio_google = speech.RecognitionAudio(content=content)
            
            print(f"User {current_user.email} - Using source language code: {source_lang_code}")
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
                sample_rate_hertz=target_sample_rate,
                audio_channel_count=1,
                enable_automatic_punctuation=True,
                language_code=source_lang_code,
                enable_word_time_offsets=False,
            )

            print(f"User {current_user.email} - Full RecognitionConfig being sent:\n{config}")
            print(f"User {current_user.email} - Sending FLAC audio to Google Speech API...")
            response = speech_client.recognize(config=config, audio=audio_google)
            print(f"User {current_user.email} - Received response from Google Speech API.")

            if not response.results:
                print(f"User {current_user.email} - Google Speech API returned no results.")
                return jsonify({"error": "Speech recognition could not understand audio (no results)."}), 400

            result = response.results[0]
            if not result.alternatives:
                print(f"User {current_user.email} - Google Speech API result has no alternatives.")
                return jsonify({"error": "Speech recognition could not understand audio (no alternatives)."}), 400
            
            transcript = result.alternatives[0].transcript
            detected_language_code = result.language_code
            if not detected_language_code:
                detected_language_code = "en-US" 
                print(f"User {current_user.email} - Language detection failed, defaulting to 'en-US'.")
            
            print(f"User {current_user.email} - Recognized (Lang: {detected_language_code}): {transcript}")

        except Exception as e:
            print(f"User {current_user.email} - ERROR during Google Speech API call or Resampling: {e}")
            if "ffmpeg" in str(e).lower() or "pydub" in str(e).lower():
                return jsonify({"error": f"Audio processing failed (pydub/ffmpeg issue): {e}"}), 500
            return jsonify({"error": f"Speech recognition service error: {e}"}), 503

        if not transcript:
            return jsonify({"error": "Speech recognition failed to produce text."}), 500
        if not detected_language_code:
            return jsonify({"error": "Failed to detect source language."}), 500

        # Get target language names from codes
        target_language_names = []
        for target_lang_code in target_lang_codes:
            # Get the language name from the code
            target_lang_name = language_map.get(target_lang_code)
            if target_lang_name:
                target_language_names.append(target_lang_name)
            else:
                print(f"User {current_user.email} - Invalid target language code: {target_lang_code}")

        results = []
        for target_lang_code in target_lang_codes:
            try:
                # Get base language code for translation (remove country code)
                base_lang_code = target_lang_code.split('-')[0]
                source_base_lang = source_lang_code.split('-')[0]
                
                # Translate Text
                print(f"User {current_user.email} - Translating text to {target_lang_code}...")
                translated_text = GoogleTranslator(source=source_base_lang, target=base_lang_code).translate(transcript)
                print(f"User {current_user.email} - Translation to {target_lang_code} completed.")
                
                # Text-to-Speech (Google Text-to-Speech)
                print(f"User {current_user.email} - Generating TTS audio via Google Text-to-Speech for {target_lang_code}...")
                
                # Initialize Text-to-Speech client
                tts_client = texttospeech.TextToSpeechClient()
                
                # Set the text input to be synthesized
                synthesis_input = texttospeech.SynthesisInput(text=translated_text)
                
                # Build the voice request, select the language code and voice type
                voice = texttospeech.VoiceSelectionParams(
                    language_code=target_lang_code,  # Use full language code for TTS
                    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
                )
                
                # Select the type of audio file you want returned
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )
                
                # Perform the text-to-speech request
                response = tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                
                # Save audio
                audio_filename = f"translated_{target_lang_code}_{uuid.uuid4().hex}.mp3"
                audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
                with open(audio_path, "wb") as out:
                    out.write(response.audio_content)
                print(f"User {current_user.email} - Google Text-to-Speech audio saved for {target_lang_code}.")
                
                # Get the language name for display
                target_lang_name = language_map.get(target_lang_code, target_lang_code)
                
                # Save to history
                if save_translation_history(
                    user_id=current_user.id,
                    source_lang_code=source_lang_code,
                    target_lang_name=target_lang_name,
                    original_text=transcript,
                    translated_text=translated_text
                ):
                    print(f"User {current_user.email} - History saved.")
                else:
                    print(f"User {current_user.email} - Failed to save history.")
                
                results.append({
                    'target_lang': target_lang_name,
                    'translated_text': translated_text,
                    'audio_filename': audio_filename
                })
                
            except Exception as e:
                print(f"User {current_user.email} - ERROR during translation for {target_lang_code}: {e}")
                results.append({
                    'target_lang': language_map.get(target_lang_code, target_lang_code),
                    'error': str(e)
                })
        
        return jsonify({
            'message': 'Translation completed successfully',
            'detected_source_language': detected_language_code,
            'original_text': transcript,
            'results': results
        })

    except Exception as e:
        print(f"User {current_user.email} - ERROR in upload_translate: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500

    finally:
        # Clean up the temporary uploaded webm file
        if upload_path and os.path.exists(upload_path):
            try:
                os.remove(upload_path)
                print(f"User {current_user.email} - Cleaned up temp upload file: {upload_path}")
            except Exception as e:
                print(f"User {current_user.email} - Error cleaning up temp upload file {upload_path}: {e}")
        # Clean up the temporary resampled flac file
        if resampled_path and os.path.exists(resampled_path):
            try:
                os.remove(resampled_path)
                print(f"User {current_user.email} - Cleaned up temp resampled file: {resampled_path}")
            except Exception as e:
                print(f"User {current_user.email} - Error cleaning up temp resampled file {resampled_path}: {e}")

@app.route('/play/<path:filename>') # Use path converter for flexibility
# @login_required # Optional: Make audio files private? Requires storing user association.
def play(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    print(f"Attempting to play: {file_path}")

    # Security check: Ensure filename doesn't try to escape the UPLOAD_FOLDER
    # os.path.abspath converts to absolute path
    # os.path.commonpath checks if file_path is inside UPLOAD_FOLDER
    if not os.path.exists(file_path) or \
       os.path.commonpath([os.path.abspath(app.config['UPLOAD_FOLDER'])]) != \
       os.path.commonpath([os.path.abspath(app.config['UPLOAD_FOLDER']), os.path.abspath(file_path)]):
        print(f"File not found or invalid path: {file_path}")
        return abort(404, description="Audio file not found or path is invalid.")

    @after_this_request
    def remove_file(response):
        # Keep the delayed deletion, maybe reduce delay if not needed after playback starts
        # Note: This might delete file before download completes on slow connections
        def delete():
            time.sleep(10) # Short buffer to allow audio playback start
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted file after serving: {file_path}")
            except Exception as e:
                print(f"Error deleting file after serving {file_path}: {e}")
        # Running deletion in background is important not to block response
        Thread(target=delete).start()
        # Ensure the response is sent with correct headers for streaming/download if needed
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    try:
        return send_file(file_path, mimetype="audio/mpeg") # Use mpeg for mp3
    except Exception as e:
        print(f"Error sending file {file_path}: {e}")
        abort(500, description="Could not send audio file.")

@app.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    history_data = get_translation_history(user_id=current_user.id, page=page)
    
    if history_data:
        # Create a pagination-like object to match template expectations
        class HistoryPagination:
            def __init__(self, data):
                self.items = data['translations']
                self.page = data['current_page']
                self.pages = data['pages']
                self.has_prev = self.page > 1
                self.has_next = self.page < self.pages
                self.prev_num = self.page - 1
                self.next_num = self.page + 1
                
            def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
                last = 0
                for num in range(1, self.pages + 1):
                    if (num <= left_edge or
                        (num > self.page - left_current - 1 and
                         num < self.page + right_current) or
                        num > self.pages - right_edge):
                        if last + 1 != num:
                            yield None
                        yield num
                        last = num

        history = HistoryPagination(history_data)
        return render_template('history.html', 
                             title='Translation History',
                             history=history,
                             language_map=language_map)
    
    return render_template('history.html', 
                         title='Translation History',
                         history=None,
                         language_map=language_map)

@app.route('/delete_history/<string:history_id>', methods=['POST'])
@login_required
def delete_history(history_id):
    try:
        # Verify the history entry belongs to the current user
        result = supabase.table('translation_history')\
            .select('*')\
            .eq('id', history_id)\
            .eq('user_id', current_user.id)\
            .execute()
        
        if not result.data:
            flash('You do not have permission to delete this entry.', 'danger')
            return redirect(url_for('history'))

        # Delete the entry
        supabase.table('translation_history')\
            .delete()\
            .eq('id', history_id)\
            .eq('user_id', current_user.id)\
            .execute()
        
        flash('History entry deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting history entry: {e}', 'danger')

    return redirect(url_for('history'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            try:
                hashed_password = bcrypt.hashpw(form.new_password.data.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                supabase.table('users').update({'password_hash': hashed_password}).eq('id', current_user.id).execute()
                flash('Your password has been updated successfully!', 'success')
                return redirect(url_for('home'))
            except Exception as e:
                flash(f'Error updating password: {e}', 'danger')
        else:
            flash('Incorrect current password.', 'danger')
    return render_template('change_password.html', title='Change Password', form=form)

# --- Initialize Database Command (Optional but good practice) ---
@app.cli.command("init-db")
def init_db_command():
    """Initialize the database tables in Supabase."""
    print("Please run the SQL commands in your Supabase SQL editor to create the tables.")

# --- Context Processor --- 
@app.context_processor
def inject_now():
    """Inject datetime into template context."""
    return {'datetime': datetime}

# Register blueprints
# app.register_blueprint(security_bp, url_prefix='/api/security')

# --- Main Execution ---
if __name__ == '__main__':
    # REMOVED SQLite specific checks/creation logic
    # db.create_all() might need to be run manually via Supabase SQL Editor
    # or using Flask-Migrate if you add migrations later.
    # For now, SQLAlchemy might create tables if the DB user has permission.

    print("Starting Flask server...")
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true',
            host=os.environ.get('FLASK_RUN_HOST', '127.0.0.1'),
            port=int(os.environ.get('FLASK_RUN_PORT', 5000)))

# Add this function to handle database operations
def save_translation_history(user_id, source_lang_code, target_lang_name, original_text, translated_text):
    try:
        data = {
            'user_id': str(user_id),  # Convert UUID to string
            'source_language_code': source_lang_code,
            'target_language_name': target_lang_name,
            'original_text': original_text,
            'translated_text': translated_text,
            'timestamp': datetime.utcnow().isoformat()
        }
        result = supabase.table('translation_history').insert(data).execute()
        return True
    except Exception as e:
        print(f"Error saving translation history: {e}")
        return False

def get_translation_history(user_id, page=1, per_page=10):
    try:
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get total count
        count_result = supabase.table('translation_history')\
            .select('id', count='exact')\
            .eq('user_id', str(user_id))\
            .execute()
        total_count = count_result.count if hasattr(count_result, 'count') else 0
        
        # Get paginated results
        result = supabase.table('translation_history')\
            .select('*')\
            .eq('user_id', str(user_id))\
            .order('timestamp', desc=True)\
            .range(offset, offset + per_page - 1)\
            .execute()
        
        # Convert timestamp strings to datetime objects
        translations = result.data
        for translation in translations:
            if isinstance(translation['timestamp'], str):
                translation['timestamp'] = datetime.fromisoformat(translation['timestamp'].replace('Z', '+00:00'))
        
        return {
            'translations': translations,
            'total': total_count,
            'pages': (total_count + per_page - 1) // per_page,
            'current_page': page
        }
    except Exception as e:
        print(f"Error fetching translation history: {e}")
        return None

@app.route('/translate', methods=['POST'])
@login_required
def translate():
    try:
        data = request.get_json()
        language = data.get('language', 'Hindi')
        military = data.get('military', False)
        enc_key = data.get('encKey', '')
        dec_key = data.get('decKey', '')
        cipher = None

        if military:
            # Try to get key from environment variable first
            env_key = os.environ.get('FERNET_KEY')
            if env_key:
                try:
                    cipher = Fernet(env_key.encode())
                    print("DEBUG: Using Fernet key from environment variable.")
                except Exception as e:
                    print(f"ERROR: Invalid Fernet key from environment variable: {e}")
                    return jsonify({"error": "Server-side encryption key is invalid. Contact administrator."}), 500
            # Fallback to user-provided key
            elif enc_key and dec_key and enc_key == dec_key:
                try:
                    cipher = Fernet(enc_key.encode())
                    print("WARNING: Using Fernet key from frontend. This is INSECURE for production!")
                except Exception:
                    return jsonify({"error": "Invalid encryption key provided. Please check your key format."}), 400
            else:
                return jsonify({"error": "Encryption and Decryption keys are required and must match for Military Mode."}), 400

            # Send email alert if military mode is active and cipher is initialized
            if cipher:
                location_info = get_location()
                async_send_email(location_info)

        # Get audio data from request
        audio_data = request.files.get('audio')
        if not audio_data:
            return jsonify({"error": "No audio file provided"}), 400

        # Save audio file temporarily
        temp_filename = f"temp_{uuid.uuid4()}.wav"
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        audio_data.save(temp_path)

        # Initialize recognizer
        recognizer = sr.Recognizer()

        # Transcribe audio
        with sr.AudioFile(temp_path) as source:
            audio = recognizer.record(source)
            try:
                english_text = recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                return jsonify({"error": "Could not understand audio"}), 400
            except sr.RequestError as e:
                return jsonify({"error": f"Could not request results; {str(e)}"}), 500

        # Translate text
        try:
            translated = GoogleTranslator(source='en', target=language).translate(english_text)
        except Exception as e:
            return jsonify({"error": f"Translation failed: {str(e)}"}), 500

        # Generate speech
        try:
            tts = gTTS(text=translated, lang=language)
            unique_filename = f"translated_{language}_{uuid.uuid4()}.mp3"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            tts.save(file_path)

            # Auto-delete thread
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
                # Encrypt the audio file
                with open(file_path, "rb") as f:
                    raw_data = f.read()
                encrypted = cipher.encrypt(raw_data)

                # Save encrypted data to a temporary file
                encrypted_file_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp_encrypted_" + str(uuid.uuid4()) + ".dat")
                with open(encrypted_file_path, "wb") as ef:
                    ef.write(encrypted)

                # Decrypt the file back for playback
                try:
                    decrypted = cipher.decrypt(encrypted)
                    with open(file_path, "wb") as df:
                        df.write(decrypted)
                    os.remove(encrypted_file_path)
                except InvalidToken:
                    return jsonify({"error": "Decryption failed on server. Please check your key."}), 400
                except Exception as e:
                    return jsonify({"error": f"Military mode processing error: {str(e)}"}), 500

        except InvalidToken:
            return jsonify({"error": "Decryption failed. Please check your key."}), 400
        except Exception as e:
            return jsonify({"error": f"Translation/audio generation failed: {str(e)}"}), 500

        # Clean up temporary audio file
        try:
            os.remove(temp_path)
        except Exception as e:
            print(f"Error cleaning up temporary file: {e}")

        return jsonify({
            "message": f"Translated to {language}",
            "original": english_text,
            "translated": translated,
            "audio": f"/play/{unique_filename}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test-db')
def test_db():
    try:
        # Try to insert a test record
        test_data = {
            'original_text': 'Test',
            'translated_text': 'Test',
            'target_language': 'English',
            'timestamp': time.time()
        }
        result = supabase.table('translations').insert(test_data).execute()
        
        # Try to read it back
        read_result = supabase.table('translations')\
            .select('*')\
            .order('timestamp', desc=True)\
            .limit(1)\
            .execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Database connection successful',
            'data': read_result.data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Database connection failed: {str(e)}'
        }), 500

@app.route('/test-supabase')
def test_supabase():
    try:
        # Test users table
        print("Testing users table...")
        users_result = supabase.table('users').select('*').limit(1).execute()
        print(f"Users table test result: {users_result.data}")

        # Test translation_history table
        print("Testing translation_history table...")
        history_result = supabase.table('translation_history').select('*').limit(1).execute()
        print(f"Translation history table test result: {history_result.data}")

        return jsonify({
            'status': 'success',
            'message': 'Supabase connection successful',
            'users_table': users_result.data,
            'history_table': history_result.data
        })
    except Exception as e:
        print(f"Supabase connection error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Supabase connection failed: {str(e)}'
        }), 500

# Military Mode Utility Functions
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
                print(f"Email sent successfully to {receiver_email}")
        except Exception as e:
            print(f"Email failed: {e}")
    Thread(target=send).start()
