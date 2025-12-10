import discord
from discord import app_commands
from discord.ext import commands
import json
import time
from datetime import datetime
import os

# ================= CONFIG =================
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789012345678"))  # default your ID
ADMINS_ENV = os.getenv("ADMINS", "")  # optional comma-separated list of admin IDs
ADMINS = [int(uid) for uid in ADMINS_ENV.split(",") if uid.strip().isdigit()]

if not TOKEN:
    raise ValueError("Discord token is not set! Please set DISCORD_TOKEN environment variable.")

# FILES
BLOCKED_FILE = "blocked.json"
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"

# ================= HELPERS =================
def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

BLOCKED = load_json(BLOCKED_FILE)
USERS = load_json(USERS_FILE)
ADMINS_FILE_LIST = load_json(ADMINS_FILE)
ADMINS += [uid for uid in ADMINS_FILE_LIST if uid not in ADMINS]  # Merge

def is_admin(user_id):
    return user_id == OWNER_ID or user_id in ADMINS

def cleanup_expired():
    changed = False
    for uid in list(BLOCKED.keys()):
        data = BLOCKED[uid]
        if not data.get('perm') and time.time() > data.get('expire', 0):
            del BLOCKED[uid]
            changed = True
    if changed:
        save_json(BLOCKED_FILE, BLOCKED)

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

# ---------------- COMMANDS ----------------

@tree.command(name="add", description="Permanently ban a user")
@app_commands.describe(user_id="User ID to ban", reason="Reason for ban")
async def add(interaction: discord.Interaction, user_id: str, reason: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return
    BLOCKED[user_id] = {'perm': True, 'msg': reason}
    save_json(BLOCKED_FILE, BLOCKED)
    await interaction.response.send_message(f"User {user_id} permanently banned.\nReason: {reason}")

@tree.command(name="tempban", description="Temporarily ban a user")
@app_commands.describe(user_id="User ID to ban", minutes="Ban duration in minutes", reason="Reason for ban")
async def tempban(interaction: discord.Interaction, user_id: str, minutes: int, reason: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return
    expire = time.time() + (minutes * 60)
    BLOCKED[user_id] = {'perm': False, 'msg': reason, 'expire': expire}
    save_json(BLOCKED_FILE, BLOCKED)
    await interaction.response.send_message(f"User {user_id} temporarily banned for {minutes} minutes.\nReason: {reason}")

@tree.command(name="remove", description="Unban a user")
@app_commands.describe(user_id="User ID to unban")
async def remove(interaction: discord.Interaction, user_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return
    if user_id in BLOCKED:
        BLOCKED.pop(user_id)
        save_json(BLOCKED_FILE, BLOCKED)
        await interaction.response.send_message(f"User {user_id} has been unbanned.")
    else:
        await interaction.response.send_message(f"User {user_id} is not banned.")

@tree.command(name="list", description="List all blocked users")
async def list_users(interaction: discord.Interaction):
    cleanup_expired()
    if not BLOCKED:
        await interaction.response.send_message("No one is blocked.")
        return
    res = "**Blocked Users:**\n"
    for uid, data in BLOCKED.items():
        t = "PERM" if data['perm'] else f"{int((data['expire'] - time.time())/60)}m left"
        res += f"ID: {uid} [{t}] - Reason: {data['msg']}\n"
    await interaction.response.send_message(res)

@tree.command(name="clear", description="Clear all bans")
async def clear(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return
    BLOCKED.clear()
    save_json(BLOCKED_FILE, BLOCKED)
    await interaction.response.send_message("All bans cleared!")

@tree.command(name="addadmin", description="Add a new admin")
@app_commands.describe(user_id="User ID to make admin")
async def addadmin(interaction: discord.Interaction, user_id: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Only owner can add admins.", ephemeral=True)
        return
    if user_id in ADMINS:
        await interaction.response.send_message(f"User {user_id} is already an admin.")
        return
    ADMINS.append(user_id)
    save_json(ADMINS_FILE, ADMINS)
    await interaction.response.send_message(f"User {user_id} added as admin.")

# ================= RUN BOT =================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot ready as {bot.user}")

bot.run(TOKEN)
