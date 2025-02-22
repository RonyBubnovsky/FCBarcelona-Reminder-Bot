import os
import datetime
import requests
import pytz
import threading
import telegram
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

# Football-Data.org v4 endpoint for FC Barcelona (team ID 81)
FOOTBALL_API_URL = "http://api.football-data.org/v4/teams/81/matches?status=SCHEDULED"

# Define Israel timezone
israel_tz = pytz.timezone("Asia/Jerusalem")

# Initialize Flask app
app = Flask(__name__)

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

def remove_chat(chat_id):
    """
    Removes a chat ID from the MongoDB database.
    """
    if chats_collection.find_one({"chat_id": chat_id}) is not None:
        chats_collection.delete_one({"chat_id": chat_id})
        print(f"Removed chat: {chat_id}")
    else:
        print(f"Chat {chat_id} was not registered.")

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

def remove(update, context):
    """
    Handler for the /remove command.
    Removes the user's chat ID from the persistent database and confirms removal.
    """
    chat_id = update.message.chat.id
    remove_chat(chat_id)
    update.message.reply_text("You have been removed from FC Barcelona reminders. Send /start to register again.")

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    """Handle incoming webhook updates from Telegram"""
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

@app.route('/')
def index():
    return "FC Barcelona Reminder Bot is running!"

def main():
    global bot, dispatcher  # Make these global so webhook handler can access them
    
    # Initialize bot and dispatcher
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    bot = updater.bot
    dispatcher = updater.dispatcher
    
    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("remove", remove))

    # Initialize and start the scheduler
    scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")
    scheduler.start()
    schedule_reminders(updater.bot, scheduler)
    scheduler.add_job(
        update_schedule,
        'cron',
        hour=0,
        minute=0,
        args=[updater.bot, scheduler],
        id="daily_update"
    )

    try:
        # Check deployment environment
        if os.environ.get('RENDER'):
            # Running on Render - use webhooks
            webhook_url = os.environ.get('WEBHOOK_URL')
            if webhook_url:
                # Always set up the webhook on Render
                full_webhook_url = f"{webhook_url}/{TELEGRAM_TOKEN}"
                # Force set the webhook without deleting first
                bot.set_webhook(full_webhook_url)
                print(f"Webhook set to: {full_webhook_url}")
                
                # Start Flask server
                app.run(host='0.0.0.0', port=PORT)
            else:
                print("Error: WEBHOOK_URL environment variable not set")
        else:
            # Local development - use polling
            bot.delete_webhook()  # Ensure no webhook is set
            updater.start_polling()
            print("Bot started in polling mode")
            updater.idle()
    except Exception as e:
        print(f"Error in main: {e}")
        # Always try to restore webhook on error if running on Render
        if os.environ.get('RENDER'):
            webhook_url = os.environ.get('WEBHOOK_URL')
            if webhook_url:
                full_webhook_url = f"{webhook_url}/{TELEGRAM_TOKEN}"
                bot.set_webhook(full_webhook_url)
                print("Restored webhook after error")

if __name__ == '__main__':
    main()