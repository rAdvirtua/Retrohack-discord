import discord
from discord.ext import commands, tasks
import psycopg2
import os
from keep_alive import keep_alive

# --- CONFIG ---
# Hugging Face pulls these from your 'Secrets' tab automatically
TOKEN = os.environ.get("DISCORD_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

class HackathonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          
        intents.message_content = True  
        
        # Proxy removed for Hugging Face migration
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.automation_loop.start()
        
        # SYNC COMMANDS: Run this once to register slash commands, 
        # then you can comment it out to prevent unnecessary API pings.
        await self.tree.sync()
        
        print("✅ Hugging Face Uplink Established.")
        print("✅ Autonomous Hunter Engine: ONLINE.")

    @tasks.loop(seconds=20)
    async def automation_loop(self):
        """The core background engine that hunts for new registrations."""
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            if not self.guilds: return
            guild = self.guilds[0]

            # --- ENGINE 1: INFRASTRUCTURE BUILDER ---
            # Creates Roles and Categories for teams not yet set up
            cur.execute("SELECT DISTINCT team_name FROM teams WHERE setup_complete = FALSE")
            for (t_name,) in cur.fetchall():
                await self.ensure_infrastructure(guild, t_name)
                cur.execute("UPDATE teams SET setup_complete = TRUE WHERE team_name = %s", (t_name,))
                conn.commit()

            # --- ENGINE 2: THE HUNTER ---
            # Automatically assigns roles to users already in the server
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
                        print(f"🎯 AUTO_ASSIGN: {username} matched to {t_name}")

        except Exception as e:
            print(f"❌ Automation Engine Error: {e}")
        finally:
            if conn: conn.close()

    async def ensure_infrastructure(self, guild, team_name):
        """Creates the private workspace for each team."""
        mentor_role = discord.utils.get(guild.roles, name="Mentor")
        
        # Create role with 'hoist=True' so they appear separately in the sidebar
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
            
            embed = discord.Embed(title=f"🚀 TEAM_{team_name}_INITIALIZED", color=0x22d3ee)
            embed.description = "System Handshake Complete. Your private grid is now live."
            await chat.send(embed=embed)
            
        return team_role

    async def on_member_join(self, member):
        """Instant role assignment for users who register on the web BEFORE joining Discord."""
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
                    print(f"⚡ INSTANT_UPLINK: {member.name} recognized and roled.")
        except Exception as e:
            print(f"❌ Join Event Error: {e}")
        finally:
            if conn: conn.close()

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def deploy_terminal(self, ctx):
        """Admin command to post the high-impact rules to your #startup-terminal channel."""
        embed = discord.Embed(
            title="📟 RETROHACK_2026 | STARTUP_TERMINAL",
            description=(
                "**WELCOME_USER. SYSTEM_READY.**\n\n"
                "**[PROT_01: RULES]**\n"
                "• Toxicity results in a permanent session disconnect.\n"
                "• Do not delete core workspace channels.\n\n"
                "**[PROT_02: UPLINK]**\n"
                "Register your team here: [**RETROHACK_COMMAND_CENTER**](https://huggingface.co/spaces/YOUR_USER/YOUR_SPACE)\n\n"
                "**[PROT_03: AUTO_SYNC]**\n"
                "The Hunter Engine will reveal your team channels within 20 seconds of registration."
            ),
            color=0xec4899 # Neon Pink
        )
        await ctx.send(embed=embed)
        await ctx.message.delete()

# Initialize the Bot
bot = HackathonBot()

# Start the Flask Web Server (keep_alive handles the Port 7860 logic)
keep_alive()

# Launch the Bot
bot.run(TOKEN)
