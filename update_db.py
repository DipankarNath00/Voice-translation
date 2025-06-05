from app import db, app

def update_database():
    with app.app_context():
        try:
            # Add the new columns
            db.engine.execute('ALTER TABLE translation_history ADD COLUMN IF NOT EXISTS encrypted_data TEXT')
            db.engine.execute('ALTER TABLE translation_history ADD COLUMN IF NOT EXISTS is_encrypted BOOLEAN DEFAULT FALSE')
            print("Successfully added new columns to translation_history table")
        except Exception as e:
            print(f"Error updating database: {e}")

if __name__ == '__main__':
    update_database() 