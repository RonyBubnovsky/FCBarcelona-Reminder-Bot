import os
import datetime
import requests
import pytz
from telegram.ext import Updater, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY')
CHAT_ID = os.environ.get('CHAT_ID')  # Your Telegram user or group ID

# Football-Data.org v4 endpoint for FC Barcelona (team ID 81)
FOOTBALL_API_URL = "http://api.football-data.org/v4/teams/81/matches?status=SCHEDULED"

# Define Israel timezone
israel_tz = pytz.timezone("Asia/Jerusalem")

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
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    response = requests.get(FOOTBALL_API_URL, headers=headers)
    if response.status_code == 200:
        data = response.json()
        matches = data.get("matches", [])
        for match in matches:
            # Convert the UTC date string to an aware datetime object then to Israel time
            utc_dt = datetime.datetime.fromisoformat(match['utcDate'].replace("Z", "+00:00"))
            match['localDate'] = utc_dt.astimezone(israel_tz)
        return matches
    else:
        print("Error fetching match schedule:", response.status_code, response.text)
        return []

def send_reminder(bot, game_time, hours_before, opponent):
    message = (
        f"Reminder: FC Barcelona match against {opponent} at {game_time.strftime('%Y-%m-%d %H:%M %Z')} "
        f"in {hours_before} hours!"
    )
    bot.send_message(chat_id=CHAT_ID, text=message)
    print(f"Sent {hours_before}h reminder for game at {game_time} against {opponent}.")

def schedule_reminders(bot, scheduler):
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
    print("Updating match schedule...")
    scheduler.remove_all_jobs()  # Clear existing scheduled jobs
    schedule_reminders(bot, scheduler)
    print("Schedule updated.")

def start(update, context):
    update.message.reply_text("FC Barcelona Reminder Bot is running!")

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))

    scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")
    scheduler.start()

    # Schedule initial match reminders
    schedule_reminders(updater.bot, scheduler)

    # Schedule a daily job at 00:00 Israel time to update the match schedule
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
