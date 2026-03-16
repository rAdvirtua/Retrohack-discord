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
        print("✅ Automation Engine started. Watching Neon...")

    async def on_ready(self):
        print(f'🚀 Bot Live: {self.user} | Connected to {len(self.guilds)} server(s)')

    @tasks.loop(seconds=20)
    async def automation_loop(self):
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            if not self.guilds: return
            guild = self.guilds[0]

            # 1. BUILD INFRASTRUCTURE
            cur.execute("SELECT DISTINCT team_name FROM teams WHERE setup_complete = FALSE")
            pending_infra = cur.fetchall()
            
            for (t_name,) in pending_infra:
                await self.ensure_infrastructure(guild, t_name)
                cur.execute("UPDATE teams SET setup_complete = TRUE WHERE team_name = %s", (t_name,))
                conn.commit()

            # 2. MATCH MEMBERS
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
            print(f"❌ Automation Error: {e}")
            if conn: conn.rollback()
        finally:
            if conn: conn.close()

    async def ensure_infrastructure(self, guild, team_name):
        mentor_role = discord.utils.get(guild.roles, name="Mentor")
        
        # Create Role
        team_role = discord.utils.get(guild.roles, name=team_name) or await guild.create_role(
            name=team_name, color=discord.Color.random(), mentionable=True
        )

        # Build Permission Overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            team_role: discord.PermissionOverwrite(
                read_messages=True, 
                send_messages=True, 
                manage_channels=True, # Teams can manage their workspace
                connect=True, 
                speak=True
            ),
            guild.me: discord.PermissionOverwrite(administrator=True)
        }
        
        # Mentors get full control (Override)
        if mentor_role:
            overwrites[mentor_role] = discord.PermissionOverwrite(
                read_messages=True, 
                send_messages=True, 
                manage_channels=True, 
                manage_permissions=True,
                connect=True,
                speak=True
            )

        # Create Category
        category = discord.utils.get(guild.categories, name=team_name)
        if not category:
            category = await guild.create_category(team_name, overwrites=overwrites)
            
            # Simple Channel Creation (No locks)
            chat = await category.create_text_channel("💬-team-chat")
            await category.create_text_channel("🆘-mentor-support")
            await category.create_voice_channel("🔊-voice-lounge")

            # Send Welcome Message
            await self.send_welcome_message(chat, team_name, mentor_role)

        return team_role

    async def send_welcome_message(self, channel, team_name, mentor_role):
        mentor_mention = mentor_role.mention if mentor_role else "@Mentor"
        
        embed = discord.Embed(
            title=f"👾 Welcome to RetroHack: {team_name}!",
            description="Your private workspace has been initialized.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="✅ What you CAN do:",
            value=(
                "• **Rename/Create Channels:** You can add more channels to this category.\n"
                "• **Voice Lounge:** Use the lounge for meetings and screensharing.\n"
                "• **Ask for help:** Tag " + mentor_mention + " in the support channel if you hit a wall."
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Rules:",
            value=(
                "• Don't delete the default channels provided.\n"
                "• Mentors are here to help and oversee the hackathon.\n"
                "• Keep the environment professional and fun!"
            ),
            inline=False
        )
        
        embed.set_footer(text="RetroHack 2026 • Code hard!")
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
