# Voice Translation Application - Technical Documentation

## Military Mode Database Schema

### MilitaryTranslation Table
- `id`: Primary Key (UUID)
- `user_id`: Foreign Key (References User.id)
- `encrypted_original_text`: Binary (Encrypted)
- `encrypted_translated_text`: Binary (Encrypted)
- `encryption_key_id`: String (Reference to encryption key)
- `source_language`: String (Language Code)
- `target_language`: String (Language Code)
- `created_at`: DateTime
- `expires_at`: DateTime
- `is_archived`: Boolean
- `security_level`: String (Classified, Secret, Top Secret)

### EncryptionKey Table
- `id`: Primary Key (UUID)
- `key_hash`: String (Hashed)
- `created_at`: DateTime
- `expires_at`: DateTime
- `is_active`: Boolean
- `rotation_period`: Integer (in days)

## Military Mode Functions

### MilitaryTranslation Functions
1. **Encrypted Translation Management**
   - `save_military_translation(user_id, original_text, translated_text, security_level)`: 
     - Encrypts and saves translation with military-grade encryption
     - Returns encrypted record ID
   
   - `get_military_translation(translation_id, encryption_key)`: 
     - Decrypts and retrieves specific translation
     - Requires valid encryption key
   
   - `archive_military_translation(translation_id)`: 
     - Archives translation for long-term storage
     - Updates encryption if needed
   
   - `delete_military_translation(translation_id)`: 
     - Securely deletes translation
     - Implements secure deletion protocol
   
   - `get_military_translations_by_level(user_id, security_level)`: 
     - Retrieves translations by security level
     - Requires appropriate clearance

2. **Security Operations**
   - `verify_translation_integrity(translation_id)`: 
     - Verifies encryption integrity
     - Checks for tampering
   
   - `rotate_encryption(translation_id)`: 
     - Rotates encryption keys
     - Re-encrypts data with new key
   
   - `audit_military_translations(user_id)`: 
     - Generates access audit log
     - Tracks all access attempts

### EncryptionKey Functions
1. **Key Management**
   - `generate_encryption_key()`: 
     - Generates new military-grade encryption key
     - Stores key hash
   
   - `rotate_encryption_keys()`: 
     - Rotates all active encryption keys
     - Re-encrypts affected data
   
   - `validate_key(key_id)`: 
     - Validates encryption key
     - Checks expiration
   
   - `revoke_key(key_id)`: 
     - Revokes compromised keys
     - Initiates emergency re-encryption

2. **Security Protocols**
   - `enforce_key_rotation()`: 
     - Enforces key rotation policy
     - Schedules rotations
   
   - `backup_encryption_keys()`: 
     - Securely backs up active keys
     - Implements secure storage
   
   - `restore_encryption_keys(backup_id)`: 
     - Restores keys from backup
     - Validates backup integrity

## Military Mode Security Features

1. **Data Protection**
   - Military-grade encryption (AES-256)
   - Secure key management
   - Automatic key rotation
   - Secure deletion protocols

2. **Access Control**
   - Security level-based access
   - Multi-factor authentication
   - Access logging and auditing
   - IP-based restrictions

3. **Compliance**
   - Military security standards
   - Data retention policies
   - Audit trail maintenance
   - Emergency protocols

## Military Mode Environment Variables

Required environment variables for military mode:
- `MILITARY_MODE_ENABLED`: Boolean
- `ENCRYPTION_KEY_ROTATION_DAYS`: Integer
- `MILITARY_SECURITY_LEVEL`: String
- `MILITARY_AUDIT_LOG_PATH`: String
- `MILITARY_BACKUP_PATH`: String
- `MILITARY_IP_WHITELIST`: String (comma-separated)
- `MILITARY_SESSION_TIMEOUT`: Integer (minutes)

## Military Mode Implementation

### TranslationHistory Table (Modified for Military Mode)
- `id`: Primary Key (UUID)
- `user_id`: Foreign Key (References User.id)
- `source_language`: String (Language Code)
- `target_language`: String (Language Code)
- `original_text`: Text (Encrypted in military mode)
- `translated_text`: Text (Encrypted in military mode)
- `audio_file_path`: String
- `created_at`: DateTime
- `is_military_mode`: Boolean

### EncryptionKey Table
- `id`: Primary Key (UUID)
- `key_hash`: String (Hashed)
- `created_at`: DateTime
- `expires_at`: DateTime
- `is_active`: Boolean

## Military Mode Functions

### TranslationHistory Functions
1. **Translation Management**
   - `save_translation(user_id, source_lang, target_lang, original_text, translated_text)`: 
     - If military mode: Encrypts text before saving
     - If normal mode: Saves as plain text
     - Returns translation ID
   
   - `get_translation(translation_id)`: 
     - If military mode: Decrypts text before returning
     - If normal mode: Returns plain text
   
   - `get_user_translations(user_id, page, per_page)`: 
     - Retrieves translations
     - Decrypts text if in military mode
   
   - `delete_translation(translation_id)`: 
     - Deletes translation record
     - Handles both modes

2. **Encryption Operations**
   - `encrypt_text(text)`: 
     - Encrypts text using military-grade encryption
     - Returns encrypted text
   
   - `decrypt_text(encrypted_text)`: 
     - Decrypts text using current encryption key
     - Returns plain text
   
   - `rotate_encryption_key()`: 
     - Generates new encryption key
     - Re-encrypts all military mode translations

## Military Mode Security Features

1. **Data Protection**
   - Military-grade encryption (AES-256) for text fields only
   - Secure key management
   - Automatic key rotation

2. **Access Control**
   - Military mode flag check
   - Secure key storage
   - Access logging

## Military Mode Environment Variables

Required environment variables for military mode:
- `MILITARY_MODE_ENABLED`: Boolean
- `ENCRYPTION_KEY`: String (Base64 encoded)
- `MILITARY_SESSION_TIMEOUT`: Integer (minutes)

## Military Mode Implementation Notes

1. **Mode Switching**
   - System checks `is_military_mode` flag
   - Only text fields are encrypted/decrypted
   - All other functionality remains unchanged

2. **Data Storage**
   - Military mode: Only text fields are encrypted
   - Normal mode: All fields stored as plain text
   - Same table structure, minimal changes

3. **Performance Considerations**
   - Only text fields require encryption/decryption
   - Minimal overhead
   - Efficient key management

4. **Migration Support**
   - Simple toggle for military mode
   - Automatic encryption of existing text
   - No structural changes needed 