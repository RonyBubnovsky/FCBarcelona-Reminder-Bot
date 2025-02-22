"""
test_bot.py

This test suite covers the main functionality of the FC Barcelona Reminder Bot.
It tests:
  - The get_opponent function (determining the opponent's name).
  - The fetch_game_schedule function using a mocked HTTP response.
  - The schedule_reminders function to ensure correct scheduling of jobs.
  - The update_schedule function to verify it clears and re-adds jobs.
  - The register_chat function to check persistent registration.
  - The /start command handler to ensure it registers a chat and replies with a welcome message.
  - The Flask server endpoint to confirm that the web server is running.

These tests are written using Python's unittest framework.
"""

import unittest
from unittest.mock import patch, MagicMock
import datetime
import pytz

# Import functions and objects from the bot module.
from bot import (
    get_opponent,
    fetch_game_schedule,
    schedule_reminders,
    update_schedule,
    register_chat,
    start,
    israel_tz,
    app  # Flask app
)

# For testing APScheduler jobs
from apscheduler.schedulers.background import BackgroundScheduler

class TestBotFunctions(unittest.TestCase):
    def test_get_opponent_home(self):
        """
        Test get_opponent when FC Barcelona (id 81) is the home team.
        Expected opponent is the away team.
        """
        match = {
            "homeTeam": {"id": 81, "name": "FC Barcelona"},
            "awayTeam": {"id": 100, "name": "Real Madrid"}
        }
        opponent = get_opponent(match)
        self.assertEqual(opponent, "Real Madrid")
        
    def test_get_opponent_away(self):
        """
        Test get_opponent when FC Barcelona is the away team.
        Expected opponent is the home team.
        """
        match = {
            "homeTeam": {"id": 100, "name": "Real Madrid"},
            "awayTeam": {"id": 81, "name": "FC Barcelona"}
        }
        opponent = get_opponent(match)
        self.assertEqual(opponent, "Real Madrid")
    
    @patch('bot.requests.get')
    def test_fetch_game_schedule(self, mock_get):
        """
        Test fetch_game_schedule by mocking requests.get.
        It should return matches with a 'localDate' field converted to Israel timezone.
        """
        fake_response = {
            "matches": [
                {
                    "utcDate": "2025-02-22T19:00:00Z",
                    "homeTeam": {"id": 81, "name": "FC Barcelona"},
                    "awayTeam": {"id": 100, "name": "Real Madrid"}
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_response
        mock_get.return_value = mock_resp
        
        matches = fetch_game_schedule()
        self.assertEqual(len(matches), 1)
        self.assertIn("localDate", matches[0])
        self.assertTrue(isinstance(matches[0]["localDate"], datetime.datetime))
        # Compare timezone names rather than tzinfo objects
        self.assertEqual(matches[0]["localDate"].tzinfo.zone, israel_tz.zone)
    
    @patch('bot.fetch_game_schedule')
    def test_schedule_reminders(self, mock_fetch):
        """
        Test that schedule_reminders schedules 3 jobs for a match 12 hours in the future.
        """
        future_time = datetime.datetime.now(israel_tz) + datetime.timedelta(hours=12)
        fake_match = {
            "utcDate": future_time.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "homeTeam": {"id": 81, "name": "FC Barcelona"},
            "awayTeam": {"id": 100, "name": "Real Madrid"},
            "localDate": future_time
        }
        mock_fetch.return_value = [fake_match]
        
        dummy_bot = MagicMock()
        scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")
        scheduler.start()
        scheduler.remove_all_jobs()  # Clear any pre-existing jobs
        
        schedule_reminders(dummy_bot, scheduler)
        jobs = scheduler.get_jobs()
        # For a match 12 hours in future with reminders at 7,5,2 hours, we expect 3 jobs.
        self.assertEqual(len(jobs), 3)
        scheduler.shutdown()
    
    @patch('bot.fetch_game_schedule')
    def test_update_schedule(self, mock_fetch):
        """
        Test that update_schedule clears existing jobs and re-adds them.
        """
        future_time = datetime.datetime.now(israel_tz) + datetime.timedelta(hours=12)
        fake_match = {
            "utcDate": future_time.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "homeTeam": {"id": 81, "name": "FC Barcelona"},
            "awayTeam": {"id": 100, "name": "Real Madrid"},
            "localDate": future_time
        }
        mock_fetch.return_value = [fake_match]
        
        dummy_bot = MagicMock()
        scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")
        scheduler.start()
        
        # First, schedule some jobs
        schedule_reminders(dummy_bot, scheduler)
        initial_jobs = scheduler.get_jobs()
        self.assertEqual(len(initial_jobs), 3)
        
        # Now, update schedule, which should remove existing jobs and re-add new ones.
        update_schedule(dummy_bot, scheduler)
        updated_jobs = scheduler.get_jobs()
        # We expect 3 jobs again.
        self.assertEqual(len(updated_jobs), 3)
        
        scheduler.shutdown()
    
    @patch('bot.chats_collection')
    def test_register_chat_new(self, mock_collection):
        """
        Test register_chat to ensure a new chat ID is inserted if not already registered.
        """
        # Simulate that find_one returns None (chat not registered)
        mock_collection.find_one.return_value = None
        
        # Call register_chat with a dummy chat id
        dummy_chat_id = 123456
        from bot import register_chat
        register_chat(dummy_chat_id)
        # Check that insert_one was called with the dummy chat id.
        mock_collection.insert_one.assert_called_with({"chat_id": dummy_chat_id})
    
    @patch('bot.chats_collection')
    def test_register_chat_existing(self, mock_collection):
        """
        Test register_chat to ensure it does not insert a chat ID that is already registered.
        """
        # Simulate that find_one returns a document (chat already registered)
        mock_collection.find_one.return_value = {"chat_id": 123456}
        
        dummy_chat_id = 123456
        from bot import register_chat
        register_chat(dummy_chat_id)
        # insert_one should not be called since chat is already registered.
        mock_collection.insert_one.assert_not_called()
    
    def test_flask_index(self):
        """
        Test the Flask server's index endpoint to ensure it returns the expected message.
        """
        # Use Flask's test client
        with app.test_client() as client:
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.decode('utf-8'), "FC Barcelona Reminder Bot is running!")
    
    @patch('bot.register_chat')
    @patch('bot.fetch_game_schedule')
    def test_start_command(self, mock_fetch, mock_register):
        """
        Test the /start command handler.
        It should register the chat and send a welcome message with upcoming games.
        """
        # Prepare a fake update and context
        dummy_chat_id = 78910
        fake_update = MagicMock()
        fake_message = MagicMock()
        fake_update.message.chat.id = dummy_chat_id
        fake_update.message.reply_text = MagicMock()
        
        # Prepare fake match schedule: one match 1 day in the future
        future_time = datetime.datetime.now(israel_tz) + datetime.timedelta(days=1)
        fake_match = {
            "utcDate": future_time.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "competition": {"name": "La Liga"},
            "homeTeam": {"id": 81, "name": "FC Barcelona"},
            "awayTeam": {"id": 100, "name": "Real Madrid"},
            "localDate": future_time
        }
        mock_fetch.return_value = [fake_match]
        
        from bot import start
        start(fake_update, None)
        
        # Check that register_chat was called with the dummy chat id
        mock_register.assert_called_with(dummy_chat_id)
        # Check that reply_text was called (with a welcome message)
        fake_update.message.reply_text.assert_called()
    
if __name__ == '__main__':
    unittest.main()
