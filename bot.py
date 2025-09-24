# ===================================== IMPORTS =====================================
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
from discord import app_commands
import random
import asyncio
import aiohttp
from datetime import datetime
import json
import os
import pytz
import os



# ===================================== BOT SETUP =====================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.has_started = False

# ===================================== VARIABLES =====================================
GUILD_ID = int(os.environ.get("GUILD_ID"))  # Replace with your guild ID
staff_channel_id = 1054765292674355308  # Your staff channel ID
accepted_partnership_channel_id = 1420502197434712095 # Channel for the accepted partnerships


# ====================== Requests ======================
class Requests(discord.ui.Modal, title="Request Form"):
    short_input = discord.ui.TextInput(label="Your Request")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 1. Respond to the interaction ONLY ONCE
            await interaction.response.send_message(
                f"✅ Request submitted: {self.short_input.value}", 
                ephemeral=True
            )
            
            # 2. Send DM to user
            try:
                dm_channel = await interaction.user.create_dm()
                await dm_channel.send(
                    f"📨 **Request Submitted**\n"
                    f"**Your request:** {self.short_input.value}\n"
                    f"*This has been sent to the staff team!*"
                )
                print(f"✅ DM sent to {interaction.user.name}")
            except discord.Forbidden:
                # Use followup since we already responded
                await interaction.followup.send(
                    "⚠️ I couldn't send you a DM! Please enable DMs from server members.",
                    ephemeral=True
                )
            
            # 3. Staff notification
            staff_channel = interaction.client.get_channel(staff_channel_id) 
            
            if staff_channel:
                await staff_channel.send(
                    f"🎯 **New Request Submitted**\n"
                    f"**User:** {interaction.user.mention} ({interaction.user.id})\n"
                    f"**Request:** {self.short_input.value}\n"
                    f"**Channel:** {interaction.channel.mention if interaction.channel else 'DM'}\n"
                    f"**Time:** {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                print("✅ Staff notification sent")
            else:
                print("❌ Staff channel not found")
            
        except Exception as e:
            print("⚠️ Error in modal submission:", e)
            # If we haven't responded yet, send error message
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing your request.", 
                    ephemeral=True
                )



# ====================== STAFF BUTTONS VIEW ======================
class StaffDecisionView(discord.ui.View):
    def __init__(self, user_id, username, server_link, reason):
        super().__init__(timeout=None)  # No timeout so buttons work forever
        self.user_id = user_id
        self.username = username
        self.server_link = server_link
        self.reason = reason

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success, custom_id="accept_partnership")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Disable both buttons after click
        for child in self.children:
            child.disabled = True
        
        # Update the message to show accepted
        embed = interaction.message.embeds[0]
        embed.color = 0x00ff00  # Green
        embed.add_field(name="Status", value="✅ **ACCEPTED**", inline=False)
        embed.add_field(name="Accepted by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Accepted at", value=discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC'), inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send DM to user
        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(
                f"🎉 **Partnership Application ACCEPTED!**\n\n"
                f"**Your application has been reviewed and accepted!**\n"
                f"**Server:** {self.server_link}\n"
                f"**Reason:** {self.reason}\n"
                f"A staff member will contact you soon to discuss details!"
            )
            await interaction.followup.send("✅ User notified via DM!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Could not send DM to user (DMs disabled)", ephemeral=True)
        
        # Sends a message in the accepted partnership channel

        partnership_channel = interaction.client.get_channel(accepted_partnership_channel_id)
        if partnership_channel:
            await partnership_channel.send(
                f"🎯 **New Partnership!!**\n"
                f"**Partner:** {self.username}\n"
                f"**Server:** {self.server_link}"
            )
            print("✅ Staff notification sent")
        else:
            print("❌ Staff channel not found")

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="deny_partnership")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Disable both buttons after click
        for child in self.children:
            child.disabled = True
        
        # Update the message to show denied
        embed = interaction.message.embeds[0]
        embed.color = 0xff0000  # Red
        embed.add_field(name="Status", value="❌ **DENIED**", inline=False)
        embed.add_field(name="Denied by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Denied at", value=discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC'), inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send DM to user
        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(
                f"❌ **Partnership Application Denied**\n\n"
                f"**Your application has been reviewed and unfortunately denied.**\n"
                f"**Server:** {self.server_link}\n"
                f"**Reason:** {self.reason}\n\n"
                f"Thank you for your interest. You may reapply in the future."
            )
            await interaction.followup.send("✅ User notified via DM!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Could not send DM to user (DMs disabled)", ephemeral=True)

# ====================== PARTNERSHIP MODAL ======================
class Partnership(discord.ui.Modal, title="Partnerships Application"):
    username = discord.ui.TextInput(
        label="Your UserID or Username",
        placeholder="Enter your discord Id or username...",
        required=True,
        max_length=50
    )

    server_name = discord.ui.TextInput(
        label="Server Link (never expire link)",
        placeholder="https://discord.gg/...",
        required=True,
        max_length=150
    )

    reason = discord.ui.TextInput(
        label="Why do you want to partner with us?",
        style=discord.TextStyle.paragraph,
        placeholder="...",
        required=True,
        max_length=500,
        min_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 1. Respond to user
            await interaction.response.send_message(
                "✅ Your partnership application has been submitted!",
                ephemeral=True
            )
            
            # 2. Send DM confirmation
            try:
                dm_channel = await interaction.user.create_dm()
                await dm_channel.send(
                    f"🤝 **Partnership Application Received**\n\n"
                    f"**Username:** {self.username}\n"
                    f"**Server:** {self.server_name}\n"
                    f"**Reason:** {self.reason}\n\n"
                    f"*We'll review your application soon!*"
                )
                print(f"✅ DM sent to {interaction.user.name}")
            except discord.Forbidden:
                await interaction.followup.send(
                    "⚠️ I couldn't send you a DM! Please enable DMs from server members.",
                    ephemeral=True
                )
            
            # 3. Staff notification with buttons
            staff_channel = interaction.client.get_channel(staff_channel_id) 
            
            if staff_channel:
                # Create embed
                embed = discord.Embed(
                    title="🤝 New Partnership Application",
                    color=0x5865F2,  # Discord blurple
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Applicant", value=f"{interaction.user.mention}\n`{self.username}`", inline=True)
                embed.add_field(name="User ID", value=interaction.user.id, inline=True)
                embed.add_field(name="Server Link", value=self.server_name, inline=False)
                embed.add_field(name="Reason", value=self.reason, inline=False)
                embed.set_footer(text="Use buttons below to accept or deny")
                
                # Create view with buttons
                view = StaffDecisionView(
                    user_id=interaction.user.id,
                    username=str(self.username),
                    server_link=self.server_name,
                    reason=self.reason
                )
                
                await staff_channel.send(embed=embed, view=view)
                print("✅ Staff notification sent with buttons")
            else:
                print("❌ Staff channel not found")
            
        except Exception as e:
            print("⚠️ Error in modal submission:", e)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing your request.", 
                    ephemeral=True
                )

# ====================== PURGE LOGIC ======================
async def execute_purge_logic(source, amount: int, is_slash: bool):
    if amount > 100:
        await respond(source, "Max 100 messages!", is_slash=is_slash, delete_after=5)
        return
    
    deleted = await source.channel.purge(limit=amount)
    await respond(source, f"✅ Deleted {len(deleted)} messages", is_slash=is_slash, delete_after=5)




# ====================== SLASH COMMANDS ======================
@bot.tree.command(
    guild=discord.Object(id=GUILD_ID),
    name="request",
    description="Type out a request to the owner or staff team"
)
async def request_command(interaction: discord.Interaction):
    await interaction.response.send_modal(Requests())

@bot.tree.command(
    guild=discord.Object(id=GUILD_ID),
    name="partnerships",
    description="Want to partner with us? Fill in this form."
)
async def partnerships_command(interaction: discord.Interaction):
    await interaction.response.send_modal(Partnership())

@bot.tree.command(name="purge", description="Purge messages")
@app_commands.describe(amount="Number to delete (max 100)")
async def purge_slash(interaction: discord.Interaction, amount: int = 100):
    await interaction.response.defer()
    await execute_purge_logic(interaction, amount, is_slash=True)

# ====================== REGULAR COMMANDS ======================
@bot.command()
async def purge(ctx, amount: int = 100):
    await execute_purge_logic(ctx, amount, is_slash=False)
    
@bot.command()
async def sync(ctx):
    guild = discord.Object(id=GUILD_ID)
    synced = await bot.tree.sync(guild=guild)
    await ctx.send(f"✅ Synced {len(synced)} command(s) to the guild!")


# ====================== ON READY ======================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Commands synced to guild {GUILD_ID}")


# ====================== RUN ======================
bot.run(os.getenv("DISCORD_TOKEN"))

