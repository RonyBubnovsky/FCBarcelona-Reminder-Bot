import unittest
from unittest.mock import patch, MagicMock
import datetime
import pytz

# Import functions from the bot module.
from bot import get_opponent, fetch_game_schedule, schedule_reminders, israel_tz

class TestBotFunctions(unittest.TestCase):
    
    def test_get_opponent_home(self):
        """Test that if FC Barcelona (id 81) is home, the opponent is the away team."""
        match = {
            "homeTeam": {"id": 81, "name": "FC Barcelona"},
            "awayTeam": {"id": 100, "name": "Real Madrid"}
        }
        opponent = get_opponent(match)
        self.assertEqual(opponent, "Real Madrid")
        
    def test_get_opponent_away(self):
        """Test that if FC Barcelona is away, the opponent is the home team."""
        match = {
            "homeTeam": {"id": 100, "name": "Real Madrid"},
            "awayTeam": {"id": 81, "name": "FC Barcelona"}
        }
        opponent = get_opponent(match)
        self.assertEqual(opponent, "Real Madrid")
    
    @patch('bot.requests.get')
    def test_fetch_game_schedule(self, mock_get):
        """Test fetch_game_schedule by mocking requests.get."""
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
        self.assertEqual(matches[0]["localDate"].tzinfo.zone, israel_tz.zone)
    
    @patch('bot.fetch_game_schedule')
    def test_schedule_reminders(self, mock_fetch):
        """Test that schedule_reminders adds the expected jobs."""
        future_time = datetime.datetime.now(israel_tz) + datetime.timedelta(hours=12)
        fake_match = {
            "utcDate": future_time.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "homeTeam": {"id": 81, "name": "FC Barcelona"},
            "awayTeam": {"id": 100, "name": "Real Madrid"},
            "localDate": future_time
        }
        mock_fetch.return_value = [fake_match]
        
        dummy_bot = MagicMock()
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")
        scheduler.start()
        scheduler.remove_all_jobs()  # Ensure no existing jobs
        
        from bot import schedule_reminders
        schedule_reminders(dummy_bot, scheduler)
        
        jobs = scheduler.get_jobs()
        self.assertEqual(len(jobs), 3)
        
        scheduler.shutdown()

if __name__ == '__main__':
    unittest.main()
