from discord.ext import commands, tasks
from aiohttp.client import request
import datetime
import discord
import aiohttp
import asyncio
import signal
import uvloop
import json
import time
import os

# Asyncio drop-in replacement, 2-4x faster
uvloop.install()

# Local imports
from modules import globals, db, utils, xp

# Setup globals
globals.loop = asyncio.get_event_loop()
globals.cur_presence = 0

globals.ADMIN_ID                 = int       (os.environ["ADMIN_ID"])                 if os.environ.get("ADMIN_ID")                 else 0
globals.ASSISTANCE_CATEGORY_IDS  = json.loads(os.environ["ASSISTANCE_CATEGORY_IDS"])  if os.environ.get("ASSISTANCE_CATEGORY_IDS")  else []
globals.BLACKLISTED_CHANNELS_IDS = json.loads(os.environ["BLACKLISTED_CHANNELS_IDS"]) if os.environ.get("BLACKLISTED_CHANNELS_IDS") else []
globals.BOT_PREFIX               = str       (os.environ["BOT_PREFIX"])               if os.environ.get("BOT_PREFIX")               else "a/"
globals.CONTRIB_AMOUNT           = int       (os.environ["CONTRIB_AMOUNT"])           if os.environ.get("CONTRIB_AMOUNT")           else 1000
globals.CONTRIB_CHANNELS_IDS     = json.loads(os.environ["CONTRIB_CHANNELS_IDS"])     if os.environ.get("CONTRIB_CHANNELS_IDS")     else []
globals.CONTRIB_COOLDOWN         = int       (os.environ["CONTRIB_COOLDOWN"])         if os.environ.get("CONTRIB_COOLDOWN")         else 3600
globals.DAILY_LEVEL_AMOUNT       = int       (os.environ["DAILY_LEVEL_AMOUNT"])       if os.environ.get("DAILY_LEVEL_AMOUNT")       else 500
globals.DISCORD_TOKEN            = str       (os.environ["DISCORD_TOKEN"])            if os.environ.get("DISCORD_TOKEN")            else ""
globals.HEROKU_TOKEN             = str       (os.environ["HEROKU_TOKEN"])             if os.environ.get("HEROKU_TOKEN")             else ""
globals.IMGUR_CLIENT_ID          = str       (os.environ["IMGUR_CLIENT_ID"])          if os.environ.get("IMGUR_CLIENT_ID")          else ""
globals.JOIN_LOG_CHANNEL_IDS     = json.loads(os.environ["JOIN_LOG_CHANNEL_IDS"])     if os.environ.get("JOIN_LOG_CHANNEL_IDS")     else {}
globals.LEVEL_NOTIF_CHANNEL_IDS  = json.loads(os.environ["LEVEL_NOTIF_CHANNEL_IDS"])  if os.environ.get("LEVEL_NOTIF_CHANNEL_IDS")  else {}
globals.MODDER_CATEGORY_IDS      = json.loads(os.environ["MODDER_CATEGORY_IDS"])      if os.environ.get("MODDER_CATEGORY_IDS")      else []
globals.MODDER_ROLE_IDS          = json.loads(os.environ["MODDER_ROLE_IDS"])          if os.environ.get("MODDER_ROLE_IDS")          else []
globals.NO_PERM_ICON             = str       (os.environ["NO_PERM_ICON"])             if os.environ.get("NO_PERM_ICON")             else "https://cdn.discordapp.com/emojis/778028443417313290.png"
globals.REP_CRED_AMOUNT          = int       (os.environ["REP_CRED_AMOUNT"])          if os.environ.get("REP_CRED_AMOUNT")          else 500
globals.REP_ICON                 = str       (os.environ["REP_ICON"])                 if os.environ.get("REP_ICON")                 else "https://cdn.discordapp.com/emojis/766042961929699358.png"
globals.REQUESTS_CHANNEL_IDS     = json.loads(os.environ["REQUESTS_CHANNEL_IDS"])     if os.environ.get("REQUESTS_CHANNEL_IDS")     else {}
globals.REQUESTS_COOLDOWN        = int       (os.environ["REQUESTS_COOLDOWN"])        if os.environ.get("REQUESTS_COOLDOWN")        else 600
globals.REQUESTS_ICONS           = json.loads(os.environ["REQUESTS_ICONS"])           if os.environ.get("REQUESTS_ICONS")           else {"Waiting": "https://cdn.discordapp.com/emojis/889210410899746897.png", "WIP": "https://cdn.discordapp.com/emojis/889210383523536896.png", "Released": "https://cdn.discordapp.com/emojis/889210365362184272.png", "Already Exists": "https://cdn.discordapp.com/emojis/889210365362184272.png"}
globals.STAFF_ROLE_IDS           = json.loads(os.environ["STAFF_ROLE_IDS"])           if os.environ.get("STAFF_ROLE_IDS")           else []
globals.TROPHY_ROLES             = json.loads(os.environ["TROPHY_ROLES"])             if os.environ.get("TROPHY_ROLES")             else []
globals.WRITE_AS_PASS            = str       (os.environ["WRITE_AS_PASS"])            if os.environ.get("WRITE_AS_PASS")            else ""
globals.WRITE_AS_POST_ID         = str       (os.environ["WRITE_AS_POST_ID"])         if os.environ.get("WRITE_AS_POST_ID")         else ""
globals.WRITE_AS_USER            = str       (os.environ["WRITE_AS_USER"])            if os.environ.get("WRITE_AS_USER")            else ""
globals.XP_AMOUNT                = int       (os.environ["XP_AMOUNT"])                if os.environ.get("XP_AMOUNT")                else 50
globals.XP_COOLDOWN              = int       (os.environ["XP_COOLDOWN"])              if os.environ.get("XP_COOLDOWN")              else 30


# Only start bot if running as main and not import
if __name__ == '__main__':

    # Make persistent image components
    utils.setup_persistent_components()

    # Fetch database
    globals.loop.run_until_complete(utils.get_db())

    # Periodically save database
    async def database_loop():
        while True:
            await asyncio.sleep(900)
            await utils.save_db()
            if globals.bot.user:  # Check if logged in
                admin = globals.bot.get_user(globals.ADMIN_ID)
                if admin:
                    await admin.send(file=discord.File('db.sqlite3'))
                else:
                    print("Couldn't DM database backup!")
    globals.loop.create_task(database_loop())

    # Enable intents
    intents = discord.Intents.default()
    intents.members = True
    intents.presences = True
    # Create bot
    globals.bot = commands.Bot(command_prefix=utils.case_insensitive(globals.BOT_PREFIX), intents=intents, case_insensitive=True)
    globals.bot.remove_command('help')
    globals.bot.load_extension('cogs.bot')
    globals.bot.load_extension('cogs.fun')
    globals.bot.load_extension('cogs.levelling')
    globals.bot.load_extension('cogs.requests')
    globals.bot.load_extension('cogs.utilities')
    globals.bot.load_extension('cogs.staff')
    globals.bot.load_extension('jishaku')

    # On ready, fires when fully connected to Discord
    @globals.bot.event
    async def on_ready():
        print(f'Logged in as {globals.bot.user}!')
        update_presence_loop.start()
        # Compute next restart time
        now = datetime.datetime.utcnow()
        midnight = datetime.time(0, 0)
        next_midnight = datetime.datetime.combine(now, midnight)
        if next_midnight < now:
            next_midnight += datetime.timedelta(days=1)
        globals.start_dt = now
        globals.restart_dt = next_midnight
        # Exit after saving DB
        async def graceful_exit():
            print("Saving DB...")
            update_presence_loop.stop()
            await utils.save_db()
            await globals.db.close()
            admin = globals.bot.get_user(globals.ADMIN_ID)
            if admin:
                await admin.send(file=discord.File('db.sqlite3'))
            print("Exiting...")
            globals.loop.stop()
            os._exit(os.EX_OK)
        # Schedule graceful exit for kill signals
        for signame in ['SIGINT', 'SIGTERM']:
            globals.loop.add_signal_handler(getattr(signal, signame), lambda: globals.loop.create_task(graceful_exit()))
        # Wait until restart time
        await discord.utils.sleep_until(globals.restart_dt)
        # Force restart
        await utils.restart()

    # Ignore command not found errors
    @globals.bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.errors.CommandNotFound):
            return
        if isinstance(error, commands.errors.NotOwner):
            await utils.embed_reply(ctx,
                                    title="💢 Yea, that's not happening buddy!",
                                    thumbnail=globals.NO_PERM_ICON)
            return
        raise error

    # Greet user when they join
    @globals.bot.event
    async def on_member_join(member):
        if str(member.guild.id) in globals.JOIN_LOG_CHANNEL_IDS:
            channel = member.guild.get_channel(globals.JOIN_LOG_CHANNEL_IDS[str(member.guild.id)]["join_channel_id"])
            await channel.send(content=f"<@!{member.id}>",
                               embed=utils.custom_embed(member.guild,
                                                        title="👋 Welcome!",
                                                        description=f"Welcome <@!{member.id}> to Night City!\n"
                                                                    "\n" +
                                                                    (f"Make sure you have read through <#{globals.JOIN_LOG_CHANNEL_IDS[str(member.guild.id)]['rules_channel_id']}>!\n" if globals.JOIN_LOG_CHANNEL_IDS[str(member.guild.id)]["rules_channel_id"] else "") +
                                                                    (f"You can pick your poisons in <#{globals.JOIN_LOG_CHANNEL_IDS[str(member.guild.id)]['selfrole_channel_id']}>!\n" if globals.JOIN_LOG_CHANNEL_IDS[str(member.guild.id)]["selfrole_channel_id"] else "") +
                                                                    "Enjoy your stay!",
                                                        thumbnail=member.avatar_url))

    # Message handler and callback dispatcher
    @globals.bot.event
    async def on_message(message):
        if not message.guild:
            return
        req_channels = globals.REQUESTS_CHANNEL_IDS.get(str(message.guild.id)) or ()
        if message.channel.id in req_channels:
            if message.content and utils.is_requests_command(message.content):
                await globals.bot.process_commands(message)
            elif not utils.is_staff(message.author):
                await message.delete()
                try:
                    await message.author.send(embed=utils.custom_embed(message.guild,
                                                                       title="💢 Only relevant commands are allowed in mod requests channels!",
                                                                       description="Check the pinned messages for more information!"))
                except Exception:
                    pass
        elif message.content and message.content.lower().startswith(globals.BOT_PREFIX.lower()):
            await globals.bot.process_commands(message)
        else:
            await xp.process_xp(message)

    # Handle deleting requests by staff
    @globals.bot.event
    async def on_raw_message_delete(payload):
        req_channels = globals.REQUESTS_CHANNEL_IDS.get(str(payload.guild_id)) or ()
        if payload.channel_id in req_channels:
            await db.delete_request(msg=payload)

    # Change status every 15 seconds
    @tasks.loop(seconds=15)
    async def update_presence_loop():
        if globals.cur_presence == 0:
            await globals.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.competing, name='Cyberspace'),     status=discord.Status.dnd)
            globals.cur_presence = 1
        elif globals.cur_presence == 1:
            count = 0
            for guild in globals.bot.guilds:
                count += guild.member_count
            await globals.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f'{count} users'), status=discord.Status.dnd)
            globals.cur_presence = 2
        elif globals.cur_presence == 2:
            await globals.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,  name='the Blackwall'),  status=discord.Status.dnd)
            globals.cur_presence = 0

    # Actually run the bot
    while True:
        try:
            globals.loop.run_until_complete(globals.bot.start(globals.DISCORD_TOKEN))
        except discord.LoginFailure:
            # Invalid token
            print("BAD TOKEN!")
            globals.loop.run_until_complete(globals.bot.http.close())
            break
        except aiohttp.ClientConnectorError:
            # Connection to Discord failed
            print("CONNECTION ERROR! Sleeping 60 seconds...")
            globals.loop.run_until_complete(globals.bot.http.close())
            time.sleep(60)
            continue
        except KeyboardInterrupt:
            print("INTERRUPTED BY USER! Exiting...")
            globals.loop.run_until_complete(globals.bot.close())
            break
        globals.loop.run_until_complete(globals.bot.http.close())
        time.sleep(10)
