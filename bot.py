import discord
from discord.ext import commands, tasks
from discord import app_commands
import psycopg2
import os
from keep_alive import keep_alive

# --- CONFIG ---
TOKEN = os.environ.get("DISCORD_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
LOG_CHANNEL_ID = 1234567890  # <--- REPLACE THIS WITH YOUR CHANNEL ID

class HackathonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.check_new_teams.start()  # Start the background task
        await self.tree.sync()        # Sync Slash Commands
        print("Slash commands synced and background task started.")

    async def on_ready(self):
        print(f'Logged in as {self.user}!')

    # --- AUDIT LOG ---
    async def log_event(self, message):
        channel = self.get_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(f"🛡️ **Audit Log:** {message}")

    # --- BACKGROUND POLLER (Checks Neon every 30s) ---
    @tasks.loop(seconds=30)
    async def check_new_teams(self):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT team_name, team_code FROM teams WHERE setup_complete = FALSE")
            new_teams = cur.fetchall()

            for team_name, team_code in new_teams:
                if self.guilds:
                    guild = self.guilds[0]
                    await self.create_team_infrastructure(guild, team_name)
                    
                    cur.execute("UPDATE teams SET setup_complete = TRUE WHERE team_name = %s", (team_name,))
                    conn.commit()
                    await self.log_event(f"Infrastructure created for Team: **{team_name}**")

            conn.close()
        except Exception as e:
            print(f"Poller Error: {e}")

    async def create_team_infrastructure(self, guild, team_name):
        organizer = discord.utils.get(guild.roles, name="Organizer")
        mentor = discord.utils.get(guild.roles, name="Mentor")
        team_role = await guild.create_role(name=team_name, color=discord.Color.random())

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            team_role: discord.PermissionOverwrite(read_messages=True, manage_channels=True, connect=True, speak=True),
            organizer: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
            mentor: discord.PermissionOverwrite(read_messages=True, manage_channels=True, send_messages=True)
        }

        category = await guild.create_category(team_name, overwrites=overwrites)
        await category.create_text_channel("team-chat")
        await category.create_voice_channel("voice-lounge")

    # --- AUTO-ASSIGN ON JOIN ---
    async def on_member_join(self, member):
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (member.name.lower(),))
        result = cur.fetchone()
        conn.close()

        if result:
            team_role = discord.utils.get(member.guild.roles, name=result[0])
            if team_role:
                await member.add_roles(team_role)
                await self.log_event(f"User **{member.name}** matched and assigned to **{result[0]}**")

bot = HackathonBot()

# --- MODERATION SLASH COMMANDS ---

@bot.tree.command(name="kick", description="Kicks a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "None"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"Kicked {member.display_name}", ephemeral=True)
    await bot.log_event(f"{member.name} kicked by {interaction.user.name}. Reason: {reason}")

@bot.tree.command(name="ban", description="Bans a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "None"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"Banned {member.display_name}", ephemeral=True)
    await bot.log_event(f"{member.name} banned by {interaction.user.name}. Reason: {reason}")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
