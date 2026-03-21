import discord
from discord.ext import commands, tasks
import psycopg2
import os
from keep_alive import keep_alive

# --- CONFIG ---
TOKEN = os.environ.get("DISCORD_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
# The proxy you found
PROXY_URL = "http://38.145.203.43:8443" 

class HackathonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          
        intents.message_content = True  
        
        super().__init__(
            command_prefix="!", 
            intents=intents,
            proxy=PROXY_URL # <--- THIS BYPASSES THE RENDER IP BLOCK
        )

    async def setup_hook(self):
        self.automation_loop.start()
        # NOTE: If you still get 429 errors, comment out the line below 
        # once your slash commands are synced once.
        await self.tree.sync()
        print(f"✅ Proxy Active: {PROXY_URL}")
        print("✅ Sidebar Hoisting & Autonomous Hunter Active.")

    @tasks.loop(seconds=20)
    async def automation_loop(self):
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            if not self.guilds: return
            guild = self.guilds[0]

            # --- ENGINE 1: INFRASTRUCTURE BUILDER ---
            cur.execute("SELECT DISTINCT team_name FROM teams WHERE setup_complete = FALSE")
            for (t_name,) in cur.fetchall():
                await self.ensure_infrastructure(guild, t_name)
                cur.execute("UPDATE teams SET setup_complete = TRUE WHERE team_name = %s", (t_name,))
                conn.commit()

            # --- ENGINE 2: THE HUNTER ---
            cur.execute("SELECT discord_username, team_name FROM teams WHERE role_assigned = FALSE")
            pending = cur.fetchall()
            
            for username, t_name in pending:
                member = discord.utils.find(lambda m: m.name.lower() == username.lower(), guild.members)
                if member:
                    role = discord.utils.get(guild.roles, name=t_name)
                    if role:
                        await member.add_roles(role)
                        cur.execute("UPDATE teams SET role_assigned = TRUE WHERE discord_username = %s AND team_name = %s", (username, t_name))
                        conn.commit()
                        print(f"🎯 AUTO_ASSIGN: {username} -> {t_name}")

        except Exception as e:
            print(f"❌ Loop Error: {e}")
        finally:
            if conn: conn.close()

    async def ensure_infrastructure(self, guild, team_name):
        mentor_role = discord.utils.get(guild.roles, name="Mentor")
        
        team_role = discord.utils.get(guild.roles, name=team_name) or await guild.create_role(
            name=team_name, color=discord.Color.random(), mentionable=True, hoist=True
        )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            team_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, connect=True),
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
            
            embed = discord.Embed(title=f"🚀 TEAM_{team_name}_INITIALIZED", color=discord.Color.blue())
            embed.description = "Workspace live. Handshake complete."
            await chat.send(embed=embed)
        return team_role

    async def on_member_join(self, member):
        conn = None
        try:
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
                    print(f"⚡ JOIN_MATCH: {member.name} auto-roled.")
        except Exception as e:
            print(f"Join Error: {e}")
        finally:
            if conn: conn.close()

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def deploy_terminal(self, ctx):
        embed = discord.Embed(
            title="📟 RETROHACK_2026 | STARTUP_TERMINAL",
            description=(
                "**WELCOME_USER. SYSTEM_READY.**\n\n"
                "**[PROT_01: RULES]**\n"
                "• No toxicity.\n"
                "• Do not delete core channels.\n\n"
                "**[PROT_02: UPLINK]**\n"
                "Register here: [**WEBSITE_LINK**](https://your-website.onrender.com)\n\n"
                "**[PROT_03: AUTO_SYNC]**\n"
                "Automation will reveal your team channels once registered."
            ),
            color=0xec4899
        )
        await ctx.send(embed=embed)
        await ctx.message.delete()

bot = HackathonBot()
keep_alive()
bot.run(TOKEN)
