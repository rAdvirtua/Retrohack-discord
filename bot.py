import discord
from discord.ext import commands
import sqlite3
import os
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()
# You will paste your actual bot token here
TOKEN = os.environ.get("DISCORD_TOKEN")

class TeamVerificationModal(discord.ui.Modal, title='Hackathon Verification'):
    team_code = discord.ui.TextInput(
        label='Enter your Team Code',
        placeholder='e.g., EVF49I',
        required=True,
        max_length=10
    )
    participant_name = discord.ui.TextInput(
        label='Enter your Full Name',
        placeholder='e.g., John Doe',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 1. DEFER FIRST: This gives the bot up to 15 minutes to finish the setup
        await interaction.response.defer(ephemeral=True)

        code_input = self.team_code.value.strip()
        
        # 2. Check the SQLite database
        conn = sqlite3.connect("hackathon.db")
        cursor = conn.cursor()
        cursor.execute("SELECT team_name FROM teams WHERE team_code = ?", (code_input,))
        result = cursor.fetchone()
        conn.close()

        # 3. Reject if the code isn't in the database
        if not result:
            # We must use followup.send() because we already deferred
            await interaction.followup.send("Invalid Team Code. Please register on the website first.", ephemeral=True)
            return

        team_name = result[0]
        guild = interaction.guild

        # 4. Check if team role already exists
        existing_role = discord.utils.get(guild.roles, name=team_name)
        
        if not existing_role:
            # 5. Create a new Role for the team
            team_role = await guild.create_role(name=team_name)
            
            # 6. Setup Category Permissions (Private to the team + bot)
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                team_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # 7. Create Category and Channels
            category = await guild.create_category(team_name, overwrites=overwrites)
            await guild.create_text_channel('team-chat', category=category)
            await guild.create_text_channel('mentor-support', category=category)
        else:
            team_role = existing_role

        # 8. Assign the role to the user
        await interaction.user.add_roles(team_role)
        
        # Optional: Change their nickname so you know who they are
        try:
            await interaction.user.edit(nick=f"{self.participant_name.value} | {team_name}")
        except discord.Forbidden:
            pass # Ignores the error if the bot tries to rename the server owner (Discord prevents this)

        # 9. Send private success message (using followup.send!)
        await interaction.followup.send(f"Success! Welcome to {team_name}. Your channels have been created.", ephemeral=True)


class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Timeout=None makes the button permanent

    @discord.ui.button(label="Verify Team Code", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This opens the modal when the button is clicked
        await interaction.response.send_modal(TeamVerificationModal())


class HackathonBot(commands.Bot):
    def __init__(self):
        # Intents are required for the bot to manage roles and see members
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Registers the persistent button so it works even after the bot restarts
        self.add_view(VerificationView())

    async def on_ready(self):
        print(f'Logged in as {self.user}!')

bot = HackathonBot()

# A command you run once to spawn the button in the waiting room
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_verification(ctx):
    await ctx.send("Welcome to the Hackathon! Click below to enter your Team Code.", view=VerificationView())
keep_alive()
bot.run(TOKEN)
