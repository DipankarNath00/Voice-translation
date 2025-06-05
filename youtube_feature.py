import os
import uuid
from flask import current_app
from pydub import AudioSegment
from google.cloud import speech
from google.cloud import texttospeech
from google.cloud import translate_v2 as translate
import html
import yt_dlp
from yt_dlp.utils import DownloadError # Ensure this is imported correctly
import google.api_core.exceptions
from deep_translator import GoogleTranslator
from gtts import gTTS

# Timeout for the long-running speech recognition operation in seconds (e.g., 15 minutes)
GCS_OPERATION_TIMEOUT = 900

def download_youtube_audio_refined(youtube_url, output_dir):
    """Downloads first 5 minutes of audio from a YouTube video using yt-dlp, saves it, and returns the path."""
    try:
        # Robustly extract video ID to get a clean URL for yt-dlp
        current_app.logger.info(f"Original YouTube URL: {youtube_url}")
        try:
            # Use yt_dlp itself to extract info and get the clean URL (id)
            info = yt_dlp.YoutubeDL({'quiet': True}).extract_info(youtube_url, download=False)
            # The 'video_id' isn't directly used for download in this function, but the check validates the URL.
            # yt-dlp is robust enough to handle the original URL in ydl.download()
        except Exception as e_extract:
            current_app.logger.error(f"Failed to extract video ID from URL ({youtube_url}): {e_extract}")
            return None, f"Invalid YouTube URL or failed to extract video ID: {str(e_extract)}"

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Define a template for the output file
        temp_filename_base = f"youtube_dl_{uuid.uuid4().hex}"
        # yt-dlp will automatically add the correct extension based on format
        output_template = os.path.join(output_dir, f"{temp_filename_base}.%(ext)s")

        # Configure yt-dlp options with FFmpeg clipping using a separate postprocessor
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                    'args': [
                        '-ss', '00:00:00',  # Start at 0 seconds
                        '-t', '300'         # Duration of 300 seconds (5 minutes)
                    ]
                }
            ],
            'quiet': True,
            'noprogress': True,
            'noplaylist': True,
        }
        
        downloaded_file_path = None
        current_app.logger.info(f"Downloading and clipping first 5 minutes of audio for {youtube_url} using yt-dlp with options: {ydl_opts}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Pass the original youtube_url directly, yt-dlp handles parsing
            info_download = ydl.extract_info(youtube_url, download=True)
            
            # Get the final output file path after all post-processing
            if info_download and 'filepath' in info_download:
                downloaded_file_path = info_download['filepath']
            else:
                # Fallback if 'filepath' is not directly available (less common)
                current_app.logger.warning("Could not find 'filepath' in download info. Falling back to expected name.")
                downloaded_file_path = os.path.join(output_dir, f"{temp_filename_base}.mp3") # Assumes .mp3 output

        if not downloaded_file_path or not os.path.exists(downloaded_file_path):
            current_app.logger.error(f"yt-dlp finished but output file not found: {downloaded_file_path}")
            return None, "Download failed: output file not created by yt-dlp."

        current_app.logger.info(f"Successfully downloaded and clipped first 5 minutes of audio to {downloaded_file_path}")
        return downloaded_file_path, None
        
    except DownloadError as e:
        current_app.logger.error(f"yt-dlp DownloadError for URL ({youtube_url}): {e}")
        return None, f"Failed to download video (yt-dlp error): {str(e)}"
    except Exception as e:
        current_app.logger.error(f"Generic error during yt-dlp download for URL ({youtube_url}): {e}")
        return None, f"An unexpected error occurred during download: {str(e)}"

def process_youtube_video(youtube_url, source_lang_code, target_lang_code, speech_client, upload_folder):
    """
    Process first 5 minutes of YouTube video:
    1. Download audio
    2. Transcribe using Google Speech-to-Text
    3. Translate using Google Translator
    4. Convert to speech using gTTS
    """
    audio_file = None
    flac_file = None
    
    try:
        current_app.logger.info(f"Starting YouTube video processing for URL: {youtube_url}")
        
        # Configure yt-dlp options for first 5 minutes with a separate FFmpegPostProcessor
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '64',  # Further reduced bitrate
            }],
            'quiet': True,
            'no_warnings': True,
            'paths': {'temp': upload_folder, 'home': upload_folder},
            'outtmpl': os.path.join(upload_folder, '%(id)s.%(ext)s'),
            'postprocessor_args': [
                '-ss', '00:00:00',
                '-t', '60',      # Changed from 300 to 60 seconds (1 minute)
                '-ar', '16000',  # Reduced to 16kHz for better compatibility
                '-ac', '1',      # Mono audio
                '-b:a', '64k'    # Explicitly set bitrate
            ],
            'extract_flat': False,
            'force_generic_extractor': False
        }

        # Download audio
        current_app.logger.info("Attempting to download YouTube audio...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            
            # Get the actual downloaded file path from info
            audio_file = None
            if info and 'filepath' in info: # Rely on 'filepath' for the final processed file path
                audio_file = info['filepath']
            elif 'requested_downloads' in info and info['requested_downloads']: # Fallback
                audio_file = info['requested_downloads'][0]['filepath']

            if not audio_file or not os.path.exists(audio_file):
                raise Exception(f"Failed to download audio or output file not found. Info: {info}")

        current_app.logger.info(f"Successfully downloaded audio to: {audio_file}")

        # Convert audio to FLAC for Google Speech-to-Text
        current_app.logger.info("Converting audio to FLAC...")
        flac_file = audio_file.replace('.mp3', '.flac')
        # Ensure the audio file actually exists before trying to load it
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Downloaded MP3 file not found at expected path: {audio_file}")
        audio = AudioSegment.from_mp3(audio_file)
        audio.export(flac_file, format="flac")
        current_app.logger.info(f"Successfully converted audio to FLAC: {flac_file}")

        # Read the audio file
        current_app.logger.info("Reading FLAC audio content...")
        with open(flac_file, "rb") as audio_file_content:
            content = audio_file_content.read()
        current_app.logger.info("FLAC audio content read.")

        # Configure and perform speech recognition
        current_app.logger.info(f"Performing speech recognition using language code: {source_lang_code}")
        audio_rec_config = speech.RecognitionAudio(content=content) # Renamed to avoid confusion with pydub audio object
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
            language_code=source_lang_code,
            enable_automatic_punctuation=True,
        )
        
        # Get transcription
        response = speech_client.recognize(config=config, audio=audio_rec_config)
        original_transcript = " ".join([result.alternatives[0].transcript for result in response.results])
        current_app.logger.info(f"Transcription successful. Original text: {original_transcript}")

        # Translate the transcript
        current_app.logger.info(f"Translating text to target language code: {target_lang_code}")
        base_lang_code_for_gtts = target_lang_code.split('-')[0]
        source_base_lang = source_lang_code.split('-')[0]
        translated_text = GoogleTranslator(source=source_base_lang, target=base_lang_code_for_gtts).translate(original_transcript)
        current_app.logger.info(f"Translation successful. Translated text: {translated_text}")

        # Generate translated audio using gTTS
        current_app.logger.info("Generating translated audio using gTTS...")
        tts = gTTS(text=translated_text, lang=base_lang_code_for_gtts)
        tts_audio_filename = f"translated_{target_lang_code}_{uuid.uuid4().hex}.mp3"
        tts_audio_path = os.path.join(upload_folder, tts_audio_filename)
        tts.save(tts_audio_path)
        current_app.logger.info(f"Translated audio saved to: {tts_audio_path}")

        return original_transcript, tts_audio_filename, translated_text, None

    except DownloadError as e:
        error_message = f"YouTube Download Error: {e}"
        current_app.logger.error(error_message)
        return None, None, None, error_message
    except google.api_core.exceptions.GoogleAPIError as e:
        error_message = f"Google Cloud API Error: {e}"
        current_app.logger.error(error_message)
        return None, None, None, error_message
    except Exception as e:
        error_message = f"An unexpected error occurred during YouTube processing: {e}"
        current_app.logger.error(error_message)
        return None, None, None, error_message

    finally:
        current_app.logger.info("Cleaning up temporary files...")
        for file_path in [audio_file, flac_file]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    current_app.logger.info(f"Cleaned up temporary file: {file_path}")
                except Exception as e:
                    current_app.logger.error(f"Error cleaning up {file_path}: {e}")
        current_app.logger.info("Temporary file cleanup complete.")