# ===================================== IMPORTS =====================================
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from flask import Flask
from threading import Thread

# ===================================== WEB SERVER =====================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 8080))  # Render sets $PORT
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===================================== BOT SETUP =====================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.has_started = False

# ===================================== CHANNEL CONFIG =====================================
CHANNELS_FILE = "channels.json"

def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        return {}
    with open(CHANNELS_FILE, "r") as f:
        return json.load(f)

def save_channels(channels):
    with open(CHANNELS_FILE, "w") as f:
        json.dump(channels, f, indent=4)

def get_channel_id(guild_id, key):
    channels = load_channels()
    return channels.get(str(guild_id), {}).get(key)

def set_channel_id(guild_id, key, channel_id):
    channels = load_channels()
    if str(guild_id) not in channels:
        channels[str(guild_id)] = {}
    channels[str(guild_id)][key] = channel_id
    save_channels(channels)

# ===================================== CHANNEL COMMAND =====================================
class ChannelConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="channel", description="Set a bot channel for this server")
    @app_commands.describe(
        type="Type of channel: staff or partnership",
        channel="The text channel to set"
    )
    async def channel(self, interaction: discord.Interaction, type: str, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator.", ephemeral=True)
            return

        type = type.lower()
        if type not in ["staff", "partnership"]:
            await interaction.response.send_message("❌ Invalid type. Use `staff` or `partnership`.", ephemeral=True)
            return

        set_channel_id(interaction.guild.id, type, channel.id)
        await interaction.response.send_message(f"✅ `{type}` channel set to {channel.mention}!", ephemeral=True)

# ===================================== REQUEST MODAL =====================================
class Requests(discord.ui.Modal, title="Request Form"):
    short_input = discord.ui.TextInput(label="Your Request")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"✅ Request submitted: {self.short_input.value}", ephemeral=True)

        try:
            dm_channel = await interaction.user.create_dm()
            await dm_channel.send(f"📨 **Request Submitted**\n**Your request:** {self.short_input.value}\n*Sent to staff!*")
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Couldn't send DM! Enable DMs from server members.", ephemeral=True)

        staff_channel_id = get_channel_id(interaction.guild.id, "staff")
        staff_channel = interaction.client.get_channel(staff_channel_id)
        if staff_channel:
            await staff_channel.send(
                f"🎯 **New Request Submitted**\n"
                f"**User:** {interaction.user.mention} ({interaction.user.id})\n"
                f"**Request:** {self.short_input.value}\n"
                f"**Channel:** {interaction.channel.mention if interaction.channel else 'DM'}\n"
                f"**Time:** {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        else:
            print("❌ Staff channel not configured for this server")

# ===================================== PARTNERSHIP MODAL =====================================
class Partnership(discord.ui.Modal, title="Partnerships Application"):
    username = discord.ui.TextInput(label="Your UserID or Username", placeholder="Enter your Discord ID or username...", required=True, max_length=50)
    server_name = discord.ui.TextInput(label="Server Link", placeholder="https://discord.gg/...", required=True, max_length=150)
    reason = discord.ui.TextInput(label="Why do you want to partner?", style=discord.TextStyle.paragraph, required=True, min_length=50, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Your partnership application has been submitted!", ephemeral=True)
        try:
            dm_channel = await interaction.user.create_dm()
            await dm_channel.send(
                f"🤝 **Partnership Application Received**\n\n"
                f"**Username:** {self.username}\n**Server:** {self.server_name}\n**Reason:** {self.reason}"
            )
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Couldn't send DM! Enable DMs from server members.", ephemeral=True)

        staff_channel_id = get_channel_id(interaction.guild.id, "staff")
        partnership_channel_id = get_channel_id(interaction.guild.id, "partnership")
        staff_channel = interaction.client.get_channel(staff_channel_id)
        partnership_channel = interaction.client.get_channel(partnership_channel_id)

        if staff_channel:
            embed = discord.Embed(title="🤝 New Partnership Application", color=0x5865F2, timestamp=discord.utils.utcnow())
            embed.add_field(name="Applicant", value=f"{interaction.user.mention}\n`{self.username}`", inline=True)
            embed.add_field(name="User ID", value=interaction.user.id, inline=True)
            embed.add_field(name="Server Link", value=self.server_name, inline=False)
            embed.add_field(name="Reason", value=self.reason, inline=False)
            embed.set_footer(text="Use buttons to accept or deny")
            view = StaffDecisionView(interaction.user.id, str(self.username), self.server_name, self.reason)
            await staff_channel.send(embed=embed, view=view)
        else:
            print("❌ Staff channel not configured for this server")

        if partnership_channel:
            await partnership_channel.send(f"🎯 **New Partnership!!**\n**Partner:** {self.username}\n**Server:** {self.server_name}")

# ===================================== STAFF DECISION VIEW =====================================
class StaffDecisionView(discord.ui.View):
    def __init__(self, user_id, username, server_link, reason):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.username = username
        self.server_link = server_link
        self.reason = reason

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        embed = interaction.message.embeds[0]
        embed.color = 0x00ff00
        embed.add_field(name="Status", value="✅ **ACCEPTED**", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(f"🎉 Your partnership application was **ACCEPTED**!\nServer: {self.server_link}\nReason: {self.reason}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Could not send DM to user.", ephemeral=True)

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        embed = interaction.message.embeds[0]
        embed.color = 0xff0000
        embed.add_field(name="Status", value="❌ **DENIED**", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(f"❌ Your partnership application was denied.\nServer: {self.server_link}\nReason: {self.reason}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Could not send DM to user.", ephemeral=True)

# ===================================== SLASH COMMANDS =====================================
@bot.tree.command(name="request", description="Send a request to the staff")
async def request_command(interaction: discord.Interaction):
    await interaction.response.send_modal(Requests())

@bot.tree.command(name="partnerships", description="Fill out a partnership application")
async def partnerships_command(interaction: discord.Interaction):
    await interaction.response.send_modal(Partnership())

# ===================================== ON READY =====================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.tree.add_command(ChannelConfig(bot).channel)
    await bot.tree.sync()
    print("✅ Commands synced globally")

# ===================================== RUN =====================================
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
