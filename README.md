# FC Barcelona Reminder Bot 🔵🔴

A Telegram bot that sends timely reminders for FC Barcelona's upcoming matches. Never miss a Barça game again! The bot sends notifications 7, 5, and 2 hours before each FC Barcelona league and Champions League match.

## Project Motivation

As a passionate FC Barcelona fan, I often found myself missing games or rushing to catch them at the last minute due to my busy schedule and the challenge of keeping track of varying match times. This personal pain point inspired me to create a solution that would help not just me, but other Barça fans never miss a match again. The bot automatically sends reminders at strategic intervals before each game, ensuring that fans have enough time to prepare and tune in to support our beloved club. Whether it's a crucial Champions League fixture or a regular league match, this bot helps keep the Culés community connected to every game.

## Table of Contents

- [Features](#features)
- [Live Demo](#live-demo)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Running Locally](#running-locally)
- [Deployment](#deployment)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)

## Features

- 🕒 Automated reminders 7, 5, and 2 hours before each match
- ⚽ Covers both League and Champions League matches
- 🌐 Match times automatically converted to Israel timezone
- 💾 Persistent storage of user data using MongoDB
- 🔄 Daily schedule updates to ensure accuracy
- 🚀 Deployed on Render for 24/7 availability

## Live Demo

You can try the bot right now:

1. Search for "FCBarcelonaReminderBot" on Telegram
2. Start a chat with the bot
3. Send the `/start` command
4. You'll receive match reminders automatically!

## Prerequisites

- Python 3.8 or higher
- MongoDB account
- Telegram Bot Token
- Football-Data.org API Key
- pip (Python package manager)

## Installation

```bash
# Clone the repository
git clone https://github.com/RonyBubnovsky/FCBarcelona-Reminder-Bot.git
cd FCBarcelona-Reminder-Bot

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
FOOTBALL_API_KEY=your_football_data_org_api_key
MONGODB_URI=your_mongodb_connection_string
PORT=5000
```

### How to Get Environment Variables:

1. **TELEGRAM_TOKEN**:

   - Open Telegram and search for "@BotFather"
   - Send `/newbot` command
   - Follow the instructions to create a new bot
   - Copy the API token provided

2. **FOOTBALL_API_KEY**:

   - Visit [Football-Data.org](https://www.football-data.org)
   - Register for a free account
   - Navigate to your account dashboard
   - Copy your API key

3. **MONGODB_URI**:
   - Create a free account on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
   - Create a new cluster
   - Click "Connect" and choose "Connect your application"
   - Copy the connection string
   - Replace `<password>` with your database user password

## Running Locally

After setting up the environment variables:

```bash
# Activate virtual environment (if not already activated)
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Run the bot
python bot.py
```

## Deployment

The bot is configured for deployment on Render. To deploy your own instance:

1. Fork this repository
2. Create a new Web Service on Render
3. Connect your repository
4. Add the environment variables in the Render dashboard
5. Deploy!

## Architecture

- **Flask Web Server**: Keeps the bot alive on Render
- **APScheduler**: Manages reminder scheduling
- **MongoDB**: Stores registered user chat IDs
- **python-telegram-bot**: Handles Telegram bot interactions
- **Football-Data.org API**: Provides match schedule data

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
