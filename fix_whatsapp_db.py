import os
import sys
from sqlalchemy import text

# Add current directory to path
sys.path.append(os.getcwd())

from northway_crm.app import create_app
from northway_crm.models import db

app = create_app()
with app.app_context():
    try:
        # SQL to ensure columns exist in conversations
        sql_conv = [
            'ALTER TABLE whatsapp_conversations ADD COLUMN IF NOT EXISTS profile_pic_url TEXT;',
            'ALTER TABLE whatsapp_conversations ADD COLUMN IF NOT EXISTS unread_count INTEGER DEFAULT 0;',
            'ALTER TABLE whatsapp_conversations ADD COLUMN IF NOT EXISTS last_message_dir VARCHAR(10) DEFAULT \'in\';',
            'ALTER TABLE whatsapp_conversations ADD COLUMN IF NOT EXISTS last_message_status VARCHAR(20) DEFAULT \'sent\';',
            'ALTER TABLE whatsapp_conversations ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMP;',
            'ALTER TABLE whatsapp_conversations ADD COLUMN IF NOT EXISTS name VARCHAR(255);'
        ]
        
        # SQL to ensure columns exist in messages
        sql_msg = [
            'ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS sender_name VARCHAR(255);',
            'ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS participant_jid VARCHAR(100);'
        ]
        
        print("Executing migration...")
        for query in sql_conv:
            db.session.execute(text(query))
        for query in sql_msg:
            db.session.execute(text(query))
            
        db.session.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        db.session.rollback()
        sys.exit(1)
