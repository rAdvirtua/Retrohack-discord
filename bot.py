import discord
from discord.ext import commands, tasks
from discord import app_commands
import psycopg2
import os
from keep_alive import keep_alive

TOKEN = os.environ.get("DISCORD_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
LOG_CHANNEL_ID = 1234567890 

class HackathonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.check_new_teams.start()
        await self.tree.sync()

    @tasks.loop(seconds=30)
    async def check_new_teams(self):
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            # Find distinct team names that haven't been setup
            cur.execute("SELECT DISTINCT team_name FROM teams WHERE setup_complete = FALSE FOR UPDATE SKIP LOCKED")
            new_teams = cur.fetchall()

            for (team_name,) in new_teams:
                guild = self.guilds[0]
                team_role = await self.create_infrastructure(guild, team_name)
                
                # Mark all members of this team as setup
                cur.execute("UPDATE teams SET setup_complete = TRUE WHERE team_name = %s", (team_name,))
                conn.commit()

                # Find all members of this team currently in server and give role
                cur.execute("SELECT discord_username FROM teams WHERE team_name = %s", (team_name,))
                members_to_find = [r[0] for r in cur.fetchall()]
                
                for username in members_to_find:
                    member = discord.utils.find(lambda m: m.name.lower() == username.lower(), guild.members)
                    if member:
                        await member.add_roles(team_role)
            conn.close()
        except Exception as e:
            if conn: conn.rollback()
            print(f"Error: {e}")

    async def create_infrastructure(self, guild, team_name):
        role = discord.utils.get(guild.roles, name=team_name) or await guild.create_role(name=team_name, color=discord.Color.random())
        category = discord.utils.get(guild.categories, name=team_name)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                role: discord.PermissionOverwrite(read_messages=True, manage_channels=True, connect=True),
                discord.utils.get(guild.roles, name="Mentor"): discord.PermissionOverwrite(read_messages=True, manage_channels=True)
            }
            cat = await guild.create_category(team_name, overwrites=overwrites)
            await cat.create_text_channel("team-chat")
            await cat.create_voice_channel("voice-lounge")
        return role

    async def on_member_join(self, member):
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (member.name.lower(),))
        res = cur.fetchone()
        if res:
            role = discord.utils.get(member.guild.roles, name=res[0])
            if role: await member.add_roles(role)
        conn.close()

bot = HackathonBot()
keep_alive()
bot.run(TOKEN)
