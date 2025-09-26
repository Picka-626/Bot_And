# ===================================== IMPORTS =====================================
import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# ===================================== WEB SERVER =====================================
from flask import Flask
from threading import Thread

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

# ===================================== CHANNEL CONFIG =====================================
guild_channels = {}
CONFIG_FILE = "channels.json"

def load_channels():
    global guild_channels
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            guild_channels = json.load(f)
    else:
        guild_channels = {}
        # maak een lege file aan zodat hij ook in je repo staat
        with open(CONFIG_FILE, "w") as f:
            json.dump(guild_channels, f, indent=4)

def save_channels():
    with open(CONFIG_FILE, "w") as f:
        json.dump(guild_channels, f, indent=4)

def get_staff_channel(guild: discord.Guild):
    guild_id = str(guild.id)
    channel_id = guild_channels.get(guild_id, {}).get("staff")
    return guild.get_channel(channel_id) if channel_id else None

def get_partner_channel(guild: discord.Guild):
    guild_id = str(guild.id)
    channel_id = guild_channels.get(guild_id, {}).get("partner")
    return guild.get_channel(channel_id) if channel_id else None

# ===================================== BOT SETUP =====================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.has_started = False
load_channels()

GUILD_ID = int(os.environ.get("GUILD_ID"))

# ====================== SLASH COMMAND TO SET CHANNELS ======================
@bot.tree.command(name="setchannel", description="Set staff or partner channel")
@app_commands.describe(channel_type="Which channel to set", channel="Mention the channel")
async def setchannel(interaction: discord.Interaction, channel_type: str, channel: discord.TextChannel):
    guild_id = str(interaction.guild.id)

    if channel_type.lower() not in ["staff", "partner"]:
        await interaction.response.send_message("❌ Choose either `staff` or `partner`.", ephemeral=True)
        return

    if guild_id not in guild_channels:
        guild_channels[guild_id] = {}

    guild_channels[guild_id][channel_type.lower()] = channel.id
    save_channels()

    await interaction.response.send_message(
        f"✅ {channel_type.capitalize()} channel set to {channel.mention}",
        ephemeral=True
    )

@setchannel.autocomplete("channel_type")
async def channel_type_autocomplete(interaction: discord.Interaction, current: str):
    options = ["staff", "partner"]
    return [
        app_commands.Choice(name=o, value=o)
        for o in options if current.lower() in o.lower()
    ]

# ====================== REQUEST MODAL ======================
class Requests(discord.ui.Modal, title="Request Form"):
    short_input = discord.ui.TextInput(label="Your Request")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"✅ Request submitted: {self.short_input.value}",
            ephemeral=True
        )

        try:
            dm_channel = await interaction.user.create_dm()
            await dm_channel.send(
                f"📨 **Request Submitted**\n"
                f"**Your request:** {self.short_input.value}\n"
                f"*This has been sent to the staff team!*"
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ I couldn't DM you! Please enable DMs from server members.",
                ephemeral=True
            )

        staff_channel = get_staff_channel(interaction.guild)
        if staff_channel:
            await staff_channel.send(
                f"🎯 **New Request Submitted**\n"
                f"**User:** {interaction.user.mention} ({interaction.user.id})\n"
                f"**Request:** {self.short_input.value}\n"
                f"**Channel:** {interaction.channel.mention if interaction.channel else 'DM'}\n"
                f"**Time:** {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        else:
            await interaction.followup.send(
                "⚠️ Staff channel not set. Use `/setchannel staff #channel` first.",
                ephemeral=True
            )

# ====================== STAFF DECISION VIEW ======================
class StaffDecisionView(discord.ui.View):
    def __init__(self, user_id, username, server_link, reason):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.username = username
        self.server_link = server_link
        self.reason = reason

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success, custom_id="accept_partnership")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = 0x00ff00
        embed.add_field(name="Status", value="✅ **ACCEPTED**", inline=False)
        embed.add_field(name="Accepted by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Accepted at", value=discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC'), inline=True)

        await interaction.response.edit_message(embed=embed, view=self)

        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(
                f"🎉 **Partnership Application ACCEPTED!**\n\n"
                f"**Server:** {self.server_link}\n"
                f"**Reason:** {self.reason}"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Could not DM the user (DMs disabled).", ephemeral=True)

        partner_channel = get_partner_channel(interaction.guild)
        if partner_channel:
            await partner_channel.send(
                f"🎯 **New Partnership!!**\n"
                f"**Partner:** {self.username}\n"
                f"**Server:** {self.server_link}"
            )
        else:
            await interaction.followup.send(
                "⚠️ Partner channel not set. Use `/setchannel partner #channel` first.",
                ephemeral=True
            )

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="deny_partnership")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = 0xff0000
        embed.add_field(name="Status", value="❌ **DENIED**", inline=False)
        embed.add_field(name="Denied by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Denied at", value=discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC'), inline=True)

        await interaction.response.edit_message(embed=embed, view=self)

        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(
                f"❌ **Partnership Application Denied**\n\n"
                f"**Server:** {self.server_link}\n"
                f"**Reason:** {self.reason}"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Could not DM the user (DMs disabled).", ephemeral=True)

# ====================== PARTNERSHIP MODAL ======================
class Partnership(discord.ui.Modal, title="Partnership Application"):
    username = discord.ui.TextInput(label="Your UserID or Username", max_length=50)
    server_name = discord.ui.TextInput(label="Server Link (never expire)", max_length=150)
    reason = discord.ui.TextInput(
        label="Why do you want to partner?",
        style=discord.TextStyle.paragraph,
        max_length=500,
        min_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "✅ Partnership application submitted!",
            ephemeral=True
        )

        try:
            dm_channel = await interaction.user.create_dm()
            await dm_channel.send(
                f"🤝 **Partnership Application Received**\n\n"
                f"**Username:** {self.username}\n"
                f"**Server:** {self.server_name}\n"
                f"**Reason:** {self.reason}"
            )
        except discord.Forbidden:
            await interaction.followup.send("⚠️ I couldn't DM you!", ephemeral=True)

        staff_channel = get_staff_channel(interaction.guild)
        if staff_channel:
            embed = discord.Embed(
                title="🤝 New Partnership Application",
                color=0x5865F2,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Applicant", value=f"{interaction.user.mention}\n{self.username}", inline=True)
            embed.add_field(name="User ID", value=interaction.user.id, inline=True)
            embed.add_field(name="Server Link", value=self.server_name, inline=False)
            embed.add_field(name="Reason", value=self.reason, inline=False)
            embed.set_footer(text="Use buttons below to accept or deny")

            view = StaffDecisionView(
                user_id=interaction.user.id,
                username=str(self.username),
                server_link=self.server_name,
                reason=self.reason
            )
            await staff_channel.send(embed=embed, view=view)
        else:
            await interaction.followup.send(
                "⚠️ Staff channel not set. Use `/setchannel staff #channel` first.",
                ephemeral=True
            )

# ====================== SLASH COMMANDS ======================
@bot.tree.command(name="request", description="Send a request to staff")
async def request_command(interaction: discord.Interaction):
    await interaction.response.send_modal(Requests())

@bot.tree.command(name="partnerships", description="Apply for a partnership")
async def partnerships_command(interaction: discord.Interaction):
    await interaction.response.send_modal(Partnership())

# ====================== SYNC COMMAND ======================
@bot.command()
async def sync(ctx):
    synced = await bot.tree.sync(guild=ctx.guild)
    await ctx.send(f"✅ Synced {len(synced)} command(s) to this guild!")

# ====================== ON READY ======================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ Commands synced to guild {GUILD_ID}")

# ====================== RUN ======================
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
