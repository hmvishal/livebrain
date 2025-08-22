import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, ChatMemberHandler,
    CallbackQueryHandler,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import TELEGRAM_BOT_TOKEN, INSTAMOJO_API, GEMINI_MODEL
from database import (
    setup_database, get_or_create_client, update_client_subscription,
    get_expiring_clients, add_or_get_group, update_user_subscription as activate_db_user,
    add_user_to_group, get_group_by_telegram_id, get_group_members,
    get_expired_group_members, set_user_inactive,
    add_faq, delete_faq, get_faqs_for_group
)
import datetime
import schedule
import time
import threading

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I am your group management bot.",
    )


async def subscription_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks the client's subscription status."""
    user_id = update.effective_user.id
    client = get_or_create_client(user_id)

    if client['subscription_status'] == 'active':
        expiry_date = datetime.datetime.fromisoformat(client['subscription_expiry_date'])
        message = (
            f"Your subscription is **active**.\n"
            f"It will expire on: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}."
        )
    else:
        message = (
            "Your subscription is **inactive**.\n"
            "Use the /subscribe command to get a payment link."
        )

    await update.message.reply_text(message, parse_mode='Markdown')


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates a payment link for the client's subscription."""
    user = update.effective_user

    # Create a new payment request
    response = INSTAMOJO_API.payment_request_create(
        amount='99',
        purpose='Monthly Bot Subscription',
        buyer_name=user.full_name,
        email='user@example.com',  # Instamojo requires an email, even if it's a dummy one
        redirect_url='https://www.example.com/', # A dummy redirect URL
        send_email=False,
        webhook='',
        allow_repeated_payments=False
    )

    if response.get('success'):
        payment_url = response['payment_request']['longurl']
        payment_id = response['payment_request']['id']
        message = (
            f"Thank you for subscribing! Please use the following link to complete your payment:\n"
            f"{payment_url}\n\n"
            f"After payment, please use the following command to verify:\n"
            f"`/verify_payment {payment_id}`"
        )
    else:
        logger.error(f"Instamojo API error: {response.get('message')}")
        message = "Sorry, there was an error creating your payment link. Please try again later."

    await update.message.reply_text(message, parse_mode='Markdown')


async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Verifies a payment with Instamojo and updates the subscription."""
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Please provide a payment ID. Usage: /verify_payment <payment_id>")
        return

    payment_id = context.args[0]

    try:
        response = INSTAMOJO_API.payment_request_status(payment_id)

        if response.get('success') and response['payment_request']['status'] == 'Completed':
            client = get_or_create_client(user_id)
            expiry_date = datetime.datetime.now() + datetime.timedelta(days=30)
            update_client_subscription(client['id'], expiry_date.isoformat())

            await update.message.reply_text(
                "Payment verified! Your subscription is now active for 30 days."
            )
        else:
            status = response.get('payment_request', {}).get('status', 'not found')
            await update.message.reply_text(f"Payment not successful. Status: {status}")

    except Exception as e:
        logger.error(f"Error verifying payment {payment_id}: {e}")
        await update.message.reply_text("There was an error verifying your payment. Please try again later.")


def send_subscription_reminders(bot):
    """Sends reminders to clients whose subscriptions are about to expire."""
    expiring_clients = get_expiring_clients()
    for client_telegram_id, expiry_date_str in expiring_clients:
        try:
            expiry_date = datetime.datetime.fromisoformat(expiry_date_str)
            message = (
                f"**Subscription Reminder**\n"
                f"Your subscription is expiring soon on {expiry_date.strftime('%Y-%m-%d')}. "
                f"Please use the /subscribe command to renew."
            )
            bot.send_message(chat_id=client_telegram_id, text=message, parse_mode='Markdown')
            logger.info(f"Sent subscription reminder to {client_telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send reminder to {client_telegram_id}: {e}")

def remove_expired_members(bot):
    """Removes members with expired subscriptions from their groups."""
    logger.info("Running job: remove_expired_members")
    expired_users = get_expired_group_members()
    for user_telegram_id, group_telegram_id in expired_users:
        try:
            bot.ban_chat_member(chat_id=group_telegram_id, user_id=user_telegram_id)
            # Unbanning immediately after just kicks them.
            bot.unban_chat_member(chat_id=group_telegram_id, user_id=user_telegram_id)

            set_user_inactive(user_telegram_id, group_telegram_id)
            logger.info(f"Removed user {user_telegram_id} from group {group_telegram_id}.")
        except Exception as e:
            logger.error(f"Failed to remove user {user_telegram_id} from group {group_telegram_id}: {e}")

def run_scheduler(bot):
    """Runs the scheduler in a loop."""
    # Schedule the jobs
    schedule.every().day.at("10:00").do(send_subscription_reminders, bot=bot)
    schedule.every().day.at("02:00").do(remove_expired_members, bot=bot)

    while True:
        schedule.run_pending()
        time.sleep(1)


async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Adds a group to be managed by the client."""
    chat_type = update.message.chat.type
    if chat_type not in ['group', 'supergroup']:
        await update.message.reply_text("This command can only be used in a group.")
        return

    group_id = update.message.chat.id
    client_user_id = update.effective_user.id

    # Ensure the user is a client
    client = get_or_create_client(client_user_id)
    if not client:
        # This should not happen due to get_or_create_client logic
        await update.message.reply_text("There was an error identifying you as a client.")
        return

    # Add the group to the database
    add_or_get_group(group_id, client['id'])

    await update.message.reply_text(f"This group has been successfully added for management.")


async def activate_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Activates a member's subscription manually. To be used by a client."""
    if not update.message.reply_to_message:
        await update.message.reply_text("Please use this command by replying to a message from the user you want to activate.")
        return

    # --- Authorization Check ---
    group_telegram_id = update.message.chat.id
    client_user_id = update.effective_user.id

    group = get_group_by_telegram_id(group_telegram_id)
    if not group:
        await update.message.reply_text("This group is not registered. Please use /addgroup first.")
        return

    client = get_or_create_client(client_user_id)
    if not client or client['id'] != group['client_id']:
        await update.message.reply_text("You are not authorized to manage this group.")
        return

    # --- Get User and Duration ---
    target_user = update.message.reply_to_message.from_user
    duration_days = 30
    if context.args and context.args[0].isdigit():
        duration_days = int(context.args[0])

    # --- Update Database ---
    group_db_id = group['id']

    add_user_to_group(target_user.id, group_db_id) # Ensure user exists in DB

    expiry_date = datetime.datetime.now() + datetime.timedelta(days=duration_days)
    activate_db_user(target_user.id, group_db_id, expiry_date.isoformat())

    await update.message.reply_text(
        f"Successfully activated {target_user.mention_html()} for {duration_days} days.",
        parse_mode='HTML'
    )


async def list_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all members in the group and their subscription status."""
    # --- Authorization Check ---
    group_telegram_id = update.message.chat.id
    client_user_id = update.effective_user.id

    group = get_group_by_telegram_id(group_telegram_id)
    if not group:
        await update.message.reply_text("This group is not registered. Please use /addgroup first.")
        return

    client = get_or_create_client(client_user_id)
    if not client or client['id'] != group['client_id']:
        await update.message.reply_text("You are not authorized to manage this group.")
        return

    # --- Get and List Members ---
    members = get_group_members(group['id'])
    if not members:
        await update.message.reply_text("There are no members in the database for this group yet.")
        return

    message = "<b>Group Members:</b>\n\n"
    for member_id, status, expiry in members:
        user_info = f"User ID: {member_id}"
        status_info = f"Status: {status.capitalize()}"
        expiry_info = ""
        if expiry:
            expiry_date = datetime.datetime.fromisoformat(expiry)
            expiry_info = f", Expires: {expiry_date.strftime('%Y-%m-%d')}"

        message += f"- {user_info} | {status_info}{expiry_info}\n"

    await update.message.reply_text(message, parse_mode='HTML')


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets new users and adds them to the database."""
    result = context.chat_member
    if not result or not result.new_chat_member.user:
        return

    new_member = result.new_chat_member.user
    group_telegram_id = update.effective_chat.id

    # Check if this is a managed group
    group = get_group_by_telegram_id(group_telegram_id)
    if not group:
        return # Not a managed group, so we do nothing

    # Add the new member to the database with inactive status
    add_user_to_group(new_member.id, group['id'])

    logger.info(f"New member {new_member.full_name} ({new_member.id}) joined group {group_telegram_id}. Added to DB.")

    await update.effective_chat.send_message(
        f"Welcome {new_member.mention_html()}! This is a private group. "
        f"Please contact the admin for subscription details.",
        parse_mode='HTML'
    )


# --- FAQ Management Commands (for Clients) ---

async def add_faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Adds a new FAQ. Usage: /addfaq question | answer"""
    # Authorization check (similar to other client commands)
    group = get_group_by_telegram_id(update.effective_chat.id)
    client = get_or_create_client(update.effective_user.id)
    if not group or not client or client['id'] != group['client_id']:
        await update.message.reply_text("You are not authorized to manage FAQs for this group.")
        return

    text = " ".join(context.args)
    if '|' not in text:
        await update.message.reply_text("Invalid format. Use: /addfaq Your Question | Your Answer")
        return

    question, answer = text.split('|', 1)
    add_faq(group['id'], question.strip(), answer.strip())
    await update.message.reply_text("FAQ added successfully.")

async def delete_faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes an FAQ by its ID."""
    # Authorization check
    group = get_group_by_telegram_id(update.effective_chat.id)
    client = get_or_create_client(update.effective_user.id)
    if not group or not client or client['id'] != group['client_id']:
        await update.message.reply_text("You are not authorized to manage FAQs for this group.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Please provide the ID of the FAQ to delete. Use /listfaqs to see IDs.")
        return

    faq_id = int(context.args[0])
    delete_faq(faq_id)
    await update.message.reply_text(f"FAQ with ID {faq_id} has been deleted.")

async def list_faqs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all FAQs for the group."""
    # Authorization check
    group = get_group_by_telegram_id(update.effective_chat.id)
    client = get_or_create_client(update.effective_user.id)
    if not group or not client or client['id'] != group['client_id']:
        await update.message.reply_text("You are not authorized to manage FAQs for this group.")
        return

    faqs = get_faqs_for_group(group['id'])
    if not faqs:
        await update.message.reply_text("No FAQs found for this group.")
        return

    message = "<b>Available FAQs:</b>\n\n"
    for faq_id, question, _ in faqs:
        message += f"<b>ID: {faq_id}</b> - {question}\n"

    await update.message.reply_text(message, parse_mode='HTML')


# --- FAQ Command (for Users) ---

async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays a list of FAQs as buttons."""
    group = get_group_by_telegram_id(update.effective_chat.id)
    if not group:
        # Not a managed group, perhaps send a silent fail or a subtle message.
        return

    faqs = get_faqs_for_group(group['id'])
    if not faqs:
        await update.message.reply_text("No frequently asked questions have been set up for this group yet.")
        return

    keyboard = []
    for faq_id, question, _ in faqs:
        button = InlineKeyboardButton(question, callback_data=f"faq_{faq_id}")
        keyboard.append([button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Please choose a question:', reply_markup=reply_markup)

async def faq_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button presses for the FAQ command."""
    query = update.callback_query
    await query.answer() # Acknowledge the button press

    faq_id = int(query.data.split('_')[1])

    # To get the answer, we need the group context again.
    group = get_group_by_telegram_id(query.message.chat.id)
    if not group:
        await query.edit_message_text(text="Error: This group is no longer managed.")
        return

    faqs = get_faqs_for_group(group['id'])
    answer = "Sorry, I couldn't find an answer for that question."
    for f_id, question, ans in faqs:
        if f_id == faq_id:
            answer = f"<b>Q: {question}</b>\n\nA: {ans}"
            break

    await query.edit_message_text(text=answer, parse_mode='HTML')


# --- Gemini AI Command ---

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answers a question using Gemini AI."""
    if not GEMINI_MODEL:
        await update.message.reply_text("The AI feature is not configured for this bot.")
        return

    question = " ".join(context.args)
    if not question:
        await update.message.reply_text("Please ask a question after the command. e.g., /ask What is the capital of France?")
        return

    # Let the user know the bot is thinking
    thinking_message = await update.message.reply_text("🤖 Thinking...")

    try:
        response = await GEMINI_MODEL.generate_content_async(question)
        await thinking_message.edit_text(response.text)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        await thinking_message.edit_text("Sorry, I encountered an error while trying to answer your question.")


def main() -> None:
    """Start the bot."""
    # Set up the database
    setup_database()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscription_status", subscription_status))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("verify_payment", verify_payment))
    application.add_handler(CommandHandler("addgroup", add_group))
    application.add_handler(CommandHandler("activate", activate_member))
    application.add_handler(CommandHandler("listmembers", list_members))
    application.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))

    # FAQ management commands
    application.add_handler(CommandHandler("addfaq", add_faq_command))
    application.add_handler(CommandHandler("deletefaq", delete_faq_command))
    application.add_handler(CommandHandler("listfaqs", list_faqs_command))
    application.add_handler(CommandHandler("faq", faq_command))
    application.add_handler(CallbackQueryHandler(faq_button_handler, pattern="^faq_"))
    application.add_handler(CommandHandler("ask", ask_command))

    # Start the scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler, args=(application.bot,), daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler started.")

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling()
    logger.info("Bot has stopped.")


if __name__ == "__main__":
    main()
