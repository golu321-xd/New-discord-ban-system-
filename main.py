# main.py
import os
import json
import time
import threading
from datetime import datetime
from flask import Flask
import requests
import discord
from discord import app_commands
from discord.ext import commands

# ---------- Load env from Render ONLY ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
PORT = int(os.getenv("PORT", "8080"))

# ---------- Files ----------
BLOCKED_FILE = "blocked.json"
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

def load_admins():
    try:
        with open(ADMINS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

BLOCKED = load_json(BLOCKED_FILE)
USERS = load_json(USERS_FILE)
ADMINS = load_admins()  
WAITING = {}  

# ---------- Helpers ----------
def save_all():
    save_json(BLOCKED_FILE, BLOCKED)
    save_json(USERS_FILE, USERS)
    save_json(ADMINS_FILE, ADMINS)

def cleanup_expired():
    changed = False
    for uid in list(BLOCKED.keys()):
        data = BLOCKED[uid]
        if not data.get("perm") and time.time() > data.get("expire", 0):
            del BLOCKED[uid]
            changed = True
    if changed:
        save_json(BLOCKED_FILE, BLOCKED)

def is_owner(discord_user_id: int):
    return discord_user_id == OWNER_ID

def is_admin(discord_user_id: int):
    return discord_user_id in ADMINS or is_owner(discord_user_id)

def get_roblox_user_info(user_id: str):
    try:
        url = f"https://users.roblox.com/v1/users/{user_id}"
        data = requests.get(url, timeout=5).json()
        username = data.get("name", "Unknown")
        display = data.get("displayName", username)
        return username, display
    except:
        return "Unknown", "Unknown"

# ---------- DISCORD BOT ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)

def make_embed(title, username, display, user_id, footer=None):
    embed = discord.Embed(title=title, color=0x2ecc71)
    embed.add_field(name="Username", value=f"@{username}", inline=False)
    embed.add_field(name="Display Name", value=display, inline=False)
    embed.add_field(name="User ID", value=str(user_id), inline=False)
    if footer:
        embed.set_footer(text=footer)
    return embed

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception:
        pass
    print("Bot ready:", bot.user)

# --- /ban ---
@bot.tree.command(name="ban", description="Perm ban a roblox user. Owner/Admin only.")
@app_commands.describe(user_id="Roblox user id", reason="Reason (optional)")
async def ban(interaction: discord.Interaction, user_id: str, reason: str = None):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ You are not allowed.", ephemeral=True)

    username, display = get_roblox_user_info(user_id)

    if not reason:
        WAITING[interaction.user.id] = {'action': 'ban', 'target_id': user_id}
        return await interaction.response.send_message(
            f"PERM BAN\nName: {display} (@{username})\nID: {user_id}\n\nType ban reason.",
            ephemeral=True
        )

    BLOCKED[user_id] = {'perm': True, 'msg': reason}
    save_json(BLOCKED_FILE, BLOCKED)
    embed = make_embed("PERM BANNED", username, display, user_id, footer=f"Reason: {reason}")
    await interaction.response.send_message(embed=embed)

# --- /tempban ---
@bot.tree.command(name="tempban", description="Temp ban a roblox user.")
@app_commands.describe(user_id="Roblox user id", minutes="Minutes", reason="Reason (optional)")
async def tempban(interaction: discord.Interaction, user_id: str, minutes: int, reason: str = None):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ You are not allowed.", ephemeral=True)

    username, display = get_roblox_user_info(user_id)

    if not reason:
        WAITING[interaction.user.id] = {'action': 'tempban', 'target_id': user_id, 'mins': minutes}
        return await interaction.response.send_message(
            f"TEMP BAN ({minutes}m)\nName: {display} (@{username})\nID: {user_id}\n\nType ban reason.",
            ephemeral=True
        )

    expire = time.time() + minutes * 60
    BLOCKED[user_id] = {'perm': False, 'msg': reason, 'expire': expire}
    save_json(BLOCKED_FILE, BLOCKED)
    embed = make_embed(f"TEMP BANNED ({minutes}m)", username, display, user_id, footer=f"Reason: {reason}")
    await interaction.response.send_message(embed=embed)

# --- /unban ---
@bot.tree.command(name="unban", description="Unban a roblox user.")
async def unban(interaction: discord.Interaction, user_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ You are not allowed.", ephemeral=True)

    username, display = get_roblox_user_info(user_id)
    BLOCKED.pop(user_id, None)
    save_json(BLOCKED_FILE, BLOCKED)

    embed = make_embed("UNBANNED", username, display, user_id)
    await interaction.response.send_message(embed=embed)

# --- /list ---
@bot.tree.command(name="list", description="List blocked users.")
async def _list(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Not allowed.", ephemeral=True)

    cleanup_expired()

    if not BLOCKED:
        return await interaction.response.send_message("No one blocked.", ephemeral=True)

    res = ""
    for i, (uid, data) in enumerate(BLOCKED.items(), start=1):
        username, display = get_roblox_user_info(uid)
        if data.get("perm"):
            t = "PERM"
        else:
            left = int((data["expire"] - time.time()) / 60)
            t = f"{left}m left"
        res += f"{i}. {display} (@{username}) | ID: {uid} | {t}\nReason: {data.get('msg','')}\n\n"

    if len(res) > 1900:
        await interaction.response.send_message("Sending file...", ephemeral=True)
        return await interaction.followup.send(file=discord.File(fp=bytes(res, "utf-8"), filename="blocked.txt"))

    await interaction.response.send_message(f"**BLOCKED USERS:**\n{res}", ephemeral=True)

# --- /clear ---
@bot.tree.command(name="clear", description="Clear all bans.")
async def clear(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Not allowed.", ephemeral=True)

    BLOCKED.clear()
    save_json(BLOCKED_FILE, BLOCKED)
    await interaction.response.send_message("All bans cleared!", ephemeral=True)

# --- /addadmin ---
@bot.tree.command(name="addadmin", description="Add admin (Owner only).")
@app_commands.describe(discord_user_id="Discord user ID to add as admin")
async def addadmin(interaction: discord.Interaction, discord_user_id: str):
    if not is_owner(interaction.user.id):
        return await interaction.response.send_message("❌ Only owner can add admins.", ephemeral=True)

    try:
        did = int(discord_user_id)
    except:
        return await interaction.response.send_message("Invalid ID.", ephemeral=True)

    if did not in ADMINS:
        ADMINS.append(did)
        save_json(ADMINS_FILE, ADMINS)

    await interaction.response.send_message(f"Admin added: {did}\nAdmins: {ADMINS}", ephemeral=True)

# --- message listener ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    if uid in WAITING:
        info = WAITING.pop(uid)
        target = info["target_id"]
        reason = message.content.strip()
        action = info["action"]

        username, display = get_roblox_user_info(target)

        if action == "ban":
            BLOCKED[target] = {"perm": True, "msg": reason}
            save_json(BLOCKED_FILE, BLOCKED)
            embed = make_embed("PERM BANNED", username, display, target, footer=f"Reason: {reason}")
            await message.channel.send(embed=embed)

        elif action == "tempban":
            mins = info["mins"]
            expire = time.time() + mins * 60
            BLOCKED[target] = {"perm": False, "msg": reason, "expire": expire}
            save_json(BLOCKED_FILE, BLOCKED)
            embed = make_embed(f"TEMP BANNED ({mins}m)", username, display, target, footer=f"Reason: {reason}")
            await message.channel.send(embed=embed)

        return

    await bot.process_commands(message)

# ---------- FLASK (Roblox APIs) ----------
app = Flask("web")

@app.route("/check/<user_id>")
def check(user_id):
    cleanup_expired()
    data = BLOCKED.get(user_id, {})
    if data.get("perm") or (not data.get("perm") and time.time() < data.get("expire", 0)):
        return "true"
    return "false"

@app.route("/track/<user_id>/<username>/<display>")
def track(user_id, username, display):
    USERS[user_id] = {"username": username, "display": display, "time": time.time()}
    save_json(USERS_FILE, USERS)
    return "OK"

@app.route("/reason/<user_id>")
def reason(user_id):
    cleanup_expired()
    data = BLOCKED.get(user_id, {})
    if data and (data.get("perm") or time.time() < data.get("expire", 0)):
        return data.get("msg", "Banned")
    return ""

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    save_json(BLOCKED_FILE, BLOCKED)
    save_json(USERS_FILE, USERS)
    save_json(ADMINS_FILE, ADMINS)

    threading.Thread(target=run_flask).start()
    bot.run(DISCORD_TOKEN)
