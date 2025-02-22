"""
FC Barcelona Reminder Bot with Flask Web Server

This bot fetches FC Barcelona's league and Champions League match schedules from Football-Data.org,
schedules reminders (7, 5, and 2 hours before each match), and runs a minimal Flask web server on the port
specified by the PORT environment variable. The web server allows Render to detect an open port,
ensuring the service remains active.

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

# Load environment variables from .env file
load_dotenv()

# Retrieve credentials
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY')
CHAT_ID = os.environ.get('CHAT_ID')  # Chat ID where the bot sends notifications
PORT = int(os.environ.get('PORT', 5000))  # Port for Flask server

# Football-Data.org v4 endpoint for FC Barcelona (team ID 81)
FOOTBALL_API_URL = "http://api.football-data.org/v4/teams/81/matches?status=SCHEDULED"

# Define Israel timezone
israel_tz = pytz.timezone("Asia/Jerusalem")

# Initialize Flask app
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
    Sends a reminder message via the Telegram bot.
    """
    message = (
        f"Reminder: FC Barcelona match against {opponent} at {game_time.strftime('%Y-%m-%d %H:%M %Z')} "
        f"in {hours_before} hours!"
    )
    bot.send_message(chat_id=CHAT_ID, text=message)
    print(f"Sent {hours_before}h reminder for game at {game_time} against {opponent}.")

def schedule_reminders(bot, scheduler):
    """
    Fetches the match schedule and schedules reminder jobs.
    Reminders are set for 7, 5, and 2 hours before the match.
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
    This job is scheduled to run daily at 00:00 Israel time.
    """
    print("Updating match schedule...")
    scheduler.remove_all_jobs()
    schedule_reminders(bot, scheduler)
    print("Schedule updated.")

def start(update, context):
    """
    Handler for the /start command.
    """
    update.message.reply_text("FC Barcelona Reminder Bot is running!")

def main():
    # Start Flask server in a separate thread so that it doesn't block the bot
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print(f"Flask web server running on port {PORT}...")

    # Initialize the Telegram bot and dispatcher
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))

    # Initialize APScheduler with Israel timezone
    scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")
    scheduler.start()

    # Schedule initial match reminders
    schedule_reminders(updater.bot, scheduler)

    # Schedule daily update at 00:00 Israel time
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
