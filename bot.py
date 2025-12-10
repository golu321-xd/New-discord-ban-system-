# =========================
# main.py (FINAL FIXED)
# =========================

import os
import json
import time
import threading
from flask import Flask
import requests
import discord
from discord import app_commands
from discord.ext import commands

# -------------------------
# Load ENV (Render)
# -------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
PORT = int(os.getenv("PORT", "8080"))

# -------------------------
# JSON Files
# -------------------------
BLOCKED_FILE = "blocked.json"
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"

def load_json(path, fallback):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return fallback

BLOCKED = load_json(BLOCKED_FILE, {})
USERS = load_json(USERS_FILE, {})
ADMINS = load_json(ADMINS_FILE, [])

WAITING = {}  # waiting for ban reason

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def save_all():
    save_json(BLOCKED_FILE, BLOCKED)
    save_json(USERS_FILE, USERS)
    save_json(ADMINS_FILE, ADMINS)

# -------------------------
# Helpers
# -------------------------
def cleanup_expired():
    now = time.time()
    changed = False

    for uid in list(BLOCKED.keys()):
        data = BLOCKED[uid]
        if not data.get("perm") and now > data.get("expire", 0):
            del BLOCKED[uid]
            changed = True

    if changed:
        save_json(BLOCKED_FILE, BLOCKED)

def is_owner(uid):
    return uid == OWNER_ID

def is_admin(uid):
    return uid in ADMINS or uid == OWNER_ID

def get_roblox_user_info(user_id: str):
    try:
        url = f"https://users.roblox.com/v1/users/{user_id}"
        data = requests.get(url, timeout=5).json()
        username = data.get("name", "Unknown")
        display = data.get("displayName", username)
        return username, display
    except:
        return "Unknown", "Unknown"

# -------------------------
# DISCORD BOT
# -------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

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
    except:
        pass
    print(f"Bot logged in as {bot.user}")

# -------------------------
# /ban
# -------------------------
@bot.tree.command(name="ban", description="Perm ban a Roblox user.")
@app_commands.describe(user_id="Roblox ID", reason="Reason (optional)")
async def ban(interaction: discord.Interaction, user_id: str, reason: str = None):

    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ You are not allowed.", ephemeral=True)

    username, display = get_roblox_user_info(user_id)

    if not reason:
        WAITING[interaction.user.id] = {"action": "ban", "target": user_id}
        return await interaction.response.send_message(
            f"PERM BAN\nName: {display} (@{username})\nID: {user_id}\n\nType ban reason.",
            ephemeral=True
        )

    BLOCKED[user_id] = {"perm": True, "msg": reason}
    save_json(BLOCKED_FILE, BLOCKED)

    embed = make_embed("PERM BANNED", username, display, user_id, footer=f"Reason: {reason}")
    await interaction.response.send_message(embed=embed)

# -------------------------
# /tempban
# -------------------------
@bot.tree.command(name="tempban", description="Temp ban a Roblox user.")
@app_commands.describe(user_id="Roblox ID", minutes="Minutes", reason="Reason (optional)")
async def tempban(interaction: discord.Interaction, user_id: str, minutes: int, reason: str = None):

    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ You are not allowed.", ephemeral=True)

    username, display = get_roblox_user_info(user_id)

    if not reason:
        WAITING[interaction.user.id] = {"action": "tempban", "target": user_id, "mins": minutes}
        return await interaction.response.send_message(
            f"TEMP BAN {minutes}m\nName: {display} (@{username})\nID: {user_id}\n\nType ban reason.",
            ephemeral=True
        )

    expire = time.time() + minutes * 60
    BLOCKED[user_id] = {"perm": False, "msg": reason, "expire": expire}
    save_json(BLOCKED_FILE, BLOCKED)

    embed = make_embed(f"TEMP BANNED ({minutes}m)", username, display, user_id, footer=f"Reason: {reason}")
    await interaction.response.send_message(embed=embed)

# -------------------------
# /unban
# -------------------------
@bot.tree.command(name="unban", description="Unban a Roblox user.")
async def unban(interaction: discord.Interaction, user_id: str):

    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Not allowed.", ephemeral=True)

    username, display = get_roblox_user_info(user_id)

    BLOCKED.pop(user_id, None)
    save_json(BLOCKED_FILE, BLOCKED)

    embed = make_embed("UNBANNED", username, display, user_id)
    await interaction.response.send_message(embed=embed)

# -------------------------
# /list
# -------------------------
@bot.tree.command(name="list", description="List all banned users.")
async def list_bans(interaction: discord.Interaction):

    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Not allowed.", ephemeral=True)

    cleanup_expired()

    if not BLOCKED:
        return await interaction.response.send_message("No one is banned.", ephemeral=True)

    result = ""

    for i, (uid, data) in enumerate(BLOCKED.items(), 1):
        username, display = get_roblox_user_info(uid)

        if data.get("perm"):
            status = "PERM"
        else:
            left = int((data["expire"] - time.time()) / 60)
            status = f"{left}m left"

        result += f"{i}. {display} (@{username}) | ID: {uid} | {status}\nReason: {data['msg']}\n\n"

    if len(result) > 1900:
        await interaction.response.send_message("Sending file...", ephemeral=True)
        return await interaction.followup.send(
            file=discord.File(fp=bytes(result, "utf-8"), filename="banned.txt")
        )

    await interaction.response.send_message(f"**BANNED USERS:**\n{result}", ephemeral=True)

# -------------------------
# /clear
# -------------------------
@bot.tree.command(name="clear", description="Clear all bans.")
async def clear(interaction: discord.Interaction):

    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Not allowed.", ephemeral=True)

    BLOCKED.clear()
    save_json(BLOCKED_FILE, BLOCKED)

    await interaction.response.send_message("All bans cleared!", ephemeral=True)

# -------------------------
# /addadmin
# -------------------------
@bot.tree.command(name="addadmin", description="Add an admin (Owner only).")
async def add_admin(interaction: discord.Interaction, discord_user_id: str):

    if not is_owner(interaction.user.id):
        return await interaction.response.send_message("❌ Only owner can add admins.", ephemeral=True)

    try:
        uid = int(discord_user_id)
    except:
        return await interaction.response.send_message("Invalid ID.", ephemeral=True)

    if uid not in ADMINS:
        ADMINS.append(uid)
        save_json(ADMINS_FILE, ADMINS)

    await interaction.response.send_message(f"Added admin: {uid}", ephemeral=True)

# -------------------------
# Read reason from normal message
# -------------------------
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    uid = message.author.id

    if uid in WAITING:
        data = WAITING.pop(uid)
        target = data["target"]
        reason = message.content.strip()

        username, display = get_roblox_user_info(target)

        if data["action"] == "ban":
            BLOCKED[target] = {"perm": True, "msg": reason}

        else:
            expire = time.time() + data["mins"] * 60
            BLOCKED[target] = {"perm": False, "msg": reason, "expire": expire}

        save_json(BLOCKED_FILE, BLOCKED)

        title = "PERM BANNED" if data["action"] == "ban" else f"TEMP BANNED ({data['mins']}m)"
        embed = make_embed(title, username, display, target, footer=f"Reason: {reason}")

        await message.channel.send(embed=embed)

    await bot.process_commands(message)

# -------------------------
# FLASK SERVER
# -------------------------
app = Flask(__name__)

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
    if data:
        if data.get("perm") or time.time() < data.get("expire", 0):
            return data.get("msg", "Banned")
    return ""

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# -------------------------
# RUN
# -------------------------
if __name__ == "__bot__":
    save_all()
    threading.Thread(target=run_flask).start()
    bot.run(DISCORD_TOKEN)
