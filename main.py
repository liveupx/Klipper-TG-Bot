"""Entry point. Run: python main.py"""
import logging

from bot.telegram_handler import build_app
from config import validate


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=logging.INFO,
    )
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    validate()  # fails fast if env vars missing

    app = build_app()
    logging.info("Bot started. Send a YouTube link in Telegram.")
    app.run_polling()


if __name__ == "__main__":
    main()
