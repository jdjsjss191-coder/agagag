import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
import datetime
import sqlite3
import random
import string
from datetime import timedelta

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Setup Intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class VanityBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = None
    
    async def setup_hook(self):
        # Initialize Database
        self.db = sqlite3.connect("vanity.db")
        cursor = self.db.cursor()
        
        # Create Tables
        cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            duration TEXT,
            expiration TIMESTAMP,
            is_redeemed INTEGER DEFAULT 0,
            redeemed_by INTEGER,
            hwid TEXT
        )''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS blacklists (
            user_id INTEGER PRIMARY KEY
        )''')
        
        self.db.commit()
        
        # This syncs the slash commands to Discord
        await self.tree.sync()
        print(f"✅ Slash commands synced and Database ready!")

bot = VanityBot()

# --- SECURITY CHECK HELPER ---
async def check_security(interaction: discord.Interaction):
    owner_name = os.getenv('OWNER_NAME', 'y9pv')
    
    # Check if user is blacklisted
    cursor = bot.db.cursor()
    cursor.execute("SELECT user_id FROM blacklists WHERE user_id = ?", (interaction.user.id,))
    if cursor.fetchone():
        await interaction.response.send_message("❌ You are blacklisted from using this panel.", ephemeral=True)
        return False

    # Check for Owner name
    if interaction.user.name != owner_name:
        await interaction.response.send_message(f"❌ user mismatch (expected {owner_name})", ephemeral=True)
        return False
    
    # Check for Owner role
    has_role = discord.utils.get(interaction.user.roles, name="Owner")
    if not has_role:
        await interaction.response.send_message("❌ role mismatch", ephemeral=True)
        return False
        
    return True

def generate_key_string():
    return "VANITY-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

@bot.event
async def on_ready():
    print(f'✅ Vanity Bot is online! Logged in as {bot.user}')

# --- UI COMPONENTS FOR SCRIPT PANEL ---

class RedeemModal(discord.ui.Modal, title="Redeem Your Key"):
    key_input = discord.ui.TextInput(
        label="Enter License Key",
        placeholder="VANITY-XXXX-XXXX-XXXX",
        min_length=10,
        max_length=50,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        key_code = self.key_input.value
        cursor = bot.db.cursor()
        
        # Check if user is blacklisted
        cursor.execute("SELECT user_id FROM blacklists WHERE user_id = ?", (interaction.user.id,))
        if cursor.fetchone():
            return await interaction.response.send_message("❌ You are blacklisted.", ephemeral=True)

        cursor.execute("SELECT key, is_redeemed, expiration FROM keys WHERE key = ?", (key_code,))
        row = cursor.fetchone()
        
        if not row:
            return await interaction.response.send_message("❌ Invalid key.", ephemeral=True)
        
        if row[1] == 1:
            return await interaction.response.send_message("❌ This key has already been redeemed.", ephemeral=True)

        # Update DB
        cursor.execute("UPDATE keys SET is_redeemed = 1, redeemed_by = ? WHERE key = ?", (interaction.user.id, key_code))
        bot.db.commit()
        
        await interaction.response.send_message(
            f"✅ Successfully redeemed key! Your subscription is now active.",
            ephemeral=True
        )

class VanityPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view

    @discord.ui.button(label="Redeem Key", style=discord.ButtonStyle.danger, custom_id="vanity:redeem")
    async def redeem_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RedeemModal())

    @discord.ui.button(label="Get Key", style=discord.ButtonStyle.secondary, custom_id="vanity:get_key")
    async def get_key_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor = bot.db.cursor()
        
        # Check if user is blacklisted
        cursor.execute("SELECT user_id FROM blacklists WHERE user_id = ?", (interaction.user.id,))
        if cursor.fetchone():
            return await interaction.response.send_message("❌ You are blacklisted.", ephemeral=True)

        # Check for active subscription
        cursor.execute("SELECT key FROM keys WHERE redeemed_by = ?", (interaction.user.id,))
        if not cursor.fetchone():
            return await interaction.response.send_message("❌ You need to redeem a key before you can get the script.", ephemeral=True)

        await interaction.response.send_message(f"```lua\nPrint(\"vanitynotoutyetlmao\")\n```", ephemeral=True)

    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.secondary, custom_id="vanity:reset_hwid")
    async def reset_hwid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor = bot.db.cursor()
        
        # Check if user is blacklisted
        cursor.execute("SELECT user_id FROM blacklists WHERE user_id = ?", (interaction.user.id,))
        if cursor.fetchone():
            return await interaction.response.send_message("❌ You are blacklisted.", ephemeral=True)

        # Check for active subscription
        cursor.execute("SELECT key FROM keys WHERE redeemed_by = ?", (interaction.user.id,))
        if not cursor.fetchone():
            return await interaction.response.send_message("❌ You need to redeem a key before you can reset your HWID.", ephemeral=True)

        await interaction.response.send_message(
            "✅ Your key HWID has been reset and can now be used on different executors.",
            ephemeral=True
        )

# --- MODERATION SLASH COMMANDS ---

@bot.tree.command(name="ban", description="Bans a member (Owner Only)")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not await check_security(interaction): return
    
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f'🔨 **{member}** has been banned. Reason: {reason}')
    except Exception as e:
        await interaction.response.send_message(f'❌ Failed to ban: {e}', ephemeral=True)

@bot.tree.command(name="kick", description="Kicks a member (Owner Only)")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not await check_security(interaction): return
    
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f'👢 **{member}** has been kicked. Reason: {reason}')
    except Exception as e:
        await interaction.response.send_message(f'❌ Failed to kick: {e}', ephemeral=True)

@bot.tree.command(name="mute", description="Mutes a member for a set duration (Owner Only)")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 60):
    if not await check_security(interaction): return
    
    try:
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=f"Muted by {interaction.user}")
        await interaction.response.send_message(f'🔇 **{member}** has been muted for {minutes} minutes.')
    except Exception as e:
        await interaction.response.send_message(f'❌ Failed to mute: {e}', ephemeral=True)

@bot.tree.command(name="unmute", description="Removes the mute from a member (Owner Only)")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    if not await check_security(interaction): return
    
    try:
        await member.timeout(None)
        await interaction.response.send_message(f'🔊 **{member}** has been unmuted.')
    except Exception as e:
        await interaction.response.send_message(f'❌ Failed to unmute: {e}', ephemeral=True)

# --- PUBLIC SLASH COMMANDS ---

@bot.tree.command(name="viewprofile", description="Shows the profile picture of a member")
async def viewprofile(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    
    embed = discord.Embed(
        title=f"👤 Profile: {member.display_name}",
        color=discord.Color.red()
    )
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="scriptpanel", description="Sends the Vanity Script management panel (Owner Only)")
async def scriptpanel(interaction: discord.Interaction):
    if not await check_security(interaction): return

    embed = discord.Embed(
        title="Vanity Script | Control Panel",
        description=(
            "Welcome to the Vanity management interface. Use the buttons below to manage your license and hardware identification.\n\n"
            "**Available Actions:**\n"
            "> Redeem Key: Activate your subscription.\n"
            "> Get Key: Information on how to obtain access.\n"
            "> Reset HWID: Resets ur key hwid to be used on different executors.\n\n"
            "*Status: System Operational*"
        ),
        color=discord.Color.from_rgb(255, 0, 0), # Pure Red
        timestamp=datetime.datetime.now()
    )
    
    # You can add a banner image here if you have one
    # embed.set_image(url="https://your-image-url.com/banner.png")
    embed.set_footer(text="Vanity Exploit • Premium Security", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

    await interaction.response.send_message(embed=embed, view=VanityPanelView())

# --- ADMIN KEY COMMANDS ---

@bot.tree.command(name="generatescript", description="Generates a Vanity key (Owner Only)")
@app_commands.describe(
    member="The member to generate a key for",
    value="Number of units (e.g. 10)",
    unit="The unit of time",
    destination="Where to send the key"
)
async def generatescript(
    interaction: discord.Interaction, 
    member: discord.Member, 
    value: int = 1, 
    unit: str = "lifetime", 
    destination: str = "channel"
):
    if not await check_security(interaction): return

    new_key = generate_key_string()
    expiration = None
    
    if unit.lower() != "lifetime":
        now = datetime.datetime.now()
        if unit == "minutes": expiration = now + timedelta(minutes=value)
        elif unit == "hours": expiration = now + timedelta(hours=value)
        elif unit == "weeks": expiration = now + timedelta(weeks=value)
        elif unit == "months": expiration = now + timedelta(days=value*30)
        else: expiration = None # Default to lifetime if unit invalid

    # Save to DB
    cursor = bot.db.cursor()
    cursor.execute("INSERT INTO keys (key, duration, expiration, is_redeemed, hwid) VALUES (?, ?, ?, ?, ?)", 
                   (new_key, f"{value} {unit}", expiration, 0, None))
    bot.db.commit()

    msg = f"Generated a Vanity key for {member.mention}\nKey: `{new_key}`\nDuration: **{value} {unit}**"
    
    if destination == "dm":
        try:
            await member.send(msg)
            await interaction.response.send_message(f"✅ Key sent to {member.mention}'s DMs.", ephemeral=True)
        except:
            await interaction.response.send_message(f"❌ Failed to DM {member.mention}. Key shown here: `{new_key}`", ephemeral=True)
    else:
        await interaction.response.send_message(f"{interaction.user.mention} generated a vanity key for {member.mention}\n`{new_key}`")

@bot.tree.command(name="blacklist", description="Blacklists a user from the script (Owner Only)")
async def blacklist(interaction: discord.Interaction, member: discord.Member):
    if not await check_security(interaction): return

    cursor = bot.db.cursor()
    cursor.execute("INSERT OR IGNORE INTO blacklists (user_id) VALUES (?)", (member.id,))
    # Wipe their keys
    cursor.execute("DELETE FROM keys WHERE redeemed_by = ?", (member.id,))
    bot.db.commit()

    await interaction.response.send_message(f"🚫 **{member}** has been blacklisted and their keys have been wiped.")

@bot.tree.command(name="unblacklist", description="Unblacklist a user")
async def unblacklist(interaction: discord.Interaction, user: discord.Member):
    if not await check_security(interaction): return
    
    cursor = bot.db.cursor()
    cursor.execute("DELETE FROM blacklists WHERE user_id = ?", (user.id,))
    bot.db.commit()
    await interaction.response.send_message(f"✅ {user.mention} has been unblacklisted.", ephemeral=True)

@bot.tree.command(name="resethwid", description="Reset the HWID bound to a key")
async def resethwid(interaction: discord.Interaction, key: str):
    if not await check_security(interaction): return
    
    cursor = bot.db.cursor()
    cursor.execute("SELECT is_redeemed FROM keys WHERE key = ?", (key,))
    row = cursor.fetchone()
    
    if not row:
        await interaction.response.send_message("❌ Key not found.", ephemeral=True)
        return
    
    cursor.execute("UPDATE keys SET hwid = NULL WHERE key = ?", (key,))
    bot.db.commit()
    await interaction.response.send_message(f"✅ HWID for key `{key}` has been reset.", ephemeral=True)

# Run the bot
if TOKEN:
    bot.run(TOKEN)
else:
    print("⚠️ DISCORD_TOKEN not found in variables. Please add it to start the bot.")
