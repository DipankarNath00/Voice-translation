from flask import Blueprint, request, jsonify, current_app
from functools import wraps
from cryptography.fernet import InvalidToken
import json
from flask_login import login_required

security_bp = Blueprint('security_api', __name__)

# Decorator to check if military mode is enabled
def require_military_mode(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_app.config.get('MILITARY_MODE_ENABLED', False):
            return jsonify({
                'success': False,
                'error': 'Military mode is not enabled'
            }), 403
        return f(*args, **kwargs)
    return decorated_function

@security_bp.route('/decrypt', methods=['POST'])
@require_military_mode
@login_required
def decrypt_data():
    """Decrypt encrypted data using Fernet"""
    try:
        data = request.get_json()
        if not data or 'encrypted_data' not in data:
            return jsonify({
                'success': False,
                'error': 'No encrypted data provided'
            }), 400

        # Get the encrypted data and metadata
        encrypted_info = json.loads(data['encrypted_data'])
        
        # Verify the data belongs to the current user
        metadata = encrypted_info.get('metadata', {})
        if metadata.get('user_id') != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Unauthorized: Data belongs to another user'
            }), 403

        # Decrypt the data
        decrypted_data, metadata = current_app.security_manager.decrypt(encrypted_info)
        
        return jsonify({
            'success': True,
            'data': json.loads(decrypted_data),
            'metadata': metadata
        })

    except InvalidToken:
        return jsonify({
            'success': False,
            'error': 'Invalid encryption token'
        }), 400
    except Exception as e:
        current_app.logger.error(f"Decryption error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@security_bp.route('/key/rotate', methods=['POST'])
@require_military_mode
@login_required
def rotate_key():
    """Rotate encryption key"""
    try:
        if not current_user.is_admin:  # Assuming you have an admin flag
            return jsonify({
                'success': False,
                'error': 'Unauthorized: Only admins can rotate keys'
            }), 403

        success = current_app.security_manager.rotate_key()
        return jsonify({
            'success': success,
            'message': 'Key rotation successful' if success else 'Key rotation failed'
        })

    except Exception as e:
        current_app.logger.error(f"Key rotation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
