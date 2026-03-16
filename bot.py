import discord
from discord.ext import commands
import psycopg2  # Changed from sqlite3
import os
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.environ.get("DISCORD_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL") # Get your Neon URL

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
        await interaction.response.defer(ephemeral=True)

        code_input = self.team_code.value.strip()
        
        # --- FIXED: Use PostgreSQL (Neon) instead of SQLite ---
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            # PostgreSQL uses %s instead of ?
            cursor.execute("SELECT team_name FROM teams WHERE team_code = %s", (code_input,))
            result = cursor.fetchone()
        except Exception as e:
            print(f"Database Error: {e}")
            await interaction.followup.send("Error connecting to database.", ephemeral=True)
            return
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals(): conn.close()

        if not result:
            await interaction.followup.send("Invalid Team Code. Please register on the website first.", ephemeral=True)
            return

        team_name = result[0]
        guild = interaction.guild

        # 4. Role & Channel Logic
        existing_role = discord.utils.get(guild.roles, name=team_name)
        
        if not existing_role:
            team_role = await guild.create_role(name=team_name)
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                team_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            category = await guild.create_category(team_name, overwrites=overwrites)
            await guild.create_text_channel('team-chat', category=category)
            await guild.create_text_channel('mentor-support', category=category)
        else:
            team_role = existing_role

        await interaction.user.add_roles(team_role)
        
        try:
            await interaction.user.edit(nick=f"{self.participant_name.value} | {team_name}")
        except discord.Forbidden:
            pass

        await interaction.followup.send(f"Success! Welcome to {team_name}.", ephemeral=True)

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Team Code", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TeamVerificationModal())

class HackathonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(VerificationView())

    async def on_ready(self):
        print(f'Logged in as {self.user}!')

bot = HackathonBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_verification(ctx):
    await ctx.send("Welcome! Click below to enter your Team Code.", view=VerificationView())

if __name__ == "__main__":
    keep_alive() # Start web server
    bot.run(TOKEN) # Start bot
