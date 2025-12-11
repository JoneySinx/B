import sys
import io
import os
import time
import traceback
import asyncio
import subprocess
from datetime import datetime
from hydrogram import Client, filters
from info import ADMINS
from database.users_chats_db import db
from utils import temp

# --- SHELL / TERMINAL COMMAND (/sh) ---
@Client.on_message(filters.command(["sh", "shell", "bash"]) & filters.user(ADMINS))
async def shell_runner(client, message):
    """Run Linux Terminal Commands via Bot"""
    if len(message.command) < 2:
        return await message.reply("<b>Usage:</b> `/sh git pull`")
    
    cmd_text = message.text.split(maxsplit=1)[1]
    msg = await message.reply("<b>🏃 Running Terminal Command...</b>")
    
    try:
        start_time = time.time()
        process = await asyncio.create_subprocess_shell(
            cmd_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        end_time = time.time()
        
        result = str(stdout.decode().strip()) + str(stderr.decode().strip())
        taken = round(end_time - start_time, 3)
        
        if len(result) > 4000:
            with open("terminal_output.txt", "w+", encoding="utf-8") as f:
                f.write(result)
            await message.reply_document(
                "terminal_output.txt", 
                caption=f"<b>🐚 Command:</b> `{cmd_text}`\n<b>⏱ Taken:</b> {taken}s"
            )
            await msg.delete()
            os.remove("terminal_output.txt")
        else:
            if not result: result = "No Output"
            await msg.edit(f"<b>🐚 Command:</b> `{cmd_text}`\n\n<pre>{result}</pre>\n\n<b>⏱ Taken:</b> {taken}s")
            
    except Exception as e:
        await msg.edit(f"<b>❌ Error:</b>\n<pre>{e}</pre>")

# --- PYTHON EVAL COMMAND (/eval) ---
@Client.on_message(filters.command("eval") & filters.user(ADMINS))
@Client.on_edited_message(filters.command("eval") & filters.user(ADMINS))
async def executor(client, message):
    """
    Advanced Python Code Executor
    Features: Live Edit, Auto-Imports, Shortcuts, Time Tracking
    """
    if len(message.command) < 2:
        return await message.reply(f"<b>Usage:</b> `/eval print('hello')`")
    
    # 1. Prepare Code
    try:
        cmd = message.text.split(maxsplit=1)[1]
    except IndexError:
        return
        
    status_msg = await message.reply("<b>🔄 Processing...</b>")
    
    # 2. Setup Environment & Shortcuts
    # Shortcuts: c=client, m=message, r=reply, db=database
    reply_to = message.reply_to_message or message
    
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    redirected_error = sys.stderr = io.StringIO()
    
    stdout, stderr, exc = None, None, None
    start_time = time.time()
    
    try:
        # Create Async Function to allow 'await'
        await aexec(cmd, client, message, reply_to)
    except Exception:
        exc = traceback.format_exc()
    
    # 3. Capture Output
    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    
    end_time = time.time()
    taken = round(end_time - start_time, 3)

    # 4. Format Result
    evaluation = ""
    if exc:
        evaluation = exc
    elif stderr:
        evaluation = stderr
    elif stdout:
        evaluation = stdout
    else:
        evaluation = "Success (No Output)"

    # 5. Send Result
    final_output = f"<b>💻 Code:</b>\n<pre>{cmd[:50]}...</pre>\n\n<b>📤 Output:</b>\n<pre>{evaluation}</pre>\n\n<b>⏱ Taken:</b> {taken}s"
    
    if len(final_output) > 4096:
        with open("eval_output.txt", "w+", encoding="utf-8") as f:
            f.write(evaluation)
        await message.reply_document(
            "eval_output.txt",
            caption=f"<b>💻 Code:</b> `{cmd[:50]}...`\n<b>⏱ Taken:</b> {taken}s"
        )
        await status_msg.delete()
        os.remove("eval_output.txt")
    else:
        await status_msg.edit(final_output)

async def aexec(code, client, message, reply_to):
    # This wrapper allows using 'await' inside /eval
    # Pre-loaded variables for convenience
    exec(
        f"async def __aexec(client, message, r, c, m, db, temp): " +
        "".join(f"\n {l}" for l in code.split("\n"))
    )
    return await locals()["__aexec"](
        client, 
        message, 
        reply_to,      # r
        client,        # c
        message,       # m
        db,            # db
        temp           # temp
    )
