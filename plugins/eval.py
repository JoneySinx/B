import sys
import io
import os
import time
import traceback
import asyncio
import subprocess
import shutil
import json
import math
from datetime import datetime
from hydrogram import Client, filters, enums
from info import ADMINS
from database.users_chats_db import db
from utils import temp, get_size, get_readable_time

# ==============================================================================
# 🐚 SHELL / TERMINAL COMMAND (/sh)
# ==============================================================================
@Client.on_message(filters.command(["sh", "shell", "bash"]) & filters.user(ADMINS))
async def shell_runner(client, message):
    """
    God Mode Terminal: Runs Bash Commands & Handles Large Outputs
    """
    if len(message.command) < 2:
        return await message.reply("<b>⚠️ Usage:</b> `/sh git pull`\n<i>Run Linux commands directly.</i>")
    
    cmd_text = message.text.split(maxsplit=1)[1]
    status_msg = await message.reply("<b>🏃 Running Terminal Command...</b>")
    
    try:
        start_time = time.time()
        process = await asyncio.create_subprocess_shell(
            cmd_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        end_time = time.time()
        
        result = ""
        if stdout:
            result += f"<b>Output:</b>\n<pre>{stdout.decode().strip()}</pre>\n"
        if stderr:
            result += f"<b>Error:</b>\n<pre>{stderr.decode().strip()}</pre>\n"
            
        taken = round(end_time - start_time, 3)
        final_output = f"<b>🐚 Command:</b> `{cmd_text}`\n\n{result}\n<b>⏱ Taken:</b> {taken}s"

        if len(final_output) > 4000:
            with open("terminal_output.txt", "w+", encoding="utf-8") as f:
                f.write(str(stdout.decode().strip()) + "\n\nERRORS:\n" + str(stderr.decode().strip()))
            
            await message.reply_document(
                "terminal_output.txt", 
                caption=f"<b>🐚 Command:</b> `{cmd_text}`\n<b>⏱ Taken:</b> {taken}s",
                protect_content=True
            )
            await status_msg.delete()
            os.remove("terminal_output.txt")
        else:
            if not result: result = "<code>No Output</code>"
            await status_msg.edit(final_output)
            
    except Exception as e:
        await status_msg.edit(f"<b>❌ Execution Error:</b>\n<pre>{e}</pre>")

# ==============================================================================
# 🐍 PYTHON EVAL COMMAND (/eval)
# ==============================================================================
@Client.on_message(filters.command(["eval", "run"]) & filters.user(ADMINS))
async def executor(client, message):
    """
    God Mode Python Executor
    Variables: c=client, m=message, r=reply, db=database, p=print
    """
    if len(message.command) < 2:
        return await message.reply(f"<b>⚠️ Usage:</b> `/eval print(c.me.username)`")
    
    # 1. Parsing Code
    try:
        cmd = message.text.split(maxsplit=1)[1]
    except IndexError:
        return
        
    status_msg = await message.reply("<b>🔄 Compiling...</b>")
    
    # 2. Setup Environment
    # Shortcuts for Admins (The God Features)
    reply_to = message.reply_to_message or message
    
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    redirected_error = sys.stderr = io.StringIO()
    
    stdout, stderr, exc = None, None, None
    start_time = time.time()
    
    try:
        # Pass shortcuts to the function
        await aexec(
            cmd, 
            client, 
            message, 
            reply_to
        )
    except Exception:
        exc = traceback.format_exc()
    
    # 3. Capture Output
    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    
    end_time = time.time()
    taken = round(end_time - start_time, 3)

    # 4. Format Output
    output = ""
    if exc:
        output += f"<b>❌ Exception:</b>\n<pre>{exc}</pre>\n"
    if stderr:
        output += f"<b>⚠️ Stderr:</b>\n<pre>{stderr}</pre>\n"
    if stdout:
        output += f"<b>📤 Stdout:</b>\n<pre>{stdout}</pre>\n"
    
    if not output:
        output = "<code>Success (No Output)</code>"

    # 5. Send Result (Smart Splitter)
    final_text = f"<b>💻 Code:</b>\n<pre>{cmd[:100]}...</pre>\n\n{output}\n<b>⏱ Taken:</b> {taken}s"
    
    if len(final_text) > 4000:
        with open("eval_output.txt", "w+", encoding="utf-8") as f:
            f.write(f"INPUT:\n{cmd}\n\nOUTPUT:\n{stdout}\n\nERRORS:\n{stderr}\n\nTRACEBACK:\n{exc}")
        
        await message.reply_document(
            "eval_output.txt",
            caption=f"<b>💻 Eval Result</b>\n<b>⏱ Taken:</b> {taken}s",
            protect_content=True
        )
        await status_msg.delete()
        os.remove("eval_output.txt")
    else:
        await status_msg.edit(final_text)

# --- 🛠️ ASYNC EXECUTOR WRAPPER ---
async def aexec(code, client, message, reply_to):
    # Shortcuts available inside /eval
    # c = client, m = message, r = reply, db = db, p = print
    # u = user, ch = chat
    
    exec(
        f"async def __aexec(c, m, r, db, temp, p, u, ch): " +
        "".join(f"\n {l}" for l in code.split("\n"))
    )
    
    return await locals()["__aexec"](
        client,            # c
        message,           # m
        reply_to,          # r
        db,                # db
        temp,              # temp
        print,             # p
        message.from_user, # u
        message.chat       # ch
    )
