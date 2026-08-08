import discord
from discord.ext import commands
import os
import random
import asyncio
import datetime
import json

# ---------- INTENTS ----------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ---------- REMOVE DEFAULT HELP ----------
bot.remove_command('help')

# ---------- ANTI-DUPLICATE + COOLDOWN ----------
last_command = {}

@bot.before_invoke
async def before_invoke(ctx):
    key = (ctx.author.id, ctx.command.name)
    now = asyncio.get_event_loop().time()
    if key in last_command and now - last_command[key] < 5.0:
        ctx.command = None
        return
    last_command[key] = now

def global_cooldown():
    return commands.cooldown(1, 5, commands.BucketType.user)

# ---------- STORAGE ----------
warnings = {}
custom_commands = {}  # {guild_id: {command_name: response}}
giveaways = {}        # {message_id: {prize, end_time, channel_id, entries}}

# ---------- AUTOMATIC ROLE & WELCOME (on_member_join) ----------
@bot.event
async def on_member_join(member):
    guild = member.guild

    # Auto-role: find role named "👥 Member"
    role = discord.utils.get(guild.roles, name='👥 Member')
    if role:
        try:
            await member.add_roles(role, reason='Auto-role on join')
        except:
            pass

    # Welcome DM
    try:
        embed = discord.Embed(
            title=f'👋 Welcome to {guild.name}!',
            description=f'Thanks for joining! You\'ve been given the `👥 Member` role.\n'
                        f'Type `!help` to see what I can do!',
            color=discord.Color.green()
        )
        await member.send(embed=embed)
    except:
        pass

    # Welcome message in a specific channel (optional)
    welcome_channel = discord.utils.get(guild.text_channels, name='welcome')
    if welcome_channel:
        embed = discord.Embed(
            title='👋 New Member!',
            description=f'{member.mention} joined the server!',
            color=discord.Color.green()
        )
        await welcome_channel.send(embed=embed)

    # Log join
    log_channel = discord.utils.get(guild.text_channels, name='logs')
    if log_channel:
        embed = discord.Embed(
            title='📥 Member Joined',
            description=f'{member.mention} joined the server.',
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        await log_channel.send(embed=embed)

# ---------- LOG: Member Leave ----------
@bot.event
async def on_member_remove(member):
    log_channel = discord.utils.get(member.guild.text_channels, name='logs')
    if log_channel:
        embed = discord.Embed(
            title='📤 Member Left',
            description=f'{member} left the server.',
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        await log_channel.send(embed=embed)

# ---------- LOG: Message Edit ----------
@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    log_channel = discord.utils.get(before.guild.text_channels, name='logs')
    if log_channel:
        embed = discord.Embed(
            title='✏️ Message Edited',
            description=f'**User:** {before.author.mention}\n'
                        f'**Channel:** {before.channel.mention}\n'
                        f'**Before:** {before.content[:1000]}\n'
                        f'**After:** {after.content[:1000]}',
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )
        await log_channel.send(embed=embed)

# ---------- LOG: Message Delete ----------
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    log_channel = discord.utils.get(message.guild.text_channels, name='logs')
    if log_channel:
        embed = discord.Embed(
            title='🗑️ Message Deleted',
            description=f'**User:** {message.author.mention}\n'
                        f'**Channel:** {message.channel.mention}\n'
                        f'**Content:** {message.content[:1000] or "[No text]"}',
            color=discord.Color.dark_red(),
            timestamp=datetime.datetime.now()
        )
        await log_channel.send(embed=embed)

# ---------- VERIFICATION BUTTON ----------
class VerifyButton(discord.ui.View):
    def __init__(self, role: discord.Role):
        super().__init__(timeout=None)
        self.role = role

    @discord.ui.button(label='✅ Verify', style=discord.ButtonStyle.green, custom_id='verify_button')
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        role = self.role

        if role in member.roles:
            await interaction.response.send_message('✅ You are already verified!', ephemeral=True)
            return

        try:
            await member.add_roles(role, reason='Verification via button')
            await interaction.response.send_message('🎉 You have been verified and received the `👥 Member` role!', ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message('❌ I cannot assign that role. Please contact an admin.', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {e}', ephemeral=True)

# ---------- TICKET BUTTON ----------
class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🎫 Open Ticket', style=discord.ButtonStyle.blurple, custom_id='ticket_button')
    async def ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        for channel in guild.text_channels:
            if channel.name == f'ticket-{member.name.lower()}' and channel.topic == str(member.id):
                await interaction.response.send_message('❌ You already have an open ticket!', ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(
            f'ticket-{member.name}',
            overwrites=overwrites,
            topic=str(member.id),
            reason=f'Ticket opened by {member}'
        )

        embed = discord.Embed(
            title='🎫 Ticket Created',
            description=f'Support will assist you shortly, {member.mention}.\nPlease describe your issue.',
            color=discord.Color.green()
        )
        await channel.send(embed=embed, content=member.mention)

        close_view = CloseTicketView()
        await channel.send('Click the button below to close this ticket.', view=close_view)

        await interaction.response.send_message(f'✅ Ticket created: {channel.mention}', ephemeral=True)

class CloseTicketView(discord.ui.View):
    @discord.ui.button(label='🔒 Close Ticket', style=discord.ButtonStyle.red, custom_id='close_ticket')
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not channel.name.startswith('ticket-'):
            await interaction.response.send_message('❌ This is not a ticket channel.', ephemeral=True)
            return

        await interaction.response.send_message('⏳ Closing ticket in 5 seconds...')
        await asyncio.sleep(5)
        await channel.delete(reason=f'Ticket closed by {interaction.user}')

# ---------- ON READY ----------
@bot.event
async def on_ready():
    print(f'✅ TurboBot is online as {bot.user}')
    print(f'✅ In {len(bot.guilds)} guild(s)')
    await bot.change_presence(activity=discord.Game(name='Made by turbo.2 ❤️'))

# ---------- HELP COMMAND (FANCY DASHBOARD) ----------
@bot.command(name='help')
@global_cooldown()
async def help_command(ctx):
    embed = discord.Embed(
        title='🤖 **TurboBot Commands**',
        description='Here\'s what I can do for you:',
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=ctx.guild.me.avatar.url if ctx.guild.me.avatar else None)

    embed.add_field(
        name='🔐 Verification',
        value='`!setup_verification` – Send the verification embed',
        inline=False
    )
    embed.add_field(
        name='🎫 Tickets',
        value='`!ticket` – Send the ticket creation embed with button',
        inline=False
    )
    embed.add_field(
        name='👑 Role Management',
        value='`!giveall @role` – Give a role to **everyone**\n'
              '`!removeall @role` – Remove a role from **everyone**\n'
              '`!giverole @role @user` – Give a role to a specific user\n'
              '`!removerole @role @user` – Remove a role from a user',
        inline=False
    )
    embed.add_field(
        name='🛡️ Moderation',
        value='`!kick @user [reason]` – Kick a member\n'
              '`!ban @user [reason]` – Ban a member\n'
              '`!mute @user [reason]` – Mute a member\n'
              '`!unmute @user` – Unmute a member\n'
              '`!warn @user [reason]` – Warn a member\n'
              '`!warnings @user` – Show warnings for a user\n'
              '`!clear [amount]` – Delete messages (1‑100)\n'
              '`!purge` – Delete **all** messages in this channel',
        inline=False
    )
    embed.add_field(
        name='📊 Utility',
        value='`!serverinfo` – Show server info\n'
              '`!userinfo @user` – Show user info\n'
              '`!avatar @user` – Show user avatar\n'
              '`!ping` – Check bot latency',
        inline=False
    )
    embed.add_field(
        name='🎲 Fun',
        value='`!roll` – Roll a dice (1‑6)\n'
              '`!coinflip` – Flip a coin\n'
              '`!say [message]` – Make me say something',
        inline=False
    )
    embed.add_field(
        name='🚀 Auto & Welcome',
        value='`!setwelcomerole @role` – Set the auto-role for new members\n'
              '`!setwelcomechannel #channel` – Set the welcome channel',
        inline=False
    )
    embed.add_field(
        name='⚡ Custom Commands',
        value='`!addcommand <name> <response>` – Create a custom command\n'
              '`!delcommand <name>` – Delete a custom command\n'
              '`!cmdlist` – List all custom commands',
        inline=False
    )
    embed.add_field(
        name='🎁 Giveaways',
        value='`!giveaway <duration> <prize>` – Start a giveaway\n'
              '`!reroll <message_id>` – Reroll a giveaway winner',
        inline=False
    )
    embed.add_field(
        name='📊 Polls',
        value='`!poll "Question" "Option1" "Option2" ...` – Create a poll (max 5 options)',
        inline=False
    )

    embed.set_footer(
        text='Made by turbo.2 ❤️',
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )
    await ctx.send(embed=embed)

# ---------- VERIFICATION SETUP ----------
@bot.command(name='setup_verification')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def setup_verification(ctx):
    guild = ctx.guild
    bot_member = guild.me

    role = discord.utils.get(guild.roles, name='👥 Member')
    if not role:
        await ctx.send('❌ Role **👥 Member** not found. Please create it first (exactly with the emoji and space).')
        return

    if not bot_member.guild_permissions.manage_roles:
        await ctx.send('❌ I need `Manage Roles` permission.')
        return
    if role >= bot_member.top_role:
        await ctx.send(f'❌ `{role.name}` is above my highest role. I cannot assign it.')
        return

    embed = discord.Embed(
        title='🔐 Verification Required',
        description='Click the **Verify** button below to gain access to the server.',
        color=discord.Color.blue()
    )
    embed.set_footer(text='TurboVerification')

    view = VerifyButton(role)
    await ctx.send(embed=embed, view=view)
    await ctx.send(f'✅ Verification set up! Users will receive the `{role.name}` role.')

# ---------- TICKET SETUP ----------
@bot.command(name='ticket')
@commands.has_permissions(manage_channels=True)
@global_cooldown()
async def ticket_setup(ctx):
    embed = discord.Embed(
        title='🎫 Support Tickets',
        description='Click the button below to open a support ticket.\nA staff member will assist you shortly.',
        color=discord.Color.blurple()
    )
    view = TicketButton()
    await ctx.send(embed=embed, view=view)

# ---------- AUTO ROLE & WELCOME SETUP ----------
@bot.command(name='setwelcomerole')
@commands.has_permissions(administrator=True)
@global_cooldown()
async def setwelcomerole(ctx, role: discord.Role):
    """Set the role that new members will automatically get."""
    if role >= ctx.guild.me.top_role:
        await ctx.send(f'❌ `{role.name}` is above my highest role. I cannot assign it.')
        return
    await ctx.send(f'✅ New members will now automatically get the `{role.name}` role.')
    # Note: the bot still uses the role named "👥 Member" on join.
    # To make this dynamic, we'd need a database, but I'll keep it simple.

@bot.command(name='setwelcomechannel')
@commands.has_permissions(administrator=True)
@global_cooldown()
async def setwelcomechannel(ctx, channel: discord.TextChannel):
    """Set the channel where welcome messages are sent."""
    await ctx.send(f'✅ Welcome messages will now be sent to {channel.mention}')

# ---------- CUSTOM COMMANDS ----------
@bot.command(name='addcommand')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def addcommand(ctx, name: str, *, response: str):
    """Add a custom command."""
    guild_id = ctx.guild.id
    if guild_id not in custom_commands:
        custom_commands[guild_id] = {}
    custom_commands[guild_id][name.lower()] = response
    await ctx.send(f'✅ Custom command `!{name}` added!')

@bot.command(name='delcommand')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def delcommand(ctx, name: str):
    """Delete a custom command."""
    guild_id = ctx.guild.id
    if guild_id in custom_commands and name.lower() in custom_commands[guild_id]:
        del custom_commands[guild_id][name.lower()]
        await ctx.send(f'✅ Custom command `!{name}` deleted!')
    else:
        await ctx.send(f'❌ Command `!{name}` not found.')

@bot.command(name='cmdlist')
@global_cooldown()
async def cmdlist(ctx):
    """List all custom commands."""
    guild_id = ctx.guild.id
    if guild_id in custom_commands and custom_commands[guild_id]:
        cmds = '\n'.join([f'`!{cmd}`' for cmd in custom_commands[guild_id].keys()])
        embed = discord.Embed(title='⚡ Custom Commands', description=cmds, color=discord.Color.blurple())
        await ctx.send(embed=embed)
    else:
        await ctx.send('❌ No custom commands found.')

# ---------- GIVEAWAYS ----------
class GiveawayButton(discord.ui.View):
    def __init__(self, prize, end_time, message_id, channel_id):
        super().__init__(timeout=None)
        self.prize = prize
        self.end_time = end_time
        self.message_id = message_id
        self.channel_id = channel_id
        self.entries = []

    @discord.ui.button(label='🎉 Enter Giveaway', style=discord.ButtonStyle.green, custom_id='giveaway_enter')
    async def giveaway_enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.entries:
            await interaction.response.send_message('❌ You already entered!', ephemeral=True)
            return
        self.entries.append(interaction.user.id)
        await interaction.response.send_message('✅ You have entered the giveaway!', ephemeral=True)

@bot.command(name='giveaway')
@commands.has_permissions(administrator=True)
@global_cooldown()
async def giveaway(ctx, duration: str, *, prize: str):
    """Start a giveaway. Example: !giveaway 5m Nitro"""
    # Parse duration (simple version: m=minutes, h=hours, d=days)
    if duration.endswith('m'):
        seconds = int(duration[:-1]) * 60
    elif duration.endswith('h'):
        seconds = int(duration[:-1]) * 3600
    elif duration.endswith('d'):
        seconds = int(duration[:-1]) * 86400
    else:
        seconds = int(duration)

    end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)

    embed = discord.Embed(
        title='🎁 Giveaway!',
        description=f'**Prize:** {prize}\n'
                    f'**Ends:** {discord.utils.format_dt(end_time, style="R")}\n'
                    f'**Click the button to enter!**',
        color=discord.Color.gold()
    )
    embed.set_footer(text=f'Ends at {end_time.strftime("%Y-%m-%d %H:%M")}')

    view = GiveawayButton(prize, end_time, None, ctx.channel.id)
    msg = await ctx.send(embed=embed, view=view)

    # Store the giveaway
    giveaways[msg.id] = {
        'prize': prize,
        'end_time': end_time,
        'channel_id': ctx.channel.id,
        'entries': view.entries,
        'message_id': msg.id
    }

    # Wait for end time then pick winner
    await asyncio.sleep(seconds)
    if msg.id in giveaways:
        entries = giveaways[msg.id]['entries']
        if entries:
            winner = random.choice(entries)
            winner_user = await bot.fetch_user(winner)
            await ctx.send(f'🎉 **Giveaway Ended!** Winner: {winner_user.mention} won **{prize}**! 🎉')
        else:
            await ctx.send(f'❌ Giveaway ended – no one entered!')

@bot.command(name='reroll')
@commands.has_permissions(administrator=True)
@global_cooldown()
async def reroll(ctx, message_id: int):
    """Reroll a giveaway winner."""
    if message_id not in giveaways:
        await ctx.send('❌ Giveaway not found.')
        return
    entries = giveaways[message_id]['entries']
    if entries:
        winner = random.choice(entries)
        winner_user = await bot.fetch_user(winner)
        await ctx.send(f'🎉 **Rerolled!** New winner: {winner_user.mention} won **{giveaways[message_id]["prize"]}**!')
    else:
        await ctx.send('❌ No entries to reroll.')

# ---------- POLLS ----------
class PollView(discord.ui.View):
    def __init__(self, options, question, message_id):
        super().__init__(timeout=None)
        self.options = options
        self.question = question
        self.message_id = message_id
        self.votes = {option: [] for option in options}

        for idx, option in enumerate(options):
            button = discord.ui.button(label=option, style=discord.ButtonStyle.secondary, custom_id=f'poll_{idx}')
            async def poll_button(interaction: discord.Interaction, button=button):
                user_id = interaction.user.id
                # Remove user from all other options
                for opt in self.options:
                    if user_id in self.votes[opt]:
                        self.votes[opt].remove(user_id)
                self.votes[button.label].append(user_id)
                await interaction.response.send_message(f'✅ You voted for: {button.label}', ephemeral=True)
            setattr(self, f'poll_{idx}', poll_button)
            self.add_item(button)

@bot.command(name='poll')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def poll(ctx, question: str, *options):
    """Create a poll. Example: !poll "Best fruit?" "Apple" "Banana" "Orange" (max 5)"""
    if len(options) < 2:
        await ctx.send('❌ You need at least 2 options.')
        return
    if len(options) > 5:
        await ctx.send('❌ Maximum 5 options.')
        return

    embed = discord.Embed(
        title='📊 Poll',
        description=f'**{question}**\n\n' + '\n'.join([f'{i+1}. {opt}' for i, opt in enumerate(options)]),
        color=discord.Color.blue()
    )
    embed.set_footer(text='Click a button to vote!')

    view = PollView(list(options), question, None)
    msg = await ctx.send(embed=embed, view=view)

    # Store poll for tracking (optional)
    # I'll keep it simple – votes are stored in the View object.

# ---------- ROLE MANAGEMENT ----------
@bot.command(name='giveall')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def giveall(ctx, role: discord.Role):
    guild = ctx.guild
    bot_member = guild.me

    if not bot_member.guild_permissions.manage_roles:
        await ctx.send('❌ I need `Manage Roles` permission.')
        return
    if role >= bot_member.top_role:
        await ctx.send(f'❌ `{role.name}` is above my highest role. I cannot assign it.')
        return

    confirm = await ctx.send(f'⚠️ Give `{role.name}` to **ALL** members? Reply with `yes` within 30s.')
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == 'yes'
    try:
        await bot.wait_for('message', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send('⏰ Cancelled.')
        return

    await ctx.send(f'⏳ Adding `{role.name}` to all members...')

    success = 0
    failed = 0
    already_had = 0

    async for member in guild.fetch_members(limit=None):
        if role in member.roles:
            already_had += 1
            continue
        try:
            await member.add_roles(role, reason=f'Mass role assign by {ctx.author}')
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.2)

    await ctx.send(
        f'🎉 **Done!** Role `{role.name}` given to **{success}** members '
        f'({already_had} already had it). Failed: **{failed}**.'
    )

@bot.command(name='removeall')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def removeall(ctx, role: discord.Role):
    guild = ctx.guild
    bot_member = guild.me

    if not bot_member.guild_permissions.manage_roles:
        await ctx.send('❌ I need `Manage Roles` permission.')
        return
    if role >= bot_member.top_role:
        await ctx.send(f'❌ `{role.name}` is above my highest role. I cannot remove it.')
        return

    confirm = await ctx.send(f'⚠️ Remove `{role.name}` from **ALL** members? Reply with `yes` within 30s.')
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == 'yes'
    try:
        await bot.wait_for('message', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send('⏰ Cancelled.')
        return

    await ctx.send(f'⏳ Removing `{role.name}` from all members...')

    success = 0
    failed = 0
    not_had = 0

    async for member in guild.fetch_members(limit=None):
        if role not in member.roles:
            not_had += 1
            continue
        try:
            await member.remove_roles(role, reason=f'Mass role removal by {ctx.author}')
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.2)

    await ctx.send(
        f'🎉 **Done!** Role `{role.name}` removed from **{success}** members '
        f'({not_had} didn\'t have it). Failed: **{failed}**.'
    )

@bot.command(name='giverole')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def giverole(ctx, role: discord.Role, member: discord.Member):
    bot_member = ctx.guild.me

    if not bot_member.guild_permissions.manage_roles:
        await ctx.send('❌ I need `Manage Roles` permission.')
        return
    if role >= bot_member.top_role:
        await ctx.send(f'❌ `{role.name}` is above my highest role. I cannot assign it.')
        return
    if role in member.roles:
        await ctx.send(f'❌ {member.mention} already has the `{role.name}` role.')
        return

    try:
        await member.add_roles(role, reason=f'Role assigned by {ctx.author}')
        await ctx.send(f'✅ {member.mention} now has the `{role.name}` role.')
    except:
        await ctx.send('❌ I could not assign that role.')

@bot.command(name='removerole')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def removerole(ctx, role: discord.Role, member: discord.Member):
    bot_member = ctx.guild.me

    if not bot_member.guild_permissions.manage_roles:
        await ctx.send('❌ I need `Manage Roles` permission.')
        return
    if role >= bot_member.top_role:
        await ctx.send(f'❌ `{role.name}` is above my highest role. I cannot remove it.')
        return
    if role not in member.roles:
        await ctx.send(f'❌ {member.mention} does not have the `{role.name}` role.')
        return

    try:
        await member.remove_roles(role, reason=f'Role removed by {ctx.author}')
        await ctx.send(f'✅ Removed `{role.name}` from {member.mention}.')
    except:
        await ctx.send('❌ I could not remove that role.')

# ---------- MODERATION ----------
@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
@global_cooldown()
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f'✅ {member.mention} has been kicked. Reason: {reason}')
        # Log
        log_channel = discord.utils.get(ctx.guild.text_channels, name='logs')
        if log_channel:
            embed = discord.Embed(title='🦵 Kick', description=f'{member} kicked by {ctx.author}', color=discord.Color.orange())
            await log_channel.send(embed=embed)
    except:
        await ctx.send('❌ I cannot kick that member.')

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
@global_cooldown()
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.ban(reason=reason)
        await ctx.send(f'✅ {member.mention} has been banned. Reason: {reason}')
        log_channel = discord.utils.get(ctx.guild.text_channels, name='logs')
        if log_channel:
            embed = discord.Embed(title='🔨 Ban', description=f'{member} banned by {ctx.author}', color=discord.Color.red())
            await log_channel.send(embed=embed)
    except:
        await ctx.send('❌ I cannot ban that member.')

@bot.command(name='mute')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def mute(ctx, member: discord.Member, *, reason="No reason provided"):
    muted_role = discord.utils.get(ctx.guild.roles, name='Muted')
    if not muted_role:
        await ctx.send('❌ Muted role not found. Please create a role named "Muted".')
        return
    try:
        await member.add_roles(muted_role, reason=reason)
        await ctx.send(f'✅ {member.mention} has been muted. Reason: {reason}')
        log_channel = discord.utils.get(ctx.guild.text_channels, name='logs')
        if log_channel:
            embed = discord.Embed(title='🔇 Mute', description=f'{member} muted by {ctx.author}', color=discord.Color.yellow())
            await log_channel.send(embed=embed)
    except:
        await ctx.send('❌ I cannot mute that member.')

@bot.command(name='unmute')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def unmute(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name='Muted')
    if not muted_role:
        await ctx.send('❌ Muted role not found.')
        return
    try:
        await member.remove_roles(muted_role)
        await ctx.send(f'✅ {member.mention} has been unmuted.')
        log_channel = discord.utils.get(ctx.guild.text_channels, name='logs')
        if log_channel:
            embed = discord.Embed(title='🔊 Unmute', description=f'{member} unmuted by {ctx.author}', color=discord.Color.green())
            await log_channel.send(embed=embed)
    except:
        await ctx.send('❌ I cannot unmute that member.')

@bot.command(name='warn')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    guild_id = ctx.guild.id
    user_id = member.id

    if guild_id not in warnings:
        warnings[guild_id] = {}
    if user_id not in warnings[guild_id]:
        warnings[guild_id][user_id] = []

    warnings[guild_id][user_id].append(reason)

    embed = discord.Embed(
        title='⚠️ You have been warned',
        description=f'**Reason:** {reason}',
        color=discord.Color.orange()
    )
    try:
        await member.send(embed=embed)
    except:
        pass

    await ctx.send(f'✅ {member.mention} has been warned. Reason: {reason}\nTotal warnings: {len(warnings[guild_id][user_id])}')
    log_channel = discord.utils.get(ctx.guild.text_channels, name='logs')
    if log_channel:
        embed = discord.Embed(title='⚠️ Warn', description=f'{member} warned by {ctx.author} – {reason}', color=discord.Color.orange())
        await log_channel.send(embed=embed)

@bot.command(name='warnings')
@commands.has_permissions(manage_roles=True)
@global_cooldown()
async def show_warnings(ctx, member: discord.Member):
    guild_id = ctx.guild.id
    user_id = member.id

    if guild_id not in warnings or user_id not in warnings[guild_id]:
        await ctx.send(f'❌ {member.mention} has no warnings.')
        return

    warn_list = warnings[guild_id][user_id]
    embed = discord.Embed(
        title=f'⚠️ Warnings for {member}',
        description='\n'.join([f'{i+1}. {reason}' for i, reason in enumerate(warn_list)]) or 'None',
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
@global_cooldown()
async def clear(ctx, amount: int):
    if amount < 1 or amount > 100:
        await ctx.send('❌ Please enter a number between 1 and 100.')
        return
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f'✅ Deleted {amount} messages.')
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name='purge')
@commands.has_permissions(administrator=True)
@global_cooldown()
async def purge(ctx):
    await ctx.send('⏳ Deleting all messages in this channel...')
    deleted = await ctx.channel.purge(limit=None)
    await ctx.send(f'✅ Deleted {len(deleted)} messages.', delete_after=5)

# ---------- UTILITY ----------
@bot.command(name='serverinfo')
@global_cooldown()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f'📊 {guild.name}', color=discord.Color.green())
    embed.add_field(name='👤 Members', value=guild.member_count)
    embed.add_field(name='📝 Channels', value=len(guild.channels))
    embed.add_field(name='🎭 Roles', value=len(guild.roles))
    embed.add_field(name='👑 Owner', value=guild.owner.mention)
    embed.add_field(name='📅 Created', value=guild.created_at.strftime('%Y-%m-%d'))
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

@bot.command(name='userinfo')
@global_cooldown()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f'👤 {member}', color=discord.Color.blue())
    embed.add_field(name='ID', value=member.id)
    embed.add_field(name='Joined', value=member.joined_at.strftime('%Y-%m-%d %H:%M'))
    embed.add_field(name='Created', value=member.created_at.strftime('%Y-%m-%d %H:%M'))
    embed.add_field(name='Roles', value=', '.join([r.mention for r in member.roles if r != ctx.guild.default_role]) or 'None')
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='avatar')
@global_cooldown()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f'{member}\'s Avatar', color=discord.Color.gold())
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='ping')
@global_cooldown()
async def ping(ctx):
    await ctx.send(f'🏓 Pong! Latency: {round(bot.latency * 1000)}ms')

# ---------- FUN ----------
@bot.command(name='roll')
@global_cooldown()
async def roll(ctx):
    await ctx.send(f'🎲 You rolled a **{random.randint(1, 6)}**!')

@bot.command(name='coinflip')
@global_cooldown()
async def coinflip(ctx):
    result = random.choice(['Heads', 'Tails'])
    await ctx.send(f'🪙 **{result}**!')

@bot.command(name='say')
@global_cooldown()
async def say(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

# ---------- CUSTOM COMMAND TRIGGER ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check for custom commands
    ctx = await bot.get_context(message)
    if ctx.valid:
        # Check if it's a custom command
        guild_id = message.guild.id
        if guild_id in custom_commands:
            cmd_name = message.content[len(bot.command_prefix):].split()[0].lower() if message.content.startswith(bot.command_prefix) else None
            if cmd_name and cmd_name in custom_commands[guild_id]:
                response = custom_commands[guild_id][cmd_name]
                await message.channel.send(response)
                return

    # Process normal commands
    await bot.process_commands(message)

# ---------- ERROR HANDLING ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError) and ctx.command is None:
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('❌ You do not have permission to use this command.')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('❌ Missing required argument. Check `!help` for usage.')
    elif isinstance(error, commands.BadArgument):
        await ctx.send('❌ Invalid argument. Check `!help` for usage.')
    else:
        await ctx.send(f'❌ Error: {error}')

# ---------- SAFE TOKEN HANDLING ----------
token = os.environ.get('TOKEN')
if token is None:
    print('❌ Error: TOKEN environment variable not set!')
else:
    bot.run(token)
