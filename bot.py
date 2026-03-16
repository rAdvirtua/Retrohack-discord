import discord
from discord.ext import commands, tasks
import psycopg2
import os
from keep_alive import keep_alive

# --- CONFIG ---
TOKEN = os.environ.get("DISCORD_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

class HackathonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          
        intents.message_content = True  
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.automation_loop.start()
        await self.tree.sync()
        print("✅ Automation Engine & Slash Commands active.")

    async def on_ready(self):
        print(f'🚀 Bot Live: {self.user} | Connected to {len(self.guilds)} servers.')

    @tasks.loop(seconds=20)
    async def automation_loop(self):
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            if not self.guilds: return
            guild = self.guilds[0]

            # ENGINE 1: INFRASTRUCTURE BUILDER
            cur.execute("SELECT DISTINCT team_name FROM teams WHERE setup_complete = FALSE")
            pending_infra = cur.fetchall()
            
            for (t_name,) in pending_infra:
                await self.ensure_infrastructure(guild, t_name)
                cur.execute("UPDATE teams SET setup_complete = TRUE WHERE team_name = %s", (t_name,))
                conn.commit()

            # ENGINE 2: MEMBER MATCHER
            cur.execute("SELECT discord_username, team_name FROM teams WHERE role_assigned = FALSE")
            pending_members = cur.fetchall()

            for username, t_name in pending_members:
                member = discord.utils.find(lambda m: m.name.lower() == username.lower(), guild.members)
                if member:
                    role = discord.utils.get(guild.roles, name=t_name)
                    if role:
                        await member.add_roles(role)
                        cur.execute("UPDATE teams SET role_assigned = TRUE WHERE discord_username = %s AND team_name = %s", (username, t_name))
                        conn.commit()
                        print(f"🎫 Assigned {username} to {t_name}")

        except Exception as e:
            print(f"❌ Loop Error: {e}")
        finally:
            if conn: conn.close()

    async def ensure_infrastructure(self, guild, team_name):
        mentor_role = discord.utils.get(guild.roles, name="Mentor")
        team_role = discord.utils.get(guild.roles, name=team_name) or await guild.create_role(
            name=team_name, color=discord.Color.random(), mentionable=True
        )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            team_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, connect=True, speak=True),
            guild.me: discord.PermissionOverwrite(administrator=True)
        }
        if mentor_role:
            overwrites[mentor_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True)

        category = discord.utils.get(guild.categories, name=team_name)
        if not category:
            category = await guild.create_category(team_name, overwrites=overwrites)
            chat = await category.create_text_channel("💬-team-chat")
            await category.create_text_channel("🆘-mentor-support")
            await category.create_voice_channel("🔊-voice-lounge")
            await self.send_welcome(chat, team_name, mentor_role)
        return team_role

    async def send_welcome(self, channel, team_name, mentor):
        m_mention = mentor.mention if mentor else "@Mentor"
        embed = discord.Embed(title=f"Welcome to RetroHack: {team_name}!", color=discord.Color.blue())
        embed.add_field(name="✅ Capabilities", value="You can create/rename channels here. For core issues, open a ticket.", inline=False)
        embed.add_field(name="🆘 Support", value=f"Tag {m_mention} in the support channel for guidance.", inline=False)
        await channel.send(embed=embed)

    async def on_member_join(self, member):
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (member.name.lower(),))
        res = cur.fetchone()
        if res:
            role = discord.utils.get(member.guild.roles, name=res[0])
            if role:
                await member.add_roles(role)
                cur.execute("UPDATE teams SET role_assigned = TRUE WHERE discord_username = %s", (member.name.lower(),))
                conn.commit()
        conn.close()

bot = HackathonBot()
keep_alive()
bot.run(TOKEN)
