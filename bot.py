import discord
from discord import app_commands
from discord.ext import commands
import json
import time
import os   # <-- ADD
# ---------------------------
# Load admins + bans
# ---------------------------
with open("admins.json", "r") as f:
    admins = json.load(f)

OWNER_ID = int(admins["owner"])
ADMIN_LIST = admins["admins"]

with open("bans.json", "r") as f:
    BANS = json.load(f)

# Save function
def save_bans():
    with open("bans.json", "w") as f:
        json.dump(BANS, f, indent=4)

# Check functions
def is_owner(uid):
    return uid == OWNER_ID

def is_admin(uid):
    return uid == OWNER_ID or str(uid) in ADMIN_LIST

# ---------------------------
# Bot setup
# ---------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

# ------------------------------------------------------
# /addadmin   (OWNER ONLY)
# ------------------------------------------------------
@bot.tree.command(name="addadmin", description="Owner kisi ko admin bana sakta hai")
async def addadmin(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction.user.id):
        return await interaction.response.send_message("❌ Sirf owner hi admin bana sakta hai.", ephemeral=True)

    if str(user.id) in ADMIN_LIST:
        return await interaction.response.send_message("⚠ Ye user already admin hai.", ephemeral=True)

    ADMIN_LIST.append(str(user.id))
    admins["admins"] = ADMIN_LIST

    with open("admins.json", "w") as f:
        json.dump(admins, f, indent=4)

    await interaction.response.send_message(f"✅ {user.mention} ab ADMIN ban chuka hai!")

# ------------------------------------------------------
# /ban   (PERMANENT BAN)
# ------------------------------------------------------
@bot.tree.command(name="ban", description="Permanent ban kare (Admin Only)")
async def ban(interaction: discord.Interaction, userid: str, reason: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Ye command admins ke liye hai.", ephemeral=True)

    BANS[userid] = {"type": "perm", "reason": reason}
    save_bans()

    await interaction.response.send_message(
        f"🔨 User `{userid}` permanently banned!\n📄 Reason: {reason}"
    )

# ------------------------------------------------------
# /tempban
# ------------------------------------------------------
@bot.tree.command(name="tempban", description="Temporary ban kare (Admin Only)")
async def tempban(interaction: discord.Interaction, userid: str, minutes: int, reason: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Ye command admins ke liye hai.", ephemeral=True)

    expire = time.time() + (minutes * 60)

    BANS[userid] = {"type": "temp", "reason": reason, "expire": expire}
    save_bans()

    await interaction.response.send_message(
        f"⏳ User `{userid}` {minutes} minutes ke liye ban ho gaya.\n📄 Reason: {reason}"
    )

# ------------------------------------------------------
# /unban
# ------------------------------------------------------
@bot.tree.command(name="unban", description="User ka ban hatao (Admin Only)")
async def unban(interaction: discord.Interaction, userid: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Ye command admins ke liye hai.", ephemeral=True)

    if userid not in BANS:
        return await interaction.response.send_message("⚠ Ye user banned hi nahi hai.", ephemeral=True)

    del BANS[userid]
    save_bans()

    await interaction.response.send_message(f"🟢 User `{userid}` unbanned!")

# ------------------------------------------------------
# Start bot (ENV TOKEN)
# ------------------------------------------------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")   # <-- railway/env se lega

bot.run(TOKEN)
