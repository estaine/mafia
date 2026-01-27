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
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mpasyybxqvzbnxciejqo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

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


def edit_telegram_message(chat_id: int, message_id: int, text: str, reply_markup: Dict = None) -> bool:
    """Edit an existing Telegram message."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
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


def get_supabase_setting(key: str, default: str = None) -> str:
    """Get a setting from Supabase app_settings table."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/app_settings"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        params = {'key': f'eq.{key}'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.ok:
            data = response.json()
            if data and len(data) > 0:
                return data[0].get('value', default)
        return default
    except Exception as e:
        print(f"Error getting setting: {e}")
        return default


def update_supabase_setting(key: str, value: str) -> bool:
    """Update a setting in Supabase app_settings table."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/update_setting"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'setting_key': key,
            'setting_value': value
        }
        
        print(f"Updating setting: {key} = {value}")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Update response: status={response.status_code}, ok={response.ok}")
        if not response.ok:
            print(f"Update error response: {response.text}")
        return response.ok
    except Exception as e:
        print(f"Error updating setting: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_all_players() -> list:
    """Get all players from Supabase."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/player"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        params = {'select': 'id,name,is_hidden', 'order': 'name.asc'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.ok:
            return response.json()
        return []
    except Exception as e:
        print(f"Error getting players: {e}")
        return []


def get_hidden_players() -> list:
    """Get all hidden players from Supabase."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/player"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        params = {'select': 'id,name', 'is_hidden': 'eq.true', 'order': 'name.asc'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.ok:
            return response.json()
        return []
    except Exception as e:
        print(f"Error getting hidden players: {e}")
        return []


def update_player_hidden_status(player_name: str, is_hidden: bool) -> bool:
    """Update a player's hidden status in Supabase."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/player"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        params = {'name': f'eq.{player_name}'}
        payload = {'is_hidden': is_hidden}
        
        response = requests.patch(url, headers=headers, params=params, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Error updating player hidden status: {e}")
        return False


def clear_all_hidden_players() -> int:
    """Unhide all hidden players. Returns count of players unhidden."""
    try:
        # First, get count of hidden players
        hidden_players = get_hidden_players()
        count = len(hidden_players)
        
        if count == 0:
            return 0
        
        # Update all hidden players to not hidden
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/player"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        params = {'is_hidden': 'eq.true'}
        payload = {'is_hidden': False}
        
        response = requests.patch(url, headers=headers, params=params, json=payload, timeout=10)
        if response.ok:
            return count
        return 0
    except Exception as e:
        print(f"Error clearing hidden players: {e}")
        return 0


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
    
    # Get current threshold value
    current_threshold = get_supabase_setting('min_games_threshold', '25')
    
    # Get current activity period value
    current_activity_period = get_supabase_setting('activity_period_days', '30')
    
    # Create inline keyboard with six buttons
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔄 Сінхранізаваць", "callback_data": "sync"}
            ],
            [
                {"text": "⚠️ Перазапісаць", "callback_data": "overwrite"}
            ],
            [
                {"text": "🏆 Пералічыць рэйтынг", "callback_data": "recompute_rating"}
            ],
            [
                {"text": f"⚙️ Змяніць заліковы мінімум ({current_threshold})", "callback_data": "change_threshold"}
            ],
            [
                {"text": f"⏰ Змяніць перыяд актыўнасці ({current_activity_period})", "callback_data": "change_activity_period"}
            ],
            [
                {"text": "👁️ Схаваныя гульцы", "callback_data": "hidden_players_menu"}
            ]
        ]
    }
    
    message = (
        "🎭 <b>Mafia Stats Bot</b>\n\n"
        "Выберыце дзеянне:\n\n"
        "<b>Сінхранізаваць</b> - дадаць новыя гульні з табліцы\n"
        "<b>Перазапісаць</b> - выдаліць усё і загрузіць зноў\n"
        "<b>Пералічыць рэйтынг</b> - пералічыць Glicko-2 рэйтынгі\n"
        f"<b>Заліковы мінімум</b> - зараз: {current_threshold} гульняў\n"
        f"<b>Перыяд актыўнасці</b> - зараз: {current_activity_period} дзён\n"
        "<b>Схаваныя гульцы</b> - кіраванне схаванымі гульцамі"
    )
    
    success = send_telegram_message(chat_id, message, keyboard)
    print(f"send_telegram_message returned: {success}")
    return {"statusCode": 200}


# Store user states for threshold input and hidden players management
user_states = {}


def show_hidden_players_menu(chat_id: int, message_id: int = None) -> bool:
    """Show the hidden players submenu."""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚫 Схаваць гульца", "callback_data": "hide_player"}
            ],
            [
                {"text": "✅ Адкрыць гульца", "callback_data": "unhide_player"}
            ],
            [
                {"text": "📋 Паказаць спіс схаваных", "callback_data": "view_hidden"}
            ],
            [
                {"text": "👥 Паказаць усіх гульцоў", "callback_data": "view_all_players"}
            ],
            [
                {"text": "🗑️ Ачысціць усё", "callback_data": "clear_hidden"}
            ],
            [
                {"text": "⬅️ Назад", "callback_data": "back_to_main"}
            ]
        ]
    }
    
    message = (
        "👁️ <b>Схаваныя гульцы</b>\n\n"
        "Выберыце дзеянне:\n\n"
        "<b>Схаваць гульца</b> - схаваць гульца з галоўнай табліцы\n"
        "<b>Адкрыць гульца</b> - вярнуць гульца ў табліцу\n"
        "<b>Паказаць спіс схаваных</b> - паглядзець усіх схаваных гульцоў\n"
        "<b>Паказаць усіх гульцоў</b> - паглядзець усіх гульцоў (🥷 = схаваны)\n"
        "<b>Ачысціць усё</b> - адкрыць усіх схаваных гульцоў"
    )
    
    if message_id:
        return edit_telegram_message(chat_id, message_id, message, keyboard)
    else:
        return send_telegram_message(chat_id, message, keyboard)


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
    
    # Handle different callback types
    if data == "change_threshold":
        # Ask user to input new threshold
        user_states[user_id] = {"waiting_for": "threshold", "message_id": message_id}
        
        current_threshold = get_supabase_setting('min_games_threshold', '25')
        prompt_text = (
            "⚙️ <b>Змена заліковага мінімуму</b>\n\n"
            f"Цяперашняе значэнне: <b>{current_threshold}</b> гульняў\n\n"
            "Увядзіце новае значэнне (лік ад 0 да 100):"
        )
        
        edit_telegram_message(chat_id, message_id, prompt_text)
        return {"statusCode": 200}
    
    elif data == "change_activity_period":
        # Ask user to input new activity period
        user_states[user_id] = {"waiting_for": "activity_period", "message_id": message_id}
        
        current_activity_period = get_supabase_setting('activity_period_days', '30')
        prompt_text = (
            "⏰ <b>Змена перыяду актыўнасці</b>\n\n"
            f"Цяперашняе значэнне: <b>{current_activity_period}</b> дзён\n\n"
            "Увядзіце новае значэнне (лік ад 1 да 365):"
        )
        
        edit_telegram_message(chat_id, message_id, prompt_text)
        return {"statusCode": 200}
    
    elif data == "hidden_players_menu":
        # Show hidden players menu
        show_hidden_players_menu(chat_id, message_id)
        return {"statusCode": 200}
    
    elif data == "hide_player":
        # Ask user to input player name to hide
        user_states[user_id] = {"waiting_for": "hide_player"}
        prompt_text = (
            "🚫 <b>Схаваць гульца</b>\n\n"
            "Увядзіце імя гульца, якога трэба схаваць з галоўнай табліцы:"
        )
        edit_telegram_message(chat_id, message_id, prompt_text)
        return {"statusCode": 200}
    
    elif data == "unhide_player":
        # Ask user to input player name to unhide
        user_states[user_id] = {"waiting_for": "unhide_player"}
        prompt_text = (
            "✅ <b>Адкрыць гульца</b>\n\n"
            "Увядзіце імя гульца, якога трэба вярнуць у галоўную табліцу:"
        )
        edit_telegram_message(chat_id, message_id, prompt_text)
        return {"statusCode": 200}
    
    elif data == "view_hidden":
        # Show list of hidden players
        hidden_players = get_hidden_players()
        
        if not hidden_players:
            message_text = (
                "📋 <b>Спіс схаваных гульцоў</b>\n\n"
                "Няма схаваных гульцоў.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            player_list = "\n".join([f"• {p['name']}" for p in hidden_players])
            message_text = (
                "📋 <b>Спіс схаваных гульцоў</b>\n\n"
                f"Усяго схавана: <b>{len(hidden_players)}</b>\n\n"
                f"{player_list}\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        
        edit_telegram_message(chat_id, message_id, message_text)
        return {"statusCode": 200}
    
    elif data == "view_all_players":
        # Show list of all players with ninja icon for hidden ones
        all_players = get_all_players()
        
        if not all_players:
            message_text = (
                "👥 <b>Усе гульцы</b>\n\n"
                "Няма гульцоў у базе дадзеных.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            # Sort players by name
            all_players.sort(key=lambda p: p['name'])
            
            # Format player list with ninja icon for hidden players
            player_list = "\n".join([
                f"🥷 {p['name']}" if p.get('is_hidden', False) else f"• {p['name']}"
                for p in all_players
            ])
            
            hidden_count = sum(1 for p in all_players if p.get('is_hidden', False))
            visible_count = len(all_players) - hidden_count
            
            message_text = (
                "👥 <b>Усе гульцы</b>\n\n"
                f"Усяго гульцоў: <b>{len(all_players)}</b>\n"
                f"Адкрытых: <b>{visible_count}</b> | Схаваных: <b>{hidden_count}</b>\n\n"
                f"{player_list}\n\n"
                "🥷 - схаваны гулец\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        
        edit_telegram_message(chat_id, message_id, message_text)
        return {"statusCode": 200}
    
    elif data == "clear_hidden":
        # Clear all hidden players
        count = clear_all_hidden_players()
        
        if count == 0:
            message_text = (
                "ℹ️ <b>Няма схаваных гульцоў</b>\n\n"
                "Усе гульцы ужо адлюстроўваюцца ў табліцы.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            message_text = (
                "✅ <b>Усе гульцы адкрытыя!</b>\n\n"
                f"Адкрыта гульцоў: <b>{count}</b>\n\n"
                "Усе гульцы цяпер будуць адлюстроўвацца ў галоўнай табліцы.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        
        edit_telegram_message(chat_id, message_id, message_text)
        return {"statusCode": 200}
    
    elif data == "back_to_main":
        # Go back to main menu
        handle_start_command(chat_id, user_id)
        return {"statusCode": 200}
    
    elif data == "recompute_rating":
        # Recompute all ratings from scratch
        edit_telegram_message(chat_id, message_id, "⏳ <b>Пералік рэйтынгу...</b>\n\nКалі ласка, пачакайце.")
        
        try:
            # Import rating engine
            import sys
            import os
            
            # Add parent directory to path to import rating_engine
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            
            from rating_engine import full_recompute
            
            # Create API instance
            from sync_engine import SupabaseAPI
            api = SupabaseAPI(SUPABASE_URL, SUPABASE_KEY)
            
            # Run full recomputation
            success = full_recompute(api)
            
            if success:
                edit_telegram_message(
                    chat_id, 
                    message_id,
                    "✅ <b>Рэйтынг пералічаны!</b>\n\n"
                    "Усе рэйтынгі Glicko-2 абноўлены.\n\n"
                    "Выкарыстайце /start для вяртання ў меню."
                )
            else:
                edit_telegram_message(
                    chat_id, 
                    message_id,
                    "❌ <b>Памылка пры пераліку рэйтынгу</b>\n\n"
                    "Не атрымалася пералічыць рэйтынгі.\n\n"
                    "Выкарыстайце /start для вяртання ў меню."
                )
        except Exception as e:
            print(f"Error in rating recomputation: {e}")
            import traceback
            traceback.print_exc()
            edit_telegram_message(
                chat_id, 
                message_id,
                f"❌ <b>Памылка</b>\n\n{str(e)}\n\nВыкарыстайце /start для вяртання ў меню."
            )
        
        return {"statusCode": 200}
    
    # Determine mode for sync operations
    mode = data  # "sync" or "overwrite"
    
    # Update message to show processing
    if mode == "sync":
        processing_text = "⏳ <b>Сінхранізацыя...</b>\n\nКалі ласка, пачакайце."
    else:
        processing_text = "⏳ <b>Перазапіс...</b>\n\n⚠️ Усе дадзеныя будуць выдаленыя!\nКалі ласка, пачакайце."
    
    edit_telegram_message(chat_id, message_id, processing_text)
    
    # Trigger GitHub workflow
    success = trigger_github_workflow(mode, chat_id)
    
    if not success:
        error_text = f"❌ <b>Памылка</b>\n\nНе атрымалася запусціць {mode}."
        edit_telegram_message(chat_id, message_id, error_text)
    
    return {"statusCode": 200}


def handle_threshold_input(chat_id: int, user_id: int, text: str, message_id: int) -> Dict[str, Any]:
    """Handle threshold value input from user."""
    try:
        # Parse the input
        threshold = int(text.strip())
        
        # Validate range
        if threshold < 0 or threshold > 100:
            send_telegram_message(
                chat_id,
                "❌ Памылка: лік павінен быць ад 0 да 100.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
            )
            return {"statusCode": 200}
        
        # Update the setting in database
        success = update_supabase_setting('min_games_threshold', str(threshold))
        
        if success:
            response_text = (
                "✅ <b>Заліковы мінімум зменены!</b>\n\n"
                f"Новае значэнне: <b>{threshold}</b> гульняў\n\n"
                "Змены адразу ж адлюструюцца на сайце.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            response_text = (
                "❌ <b>Памылка</b>\n\n"
                "Не атрымалася абнавіць налады.\n\n"
                "Паспрабуйце яшчэ раз ці звяжыцеся з адміністратарам."
            )
        
        send_telegram_message(chat_id, response_text)
        
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        
    except ValueError:
        send_telegram_message(
            chat_id,
            "❌ Памылка: увядзіце карэктны лік.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
    
    return {"statusCode": 200}


def handle_activity_period_input(chat_id: int, user_id: int, text: str, message_id: int) -> Dict[str, Any]:
    """Handle activity period value input from user."""
    try:
        # Parse the input
        period = int(text.strip())
        
        # Validate range
        if period < 1 or period > 365:
            send_telegram_message(
                chat_id,
                "❌ Памылка: лік павінен быць ад 1 да 365.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
            )
            return {"statusCode": 200}
        
        # Update the setting in database
        success = update_supabase_setting('activity_period_days', str(period))
        
        if success:
            response_text = (
                "✅ <b>Перыяд актыўнасці зменены!</b>\n\n"
                f"Новае значэнне: <b>{period}</b> дзён\n\n"
                "Змены адразу ж адлюструюцца на сайце.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            response_text = (
                "❌ <b>Памылка</b>\n\n"
                "Не атрымалася абнавіць налады.\n\n"
                "Паспрабуйце яшчэ раз ці звяжыцеся з адміністратарам."
            )
        
        send_telegram_message(chat_id, response_text)
        
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        
    except ValueError:
        send_telegram_message(
            chat_id,
            "❌ Памылка: увядзіце карэктны лік.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
    
    return {"statusCode": 200}


def handle_hide_player_input(chat_id: int, user_id: int, text: str) -> Dict[str, Any]:
    """Handle hide player name input from user."""
    player_name = text.strip()
    
    if not player_name:
        send_telegram_message(
            chat_id,
            "❌ Памылка: імя гульца не можа быць пустым.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
        return {"statusCode": 200}
    
    # Get all players to check if player exists
    all_players = get_all_players()
    player_found = None
    
    for player in all_players:
        if player['name'].lower() == player_name.lower():
            player_found = player
            break
    
    if not player_found:
        send_telegram_message(
            chat_id,
            f"❌ <b>Гулец не знойдзены</b>\n\nГулец з імем '<b>{player_name}</b>' не знойдзены ў базе дадзеных.\n\nПраверце правапіс і паспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
        return {"statusCode": 200}
    
    if player_found.get('is_hidden', False):
        send_telegram_message(
            chat_id,
            f"ℹ️ <b>Гулец ужо схаваны</b>\n\nГулец '<b>{player_found['name']}</b>' ужо схаваны.\n\nВыкарыстайце /start для вяртання ў меню."
        )
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        return {"statusCode": 200}
    
    # Update player's hidden status
    success = update_player_hidden_status(player_found['name'], True)
    
    if success:
        response_text = (
            f"✅ <b>Гулец схаваны!</b>\n\n"
            f"Гулец '<b>{player_found['name']}</b>' больш не будзе адлюстроўвацца ў галоўнай табліцы па змоўчанні.\n\n"
            "Выкарыстайце /start для вяртання ў меню."
        )
    else:
        response_text = (
            "❌ <b>Памылка</b>\n\n"
            "Не атрымалася абнавіць статус гульца.\n\n"
            "Паспрабуйце яшчэ раз ці звяжыцеся з адміністратарам."
        )
    
    send_telegram_message(chat_id, response_text)
    
    # Clear user state
    if user_id in user_states:
        del user_states[user_id]
    
    return {"statusCode": 200}


def handle_unhide_player_input(chat_id: int, user_id: int, text: str) -> Dict[str, Any]:
    """Handle unhide player name input from user."""
    player_name = text.strip()
    
    if not player_name:
        send_telegram_message(
            chat_id,
            "❌ Памылка: імя гульца не можа быць пустым.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
        return {"statusCode": 200}
    
    # Get all players to check if player exists
    all_players = get_all_players()
    player_found = None
    
    for player in all_players:
        if player['name'].lower() == player_name.lower():
            player_found = player
            break
    
    if not player_found:
        send_telegram_message(
            chat_id,
            f"❌ <b>Гулец не знойдзены</b>\n\nГулец з імем '<b>{player_name}</b>' не знойдзены ў базе дадзеных.\n\nПраверце правапіс і паспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
        return {"statusCode": 200}
    
    if not player_found.get('is_hidden', False):
        send_telegram_message(
            chat_id,
            f"ℹ️ <b>Гулец ужо адкрыты</b>\n\nГулец '<b>{player_found['name']}</b>' ужо адлюстроўваецца ў табліцы.\n\nВыкарыстайце /start для вяртання ў меню."
        )
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        return {"statusCode": 200}
    
    # Update player's hidden status
    success = update_player_hidden_status(player_found['name'], False)
    
    if success:
        response_text = (
            f"✅ <b>Гулец адкрыты!</b>\n\n"
            f"Гулец '<b>{player_found['name']}</b>' цяпер будзе адлюстроўвацца ў галоўнай табліцы.\n\n"
            "Выкарыстайце /start для вяртання ў меню."
        )
    else:
        response_text = (
            "❌ <b>Памылка</b>\n\n"
            "Не атрымалася абнавіць статус гульца.\n\n"
            "Паспрабуйце яшчэ раз ці звяжыцеся з адміністратарам."
        )
    
    send_telegram_message(chat_id, response_text)
    
    # Clear user state
    if user_id in user_states:
        del user_states[user_id]
    
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
                message_id = message.get("message_id")
                
                print(f"Message from user {user_id}: {text}")
                
                # Check if user is waiting for input
                if user_id in user_states:
                    waiting_for = user_states[user_id].get("waiting_for")
                    if waiting_for == "threshold":
                        handle_threshold_input(chat_id, user_id, text, message_id)
                    elif waiting_for == "activity_period":
                        handle_activity_period_input(chat_id, user_id, text, message_id)
                    elif waiting_for == "hide_player":
                        handle_hide_player_input(chat_id, user_id, text)
                    elif waiting_for == "unhide_player":
                        handle_unhide_player_input(chat_id, user_id, text)
                elif text.startswith("/start"):
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

