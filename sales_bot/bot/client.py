from pyrogram import Client

# Global client instance
app: Client = None

def init_client(api_id: int, api_hash: str, bot_token: str) -> Client:
    """Initialize the Pyrogram client"""
    global app
    if app is None:
        app = Client(
            "sales_bot",
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token
        )
    return app

def get_client() -> Client:
    """Get the initialized client instance"""
    if app is None:
        raise RuntimeError("Client not initialized. Call init_client() first.")
    return app
