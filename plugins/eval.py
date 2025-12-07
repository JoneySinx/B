import sys
import os
import traceback
import html
from io import StringIO
from hydrogram import Client, filters
from hydrogram.errors import MessageTooLong
from info import ADMINS

# यदि आप चाहते हैं कि eval के अंदर database का उपयोग हो सके, तो उन्हें यहाँ इम्पोर्ट करें
# from database.users_chats_db import db
# from utils import temp

@Client.on_message(filters.command("eval") & filters.user(ADMINS))
async def executor(client, message):
    try:
        code = message.text.split(" ", 1)[1]
    except IndexError:
        return await message.reply('<b>Command Incomplete!</b>\nUsage: <code>/eval print("Hello")</code>')
        
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()
    stdout, stderr, exc = None, None, None
    
    try:
        await aexec(code, client, message)
    except Exception:
        exc = traceback.format_exc()
        
    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    
    evaluation = ""
    if exc:
        evaluation = exc
    elif stderr:
        evaluation = stderr
    elif stdout:
        evaluation = stdout
    else:
        evaluation = "Success!"
        
    # HTML escape बहुत जरूरी है ताकि टेलीग्राम HTML पार्सिंग एरर न दे
    final_output = f"<b>Output:</b>\n\n<pre>{html.escape(evaluation)}</pre>"
    
    try:
        await message.reply(final_output)
    except MessageTooLong:
        # यदि मैसेज बहुत बड़ा है तो फाइल के रूप में भेजें
        try:
            with open('eval.txt', 'w+', encoding='utf-8') as outfile:
                outfile.write(str(evaluation))
            await message.reply_document('eval.txt', caption="Evaluation Result")
        except Exception as e:
            await message.reply(f"<b>Error sending file:</b> {e}")
        finally:
            if os.path.exists('eval.txt'):
                os.remove('eval.txt')

async def aexec(code, client, message):
    # exec को async context में लपेटना
    exec(
        "async def __aexec(client, message): "
        + "".join(f"\n {a}" for a in code.split("\n"))
    )
    return await locals()["__aexec"](client, message)
