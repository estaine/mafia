"""
Vercel serverless function for handling Telegram bot webhooks.
Receives commands from authorized users and triggers GitHub workflows.
"""

import os
import json
import requests
from typing import Dict, Any

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')  # Format: "username/repo"
ALLOWED_USER_IDS = os.environ.get('ALLOWED_USER_IDS', '5980607330,184403698')

# Parse allowed user IDs
ALLOWED_USERS = set(int(uid.strip()) for uid in ALLOWED_USER_IDS.split(',') if uid.strip())


def send_telegram_message(chat_id: int, text: str, reply_markup: Dict = None) -> bool:
    """Send a message to Telegram chat."""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    print(f"Sending message to chat_id={chat_id}, has_keyboard={reply_markup is not None}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Telegram API response: status={response.status_code}")
        if not response.ok:
            print(f"Telegram API error: {response.text}")
        return response.ok
    except Exception as e:
        print(f"Error sending message: {e}")
        import traceback
        traceback.print_exc()
        return False


def edit_telegram_message(chat_id: int, message_id: int, text: str) -> bool:
    """Edit an existing Telegram message."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Error editing message: {e}")
        return False


def answer_callback_query(callback_query_id: str, text: str = "") -> bool:
    """Answer a callback query to remove the loading state."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "text": text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Error answering callback: {e}")
        return False


def trigger_github_workflow(mode: str, chat_id: int) -> bool:
    """Trigger GitHub workflow via repository_dispatch."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "event_type": mode,  # "sync" or "overwrite"
        "client_payload": {
            "chat_id": str(chat_id),
            "mode": mode
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 204]
    except Exception as e:
        print(f"Error triggering workflow: {e}")
        return False


def handle_start_command(chat_id: int, user_id: int) -> Dict[str, Any]:
    """Handle /start command - show menu with buttons."""
    print(f"handle_start_command: user_id={user_id}, allowed_users={ALLOWED_USERS}")
    
    if user_id not in ALLOWED_USERS:
        print(f"User {user_id} is not authorized")
        send_telegram_message(
            chat_id,
            "❌ Вы не маеце доступу да гэтага бота."
        )
        return {"statusCode": 200}
    
    print(f"User {user_id} is authorized, sending menu")
    
    # Create inline keyboard with two buttons
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔄 Сінхранізаваць", "callback_data": "sync"}
            ],
            [
                {"text": "⚠️ Перазапісаць", "callback_data": "overwrite"}
            ]
        ]
    }
    
    message = (
        "🎭 <b>Mafia Stats Bot</b>\n\n"
        "Выберыце дзеянне:\n\n"
        "<b>Сінхранізаваць</b> - дадаць новыя гульні з табліцы\n"
        "<b>Перазапісаць</b> - выдаліць усё і загрузіць зноў"
    )
    
    success = send_telegram_message(chat_id, message, keyboard)
    print(f"send_telegram_message returned: {success}")
    return {"statusCode": 200}


def handle_callback_query(callback_query: Dict) -> Dict[str, Any]:
    """Handle button callback."""
    query_id = callback_query.get("id")
    data = callback_query.get("data")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    user_id = callback_query.get("from", {}).get("id")
    
    # Validate user
    if user_id not in ALLOWED_USERS:
        answer_callback_query(query_id, "Доступ забаронены")
        return {"statusCode": 200}
    
    # Answer the callback query
    answer_callback_query(query_id)
    
    # Determine mode
    mode = data  # "sync" or "overwrite"
    
    # Update message to show processing
    if mode == "sync":
        processing_text = "⏳ <b>Сінхранізацыя...</b>\n\nКалі ласка, пачакайце."
    else:
        processing_text = "⏳ <b>Перазапіс...</b>\n\n⚠️ Усе даныя будуць выдалены!\nКалі ласка, пачакайце."
    
    edit_telegram_message(chat_id, message_id, processing_text)
    
    # Trigger GitHub workflow
    success = trigger_github_workflow(mode, chat_id)
    
    if not success:
        error_text = f"❌ <b>Памылка</b>\n\nНе атрымалася запусціць {mode}."
        edit_telegram_message(chat_id, message_id, error_text)
    
    return {"statusCode": 200}


from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs


class handler(BaseHTTPRequestHandler):
    """
    Vercel entry point using BaseHTTPRequestHandler.
    This is the pattern Vercel's Python runtime expects.
    """
    
    def do_POST(self):
        """Handle POST requests from Telegram webhook."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body_text = self.rfile.read(content_length).decode('utf-8')
            
            print(f"Received POST request, body length: {content_length}")
            
            # Parse JSON
            try:
                body = json.loads(body_text) if body_text else {}
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return
            
            print(f"Parsed body keys: {list(body.keys())}")
            
            # Handle different update types
            if "message" in body:
                message = body["message"]
                chat_id = message.get("chat", {}).get("id")
                user_id = message.get("from", {}).get("id")
                text = message.get("text", "")
                
                print(f"Message from user {user_id}: {text}")
                
                if text.startswith("/start"):
                    handle_start_command(chat_id, user_id)
            
            elif "callback_query" in body:
                print("Handling callback query")
                handle_callback_query(body["callback_query"])
            
            # Always return 200 OK to Telegram
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
            
        except Exception as e:
            print(f"Error in handler: {e}")
            import traceback
            traceback.print_exc()
            
            # Still return 200 to Telegram to avoid retries
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
    
    def do_GET(self):
        """Reject GET requests."""
        self.send_response(405)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Method not allowed"}).encode())

