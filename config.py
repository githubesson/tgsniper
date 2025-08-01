import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.getenv('API_ID'))
    API_HASH = os.getenv('API_HASH')
    SESSION_NAME = os.getenv('SESSION_NAME', 'marketchecker')
    
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
    
    # Stars market settings
    MIN_PRICE = int(os.getenv('MIN_PRICE', 1))
    MAX_PRICE = int(os.getenv('MAX_PRICE', 400))
    MIN_PROFIT_PERCENTAGE = float(os.getenv('MIN_PROFIT_PERCENTAGE', 8.0))
    
    # TON market settings
    ENABLE_TON_SNIPING = os.getenv('ENABLE_TON_SNIPING', 'false').lower() == 'true'
    MIN_TON_PRICE = float(os.getenv('MIN_TON_PRICE', 0))
    MAX_TON_PRICE = float(os.getenv('MAX_TON_PRICE', 10_000))
    MIN_TON_PROFIT_PERCENTAGE = float(os.getenv('MIN_TON_PROFIT_PERCENTAGE', 8.0))
    
    USE_CONCURRENT = os.getenv('USE_CONCURRENT', 'true').lower() == 'true'
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', 50))
    SCAN_INTERVAL = float(os.getenv('SCAN_INTERVAL', 2.5))
    SUMMARY_INTERVAL = int(os.getenv('SUMMARY_INTERVAL', 100))

config = Config()
