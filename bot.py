"""
FC Barcelona Reminder Bot with Persistent MongoDB Storage, Flask Web Server, and Multi-User Support

This bot fetches FC Barcelona's match schedules from Football-Data.org v4,
schedules reminders (7, 5, and 2 hours before each match), and sends notifications
to all registered users. Registered chat IDs are stored persistently in MongoDB.
Includes an auto-recovery webhook system, health monitoring, and a /standings command
to display the La Liga standings.

Author: Your Name
"""

import os
import datetime
import requests
import pytz
import threading
import telegram
import time
from flask import Flask, request
from telegram.ext import Updater, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from .env
load_dotenv()

# Retrieve credentials and configuration
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY')
PORT = int(os.environ.get('PORT', 8080))
MONGODB_URI = os.environ.get('MONGODB_URI')

# Connect to MongoDB and use the "fcbarca_bot" database
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["fcbarca_bot"]
chats_collection = db.registered_chats

# Football-Data.org v4 endpoint for FC Barcelona matches (team ID 81)
FOOTBALL_API_URL = "http://api.football-data.org/v4/teams/81/matches?status=SCHEDULED"

# Football-Data.org v4 endpoint for La Liga standings (competition code PD)
STANDINGS_API_URL = "http://api.football-data.org/v4/competitions/PD/standings"

# Define Israel timezone
israel_tz = pytz.timezone("Asia/Jerusalem")

# Initialize Flask app (for Render port binding and health checks)
app = Flask(__name__)

@app.route('/')
def index():
    return "FC Barcelona Reminder Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

def check_webhook_health():
    """
    Checks if the webhook is working by getting webhook info from Telegram.
    Returns True if webhook is properly set, False otherwise.
    """
    try:
        webhook_info = bot.get_webhook_info()
        webhook_url = os.environ.get('WEBHOOK_URL')
        expected_webhook_url = f"{webhook_url}/{TELEGRAM_TOKEN}"
        if webhook_info.url == expected_webhook_url:
            return True
        print(f"Webhook mismatch. Expected: {expected_webhook_url}, Got: {webhook_info.url}")
        return False
    except Exception as e:
        print(f"Error checking webhook health: {e}")
        return False

def restore_webhook():
    """
    Attempts to restore the webhook configuration.
    """
    try:
        webhook_url = os.environ.get('WEBHOOK_URL')
        if webhook_url:
            full_webhook_url = f"{webhook_url}/{TELEGRAM_TOKEN}"
            bot.set_webhook(full_webhook_url)
            print(f"Restored webhook to: {full_webhook_url}")
            return True
    except Exception as e:
        print(f"Error restoring webhook: {e}")
    return False

def webhook_monitor():
    """
    Background task that monitors webhook health and restores it if needed.
    """
    while True:
        if os.environ.get('RENDER') and not check_webhook_health():
            print("Webhook appears to be down, attempting to restore...")
            restore_webhook()
        time.sleep(60)  # Check every minute

def get_opponent(match):
    """
    Determines the opponent's name from the match data.
    Assumes FC Barcelona's team ID is 81.
    """
    if match.get('homeTeam', {}).get('id') == 81:
        return match.get('awayTeam', {}).get('name', 'Unknown Opponent')
    else:
        return match.get('homeTeam', {}).get('name', 'Unknown Opponent')

def fetch_game_schedule():
    """
    Fetches scheduled matches for FC Barcelona from Football-Data.org (v4).
    Converts the UTC match time to an aware datetime in Israel time.
    """
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    response = requests.get(FOOTBALL_API_URL, headers=headers)
    if response.status_code == 200:
        data = response.json()
        matches = data.get("matches", [])
        for match in matches:
            utc_dt = datetime.datetime.fromisoformat(match['utcDate'].replace("Z", "+00:00"))
            match['localDate'] = utc_dt.astimezone(israel_tz)
        return matches
    else:
        print("Error fetching match schedule:", response.status_code, response.text)
        return []

def fetch_standings():
    """
    Fetches the La Liga standings from Football-Data.org (v4).
    """
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    response = requests.get(STANDINGS_API_URL, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error fetching standings:", response.status_code, response.text)
        return None

def send_reminder(bot, game_time, hours_before, opponent, home_away):
    """
    Sends a reminder message via the Telegram bot to all registered chats.
    """
    message = (
        f"Reminder: FC Barcelona {home_away} match against {opponent} at "
        f"{game_time.strftime('%Y-%m-%d %H:%M %Z')} in {hours_before} hours!"
    )
    for chat in chats_collection.find():
        chat_id = chat['chat_id']
        try:
            bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            print(f"Error sending reminder to chat {chat_id}: {e}")
    print(f"Sent {hours_before}h reminder for game at {game_time} against {opponent} ({home_away}).")

def schedule_reminders(bot, scheduler):
    """
    Fetches the match schedule and schedules reminder jobs for each match.
    Reminders are set for 7, 5, and 2 hours before each match.
    """
    matches = fetch_game_schedule()
    now = datetime.datetime.now(israel_tz)
    for match in matches:
        game_time = match['localDate']
        opponent = get_opponent(match)
        is_home = match.get('homeTeam', {}).get('id') == 81
        home_away = "Home" if is_home else "Away"
        if game_time > now:
            for hours in [7, 5, 2]:
                reminder_time = game_time - datetime.timedelta(hours=hours)
                if reminder_time > now:
                    job_id = f"{game_time.isoformat()}_{hours}"
                    scheduler.add_job(
                        send_reminder,
                        'date',
                        run_date=reminder_time,
                        args=[bot, game_time, hours, opponent, home_away],
                        id=job_id
                    )
                    print(f"Scheduled {hours}h reminder for game at {game_time} against {opponent} ({home_away}) (runs at {reminder_time}).")

def update_schedule(bot, scheduler):
    """
    Clears all scheduled jobs and re-fetches the match schedule to update reminders.
    This job runs daily at 00:00 Israel time.
    """
    print("Updating match schedule...")
    scheduler.remove_all_jobs()
    schedule_reminders(bot, scheduler)
    print("Schedule updated.")

def register_chat(chat_id):
    """
    Registers a chat ID in the MongoDB database if it's not already registered.
    """
    if chats_collection.find_one({"chat_id": chat_id}) is None:
        chats_collection.insert_one({"chat_id": chat_id})
        print(f"Registered new chat: {chat_id}")
    else:
        print(f"Chat {chat_id} already registered.")

def remove_chat(chat_id):
    """
    Removes a chat ID from the MongoDB database.
    """
    if chats_collection.find_one({"chat_id": chat_id}) is not None:
        chats_collection.delete_one({"chat_id": chat_id})
        print(f"Removed chat: {chat_id}")
    else:
        print(f"Chat {chat_id} was not registered.")

def standings(update, context):
    """
    Handler for the /standings command.
    Fetches the La Liga standings from Football-Data.org (v4) and sends them to the user.
    """
    data = fetch_standings()
    if not data:
        update.message.reply_text("Unable to fetch standings at this time.")
        return

    # Look for the standings of type "TOTAL"
    table = None
    for standing in data.get("standings", []):
        if standing.get("type") == "TOTAL":
            table = standing.get("table", [])
            break

    if not table:
        update.message.reply_text("Standings data is not available.")
        return

    lines = ["*La Liga Standings:*"]
    for entry in table:
        pos = entry.get("position")
        team_name = entry.get("team", {}).get("name")
        points = entry.get("points")
        won = entry.get("won")
        draw = entry.get("draw")
        lost = entry.get("lost")
        line = f"{pos}. {team_name} - {points} pts (W:{won} D:{draw} L:{lost})"
        lines.append(line)
    message = "\n".join(lines)
    update.message.reply_text(message, parse_mode=telegram.ParseMode.MARKDOWN)

def start(update, context):
    """
    Handler for the /start command.
    Registers the user's chat ID persistently and sends a welcome message along with
    the upcoming matches for the next 7 days (grouped into Champions League and League matches).
    """
    chat_id = update.message.chat.id
    register_chat(chat_id)

    now = datetime.datetime.now(israel_tz)
    week_later = now + datetime.timedelta(days=7)
    matches = fetch_game_schedule()
    
    league_games = []
    champions_games = []
    
    for match in matches:
        game_time = match.get("localDate")
        if game_time and now <= game_time <= week_later:
            comp_name = match.get("competition", {}).get("name", "").lower()
            opponent = get_opponent(match)
            is_home = match.get('homeTeam', {}).get('id') == 81
            home_away = "Home" if is_home else "Away"
            match_info = f"{game_time.strftime('%Y-%m-%d %H:%M %Z')} - vs {opponent} ({home_away})"
            if "champions" in comp_name:
                champions_games.append(match_info)
            elif "liga" in comp_name:
                league_games.append(match_info)
            else:
                league_games.append(match_info)  # default to league if unrecognized
            
    welcome = (
        "You have been registered for FC Barcelona reminders!\n"
        "This bot will remind you 7, 5, and 2 hours before each FC Barcelona league or Champions League match.\n\n"
        "Here are your upcoming games for the week:\n"
    )
    if champions_games:
        welcome += "\n**Champions League Matches:**\n" + "\n".join(champions_games) + "\n"
    if league_games:
        welcome += "\n**League Matches:**\n" + "\n".join(league_games) + "\n"
    if not champions_games and not league_games:
        welcome += "\nNo upcoming matches within the next week."
    
    update.message.reply_text(welcome)

def remove(update, context):
    """
    Handler for the /remove command.
    Removes the user's chat ID from the persistent database and confirms removal.
    """
    chat_id = update.message.chat.id
    remove_chat(chat_id)
    update.message.reply_text("You have been removed from FC Barcelona reminders. Send /start to register again.")

def main():
    global bot, dispatcher

    # Initialize bot and dispatcher
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    bot = updater.bot
    dispatcher = updater.dispatcher
    
    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("remove", remove))
    dispatcher.add_handler(CommandHandler("standings", standings))

    # Initialize APScheduler with Israel timezone
    scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")
    scheduler.start()
    schedule_reminders(bot, scheduler)
    scheduler.add_job(
        update_schedule,
        'cron',
        hour=0,
        minute=0,
        args=[bot, scheduler],
        id="daily_update"
    )

    if os.environ.get('DEVELOPMENT'):
        # Development mode: use polling
        print("Running in development mode: deleting webhook and using polling.")
        try:
            bot.delete_webhook()
            time.sleep(1)
        except Exception as e:
            print("Error deleting webhook:", e)
        updater.start_polling()
        updater.idle()
    else:
        # Production mode: use webhooks and monitor health
        monitor_thread = threading.Thread(target=webhook_monitor, daemon=True)
        monitor_thread.start()
        webhook_url = os.environ.get('WEBHOOK_URL')
        if webhook_url:
            full_webhook_url = f"{webhook_url}/{TELEGRAM_TOKEN}"
            bot.set_webhook(full_webhook_url)
            print(f"Webhook set to: {full_webhook_url}")
            # In production mode, use the Flask server for incoming webhook updates
            app.run(host='0.0.0.0', port=PORT)
        else:
            print("Error: WEBHOOK_URL environment variable not set")
            updater.idle()

if __name__ == '__main__':
    main()
