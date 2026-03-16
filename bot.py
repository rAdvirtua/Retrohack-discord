import discord
from discord.ext import commands, tasks
from discord import app_commands
import psycopg2
import os
from keep_alive import keep_alive

# --- CONFIG ---
TOKEN = os.environ.get("DISCORD_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
LOG_CHANNEL_ID = 1234567890  # <--- REPLACE WITH YOUR AUDIT LOG CHANNEL ID

class HackathonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # CRITICAL: Must be ON in Developer Portal
        intents.message_content = True  
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.check_new_teams.start()
        await self.tree.sync()
        print("✅ Bot logic synced. Poller active.")

    async def on_ready(self):
        print(f'🚀 Logged in as {self.user}!')

    async def log_event(self, message):
        channel = self.get_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(f"🛡️ **Audit Log:** {message}")

    # --- THE MULTI-MEMBER POLLER ---
    @tasks.loop(seconds=30)
    async def check_new_teams(self):
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            
            # 1. Get all team names that haven't been set up yet
            cur.execute("""
                SELECT DISTINCT team_name 
                FROM teams 
                WHERE setup_complete = FALSE 
                FOR UPDATE SKIP LOCKED
            """)
            new_teams = cur.fetchall()

            if not new_teams:
                return

            for (team_name,) in new_teams:
                if not self.guilds: continue
                guild = self.guilds[0]
                
                # 2. Create Role & Category (Internal checks prevent duplicates)
                team_role = await self.create_team_infrastructure(guild, team_name)
                
                # 3. Mark the team as setup in the DB immediately
                cur.execute("UPDATE teams SET setup_complete = TRUE WHERE team_name = %s", (team_name,))
                conn.commit()

                # 4. Find ALL registered members for this team name
                cur.execute("SELECT discord_username FROM teams WHERE team_name = %s", (team_name,))
                registered_usernames = [r[0] for r in cur.fetchall()]

                # 5. Scan the server for these users and assign roles
                for username in registered_usernames:
                    member = discord.utils.find(lambda m: m.name.lower() == username.lower(), guild.members)
                    if member:
                        if team_role not in member.roles:
                            await member.add_roles(team_role)
                            await self.log_event(f"Assigned **{member.name}** to existing team: **{team_name}**")
                
                await self.log_event(f"Infrastructure setup finished for **{team_name}**.")

        except Exception as e:
            if conn: conn.rollback()
            print(f"Poller Error: {e}")
        finally:
            if conn: conn.close()

    async def create_team_infrastructure(self, guild, team_name):
        """Builds the roles and channels. Checks if they exist first to prevent duplicates."""
        organizer = discord.utils.get(guild.roles, name="Organizer")
        mentor = discord.utils.get(guild.roles, name="Mentor")
        
        # Role Check
        team_role = discord.utils.get(guild.roles, name=team_name)
        if not team_role:
            team_role = await guild.create_role(name=team_name, color=discord.Color.random(), mentionable=True)

        # Category Check
        category = discord.utils.get(guild.categories, name=team_name)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                team_role: discord.PermissionOverwrite(read_messages=True, manage_channels=True, connect=True, speak=True),
                organizer: discord.PermissionOverwrite(read_messages=True, manage_messages=True, send_messages=True),
                mentor: discord.PermissionOverwrite(read_messages=True, manage_channels=True, send_messages=True)
            }
            category = await guild.create_category(team_name, overwrites=overwrites)
            await category.create_text_channel("team-chat")
            await category.create_voice_channel("voice-lounge")
        
        return team_role

    # --- AUTO-ASSIGN ON JOIN ---
    async def on_member_join(self, member):
        """If a teammate joins late, find their team and give them the role."""
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (member.name.lower(),))
            result = cur.fetchone()
            conn.close()

            if result:
                team_role = discord.utils.get(member.guild.roles, name=result[0])
                if team_role:
                    await member.add_roles(team_role)
                    await self.log_event(f"Late arrival **{member.name}** auto-assigned to **{result[0]}**.")
        except Exception as e:
            print(f"Join Error: {e}")

# --- MODERATION SLASH COMMANDS ---
bot = HackathonBot()

@bot.tree.command(name="kick", description="Kicks a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "None"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"Kicked {member.display_name}", ephemeral=True)

@bot.tree.command(name="ban", description="Bans a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "None"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"Banned {member.display_name}", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
