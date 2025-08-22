# Telegram Paid Group Management Bot

This is a powerful Telegram bot designed to help admins of paid subscription groups automate user management and support. The bot is built with a flexible architecture, allowing for client-specific configurations and future integrations.

## Features

### For Bot Owners & Clients (Group Admins)
- **Client Subscription System:** Clients subscribe to use the bot with a monthly fee, managed via Instamojo.
- **Automated Reminders:** The bot sends automated reminders to clients when their subscription is about to expire.
- **Manual Member Management:** Clients can manually activate subscriptions for their group members.
- **Group Management:** Clients can register their groups with the bot to enable management features.
- **FAQ Management:** Clients can add, delete, and list frequently asked questions for their group.

### For Users (Group Members)
- **Automated Welcome:** New users are greeted with a welcome message upon joining a group.
- **Automated Removal:** Users with expired subscriptions are automatically removed from the group.
- **Interactive FAQ:** Users can use the `/faq` command to browse and get answers to common questions through an interactive button menu.

## Setup and Installation

### 1. Prerequisites
- Python 3.8 or higher
- A Telegram Bot Token from BotFather
- An Instamojo account (optional, for testing)

### 2. Installation
1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```
2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### 3. Configuration
Create a file named `config.env` in the root directory of the project and add the following variables:

```env
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
INSTAMOJO_API_KEY="YOUR_INSTAMOJO_API_KEY"
INSTAMOJO_AUTH_TOKEN="YOUR_INSTAMOJO_AUTH_TOKEN"
ADMIN_TELEGRAM_ID="YOUR_ADMIN_TELEGRAM_ID"
```

- `TELEGRAM_BOT_TOKEN`: Your bot's API token from Telegram's BotFather.
- `INSTAMOJO_API_KEY` & `INSTAMOJO_AUTH_TOKEN`: Your API credentials from Instamojo. You can use the placeholder values to run the bot with the test API.
- `ADMIN_TELEGRAM_ID`: The Telegram User ID of the primary bot owner/administrator.

## Running the Bot

To run the bot locally, use the following command:
```bash
python src/bot.py
```
The bot will start, and you should see log messages in your console.

## Command Reference

### Client (Group Admin) Commands
These commands are for the admins of the paid groups.

- `/subscribe`: Generates a personal Instamojo link for the client to pay their monthly bot subscription fee.
- `/verify_payment <payment_id>`: Verifies the client's subscription payment to activate their bot usage.
- `/subscription_status`: Checks the status and expiry date of the client's subscription to the bot.
- `/addgroup`: **(Must be used inside the group)** Registers the group with the bot, linking it to the client who uses the command.
- `/activate`: **(Reply to a user's message)** Manually activates a group member's subscription. Usage: `/activate` (defaults to 30 days) or `/activate [days]`.
- `/listmembers`: Lists all members of the group who are in the bot's database, along with their subscription status.
- `/addfaq [question] | [answer]`: Adds a new frequently asked question for the group.
- `/deletefaq [faq_id]`: Deletes an FAQ using its ID (use `/listfaqs` to find the ID).
- `/listfaqs`: Shows all the current FAQs and their IDs for the group.
- `/setup_automation`: Starts a guided setup to connect a payment gateway (e.g., Stripe) for fully automated member subscriptions.

### User (Group Member) Commands
These commands are for the regular members of a client's group.

- `/start`: Displays a welcome message.
- `/faq`: Shows an interactive menu of frequently asked questions for the group.
- `/ask [question]`: Asks a question to the bot's integrated AI for a helpful answer.

## Full Automation Setup (Stripe Example)

To enable fully automated member subscriptions, your clients need to connect their payment gateway to the bot. The `/setup_automation` command makes this easy. Here is the process for Stripe:

### Client-Side Setup
1.  The client (group admin) uses the `/setup_automation` command in a private message with the bot.
2.  The bot will guide them through selecting "Stripe" and providing their Stripe **secret API key**.
3.  The bot will then provide a unique **Webhook URL**. The client must copy this URL.
4.  In their Stripe Dashboard, the client goes to **Developers > Webhooks**.
5.  They click **Add an endpoint**, paste the URL from the bot, and select the event `checkout.session.completed`.

### Creating Payment Links
For the automation to work, the bot needs to know which Telegram user made a payment. To do this, the client must include the user's Telegram ID when creating a Stripe Payment Link.

When creating a product or payment link in Stripe, in the advanced options or metadata, there is often a field called **Client Reference ID**. The client must pass the user's Telegram ID into this field. The bot will then automatically match the payment to the user.

*Note: A future version of the bot could include a command like `/generatelink @username` to make this process even easier for the client.*

## Deployment

For production use, you should run the bot on a server where it can operate 24/7. This bot runs a web server on port **8443** to listen for webhooks, so you must ensure this port is open and accessible from the internet.

### Example with `nohup` (simple, not recommended for large scale)
```bash
nohup python src/bot.py &
```

### Example with `systemd` (more robust)
1.  Create a service file: `sudo nano /etc/systemd/system/telegram_bot.service`
2.  Add the following content, adjusting paths as necessary:
    ```ini
    [Unit]
    Description=Telegram Group Management Bot
    After=network.target

    [Service]
    User=your_user
    Group=your_group
    WorkingDirectory=/path/to/your/bot/project
    ExecStart=/path/to/your/bot/project/venv/bin/python src/bot.py
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
3.  Enable and start the service:
    ```bash
    sudo systemctl enable telegram_bot
    sudo systemctl start telegram_bot
    ```
