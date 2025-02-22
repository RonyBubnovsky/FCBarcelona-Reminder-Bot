"""
FC Barcelona Reminder Bot with Persistent MongoDB Storage, Flask Web Server, and Multi-User Support

This bot fetches FC Barcelona's match schedules from Football-Data.org v4,
schedules reminders (7, 5, and 2 hours before each match), and sends notifications
to all registered users. Registered chat IDs are stored persistently in MongoDB.
A minimal Flask web server is run on the specified PORT (for deployment purposes).

"""

import os
import datetime
import requests
import pytz
import threading
from flask import Flask
from telegram.ext import Updater, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from .env
load_dotenv()

# Retrieve credentials and configuration
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY')
PORT = int(os.environ.get('PORT', 5000))
MONGODB_URI = os.environ.get('MONGODB_URI')

# Connect to MongoDB and use the "fcbarca_bot" database
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["fcbarca_bot"]
chats_collection = db.registered_chats

# Football-Data.org v4 endpoint for FC Barcelona (team ID 81)
FOOTBALL_API_URL = "http://api.football-data.org/v4/teams/81/matches?status=SCHEDULED"

# Define Israel timezone
israel_tz = pytz.timezone("Asia/Jerusalem")

# Initialize Flask app for Render port binding
app = Flask(__name__)

@app.route('/')
def index():
    return "FC Barcelona Reminder Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

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

def send_reminder(bot, game_time, hours_before, opponent):
    """
    Sends a reminder message via the Telegram bot to all registered chats.
    """
    message = (
        f"Reminder: FC Barcelona match against {opponent} at {game_time.strftime('%Y-%m-%d %H:%M %Z')} "
        f"in {hours_before} hours!"
    )
    for chat in chats_collection.find():
        chat_id = chat['chat_id']
        bot.send_message(chat_id=chat_id, text=message)
    print(f"Sent {hours_before}h reminder for game at {game_time} against {opponent}.")

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
        if game_time > now:
            for hours in [7, 5, 2]:
                reminder_time = game_time - datetime.timedelta(hours=hours)
                if reminder_time > now:
                    job_id = f"{game_time.isoformat()}_{hours}"
                    scheduler.add_job(
                        send_reminder,
                        'date',
                        run_date=reminder_time,
                        args=[bot, game_time, hours, opponent],
                        id=job_id
                    )
                    print(f"Scheduled {hours}h reminder for game at {game_time} against {opponent} (runs at {reminder_time}).")

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
            match_info = f"{game_time.strftime('%Y-%m-%d %H:%M %Z')} - vs {opponent}"
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

def main():
    # Start Flask server in a separate thread (for port binding on deployment)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print(f"Flask web server running on port {PORT}...")

    # Initialize Telegram bot and dispatcher
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))

    # Initialize APScheduler with Israel timezone
    scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")
    scheduler.start()

    # Schedule initial match reminders
    schedule_reminders(updater.bot, scheduler)

    # Schedule daily update at 00:00 Israel time to refresh match schedule
    scheduler.add_job(
        update_schedule,
        'cron',
        hour=0,
        minute=0,
        args=[updater.bot, scheduler],
        id="daily_update"
    )

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
