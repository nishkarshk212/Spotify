# Copyright (c) 2025 TheHamkerAlone 
# Licensed under the MIT License.
# This file is part of spotifyMusic


import pyrogram

from spotify import config, logger


class Bot(pyrogram.Client):
    def __init__(self):
        super().__init__(
            name="spotify",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            parse_mode=pyrogram.enums.ParseMode.HTML,
            max_concurrent_transmissions=7,
            link_preview_options=pyrogram.types.LinkPreviewOptions(is_disabled=True),
        )
        self.owner = config.OWNER_ID
        self.logger = config.LOGGER_ID
        self.bl_users = pyrogram.filters.user()
        self.sudoers = pyrogram.filters.user(self.owner)

    async def boot(self):
        """
        Starts the bot and performs initial setup.

        Raises:
            SystemExit: If the bot fails to access the log group or is not an administrator in the logger group.
        """
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            await self.send_message(self.logger, "Bot Started")
            get = await self.get_chat_member(self.logger, self.id)
        except Exception as ex:
            raise SystemExit(f"Bot has failed to access the log group: {self.logger}\nReason: {ex}")

        if get.status != pyrogram.enums.ChatMemberStatus.ADMINISTRATOR:
            raise SystemExit("Please promote the bot as an admin in logger group.")
        
        await self.set_bot_commands()
        logger.info(f"Bot started as @{self.username}")

    async def set_bot_commands(self):
        """Set bot commands for command suggestions when typing /"""
        commands = [
            pyrogram.types.BotCommand("start", "Start the bot"),
            pyrogram.types.BotCommand("help", "Show help menu"),
            pyrogram.types.BotCommand("play", "Play music"),
            pyrogram.types.BotCommand("vplay", "Play video"),
            pyrogram.types.BotCommand("playforce", "Force play music"),
            pyrogram.types.BotCommand("vplayforce", "Force play video"),
            pyrogram.types.BotCommand("pause", "Pause the stream"),
            pyrogram.types.BotCommand("resume", "Resume the stream"),
            pyrogram.types.BotCommand("skip", "Skip current track"),
            pyrogram.types.BotCommand("stop", "Stop the stream"),
            pyrogram.types.BotCommand("queue", "Show queue"),
            pyrogram.types.BotCommand("ping", "Check bot ping"),
            pyrogram.types.BotCommand("stats", "Show bot stats"),
            pyrogram.types.BotCommand("settings", "Bot settings"),
            pyrogram.types.BotCommand("playmode", "Admin only play mode"),
            pyrogram.types.BotCommand("lang", "Change language"),
        ]
        await super().set_bot_commands(commands)

    async def exit(self):
        """
        Asynchronously stops the bot.
        """
        await super().stop()
        logger.info("Bot stopped.")
