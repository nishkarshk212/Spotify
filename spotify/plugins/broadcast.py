# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of spotifyMusic

import asyncio
import os
import time
from pyrogram import filters, enums
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from spotify import app, db, lang, userbot, logger, tasks

IS_BROADCASTING = False

# Local constants and variables for background tasks
CACHE_DURATION = 3600
CACHE_SLEEP = 300
file_cache = {}
autoclean = []

def parse_flags(text: str):
    return {
        "pin": "-pin" in text,
        "pinloud": "-pinloud" in text,
        "nobot": "-nobot" in text,
        "user": "-user" in text,
        "assistant": "-assistant" in text
    }

async def broadcast_to_targets(client, targets, query, y=None, x=None, pin=False, pinloud=False):
    global IS_BROADCASTING
    sent = 0
    pinned = 0
    footer = f"\n\nBroadcasted by {app.name}"
    for target_id in targets:
        if not IS_BROADCASTING:
            break
        try:
            if x and y:
                m = await client.forward_messages(target_id, y, x)
            else:
                m = await client.send_message(target_id, text=query + footer)

            if pin:
                try:
                    await m.pin(disable_notification=True)
                    pinned += 1
                except:
                    pass
            elif pinloud:
                try:
                    await m.pin(disable_notification=False)
                    pinned += 1
                except:
                    pass
            sent += 1
            await asyncio.sleep(0.2)

        except FloodWait as fw:
            if fw.value > 200:
                continue
            await asyncio.sleep(fw.value)
        except:
            continue
    return sent, pinned

@app.on_message(filters.command(["broadcast", "gcast"]) & app.sudoers)
@lang.language()
async def broadcast_message(client, message: Message):
    global IS_BROADCASTING
    if IS_BROADCASTING:
        return await message.reply_text(message.lang.get("gcast_active", "A broadcast is already running. Please wait."))

    flags = parse_flags(message.text)
    query = None
    y = x = None

    if message.reply_to_message:
        y = message.chat.id
        x = message.reply_to_message.id
    else:
        if len(message.command) < 2:
            return await message.reply_text(message.lang.get("gcast_usage", "Reply to a message or provide text to broadcast."))
        query = message.text.split(None, 1)[1]
        for flag in ["pin", "pinloud", "nobot", "user", "assistant"]:
            query = query.replace(f"-{flag}", "").strip()
        if not query:
            return await message.reply_text(message.lang.get("gcast_usage", "Please provide text to broadcast."))

    IS_BROADCASTING = True
    await message.reply_text(message.lang.get("gcast_start", "Broadcast started."))

    # Bot Broadcast
    if not flags["nobot"]:
        chat_ids = await db.get_chats()
        sent, pinned = await broadcast_to_targets(
            client, chat_ids, query, y, x, flags["pin"], flags["pinloud"]
        )
        try:
            await message.reply_text(f"Broadcasted to {sent} chats and pinned {pinned} messages.")
        except:
            pass

    # User Broadcast
    if IS_BROADCASTING and flags["user"]:
        user_ids = await db.get_users()
        sent, _ = await broadcast_to_targets(client, user_ids, query, y, x)
        try:
            await message.reply_text(f"Broadcasted to {sent} users.")
        except:
            pass

    # Assistant Broadcast
    if IS_BROADCASTING and flags["assistant"]:
        status_msg = await message.reply_text("Assistant broadcast started...")
        result_text = "Assistant Broadcast Results:\n"
        footer = f"\n\nBroadcasted by {app.name}"

        for i, user_client in enumerate(userbot.clients, 1):
            if not IS_BROADCASTING:
                break
            sent = 0
            try:
                async for dialog in user_client.get_dialogs():
                    if not IS_BROADCASTING:
                        break
                    try:
                        if x and y:
                            await user_client.forward_messages(dialog.chat.id, y, x)
                        else:
                            await user_client.send_message(dialog.chat.id, text=query + footer)
                        sent += 1
                        await asyncio.sleep(3)
                    except FloodWait as fw:
                        if fw.value > 200:
                            continue
                        await asyncio.sleep(fw.value)
                    except:
                        continue
                result_text += f"\nAssistant {i}: {sent} chats"
            except:
                continue
        try:
            await status_msg.edit_text(result_text)
        except:
            pass

    IS_BROADCASTING = False

@app.on_message(filters.command(["stop_gcast", "stop_broadcast"]) & app.sudoers)
async def stop_broadcast_handler(_, message: Message):
    global IS_BROADCASTING
    if not IS_BROADCASTING:
        return await message.reply_text("No ongoing broadcast to stop.")
    IS_BROADCASTING = False
    await message.reply_text("Broadcast stopped.")

async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await db.get_chats()
            for chat_id in served_chats:
                if chat_id not in db.admin_list:
                    db.admin_list[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS
                    ):
                        if user.privileges and user.privileges.can_manage_video_chats:
                            db.admin_list[chat_id].append(user.user.id)

                    auth_users = await db._get_auth(chat_id)
                    for user_id in auth_users:
                        db.admin_list[chat_id].append(user_id)
        except:
            continue

async def auto_clean_cache():
    while not await asyncio.sleep(CACHE_SLEEP):
        try:
            now = time.time()
            expired = [
                f for f, t in file_cache.items()
                if now - t > CACHE_DURATION and f not in autoclean
            ]
            for file in expired:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                        file_cache.pop(file, None)
                except:
                    continue
        except:
            continue

tasks.append(asyncio.create_task(auto_clean()))
tasks.append(asyncio.create_task(auto_clean_cache()))
