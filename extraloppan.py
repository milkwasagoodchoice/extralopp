import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from threading import Timer

# Define your Telegram bot token
TELEGRAM_BOT_TOKEN = '7713171054:AAF4sL1XxoU6yyMCZftuj870n5iQPGj-nxo'  # Replace with your bot token

# Define the base URL for the API
BASE_URL = "https://www.extraloppan.is/boerneloppen-theme/searches/search.json"

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Default refresh interval (in seconds)
DEFAULT_REFRESH_INTERVAL = 60 * 60 * 1  # 1 hour


# Function to search products based on a keyword
def search_products(keyword):
    all_results = []
    initial_response = requests.get(
        f"{BASE_URL}?page=1&query={keyword}&boerneloppen_theme_store_id=&boerneloppen_theme_status_id=&sort=name&direction=ASC&only_own_products=false&show_marked_inactive=false")

    if initial_response.status_code == 200:
        initial_data = initial_response.json()
        total_pages = initial_data.get('pages', 0)

        for i in range(1, total_pages + 1):
            response = requests.get(
                f"{BASE_URL}?page={i}&query={keyword}&boerneloppen_theme_store_id=&boerneloppen_theme_status_id=&sort=name&direction=ASC&only_own_products=false&show_marked_inactive=false")
            if response.status_code == 200:
                data = response.json()
                results = data.get('data', [])
                all_results.extend(results)

        # Sort results by name, stand, and price
        sorted_results = sorted(all_results,
                                key=lambda x: (x.get('name', ''), x.get('stand', ''), x.get('price', float('inf'))))
        return sorted_results
    return None


# Function to send search results to the user
async def send_results(update: Update, results):
    response_message = "Search Results:\n"
    for item in results:
        title = item.get('name', 'N/A')
        stand = item.get('stand', 'N/A')
        price = item.get('price', 'N/A')
        response_message += f"Title: {title}, Stand: {stand}, Price: {price}\n"

    if len(response_message) > 4096:
        response_message = response_message[:4096] + "... (truncated)"

    await update.message.reply_text(response_message)


# Command handler for /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Please enter a keyword to search for products.")


# Command handler for /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Available Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/set_interval - Set the refresh interval for results\n"
        "/clear - Clear all saved searches\n"
        "/saved - List all saved searches"
    )
    await update.message.reply_text(help_text)


# Command handler for /saved
async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saved_searches = context.user_data.get('saved_searches', [])
    if saved_searches:
        await update.message.reply_text("Saved Searches:\n" + "\n".join(saved_searches))
    else:
        await update.message.reply_text("No saved searches found.")


# Command handler for /clear
async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['saved_searches'] = []  # Clear saved searches
    await update.message.reply_text("All saved searches have been cleared.")


# Handler for text messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text
    await update.message.reply_text(f"Searching for '{keyword}'...")

    results = search_products(keyword)

    if results:
        await send_results(update, results)

        # Create inline keyboard for saving results
        keyboard = [[InlineKeyboardButton("Save Results", callback_data=f"save_{keyword}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Would you like to save these results?", reply_markup=reply_markup)

        # Start a timer to refresh the search results
        refresh_interval = context.user_data.get('refresh_interval', DEFAULT_REFRESH_INTERVAL)
        context.user_data['refresh_timer'] = Timer(refresh_interval, lambda: refresh_search(update, context, keyword))
        context.user_data['refresh_timer'].start()
    else:
        await update.message.reply_text("No results found. You can still save this search keyword.")

        # Create inline keyboard for saving results even if no results are found
        keyboard = [[InlineKeyboardButton("Save Search Keyword", callback_data=f"save_{keyword}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Would you like to save this search keyword?", reply_markup=reply_markup)


# Callback function for button presses
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the callback

    if query.data.startswith("save_"):
        keyword = query.data.split("_")[1]
        saved_searches = context.user_data.get('saved_searches', [])
        if keyword not in saved_searches:
            saved_searches.append(keyword)
            context.user_data['saved_searches'] = saved_searches
            await query.message.reply_text(f"'{keyword}' has been saved!")
        else:
            await query.message.reply_text(f"'{keyword}' is already saved.")
    elif query.data.startswith("set_interval_"):
        interval = int(query.data.split("_")[2]) * 3600  # Convert hours to seconds
        context.user_data['refresh_interval'] = interval
        await query.message.reply_text(f"Refresh interval set to {interval // 3600} hours.")


# Function to refresh the search results
def refresh_search(update: Update, context: ContextTypes.DEFAULT_TYPE, keyword):
    logger.info("Refreshing search results...")
    results = search_products(keyword)

    if results:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Refreshing search results...")
        send_results(update, results)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No new results found.")


async def show_interval_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1 hour", callback_data="set_interval_1"),
         InlineKeyboardButton("2 hours", callback_data="set_interval_2")],
        [InlineKeyboardButton("3 hours", callback_data="set_interval_3"),
         InlineKeyboardButton("4 hours", callback_data="set_interval_4")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose a refresh interval:", reply_markup=reply_markup)

# Main function to run the bot
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))  # Added help command
    application.add_handler(CommandHandler("set_interval", show_interval_buttons))  # Button handler
    application.add_handler(CommandHandler("saved", saved_command))  # Added saved command
    application.add_handler(CommandHandler("clear", clear_command))  # Added clear command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()

if __name__ == '__main__':
    main()