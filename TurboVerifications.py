import discord
from discord.ext import commands
import os
import random
import asyncio

# ---------- INTENTS ----------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ---------- FIX: REMOVE DEFAULT HELP COMMAND ----------
bot.remove_command('help')   # <-- THIS IS THE FIX

# ---------- WARNING STORAGE ----------
warnings = {}

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
    await bot.change_presence(activity=discord.Game(name='!help'))

# ---------- HELP COMMAND ----------
@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title='🤖 TurboBot Commands',
        description='Here are all my commands:',
        color=discord.Color.blue()
    )

    embed.add_field(
        name='🔐 Verification',
        value='`!setup_verification` - Send the verification embed',
        inline=False
    )
    embed.add_field(
        name='🎫 Tickets',
        value='`!ticket` - Send the ticket creation embed with button',
        inline=False
    )
    embed.add_field(
        name='🛡️ Moderation',
        value='`!kick @user [reason]` - Kick a member\n'
              '`!ban @user [reason]` - Ban a member\n'
              '`!mute @user [reason]` - Mute a member\n'
              '`!unmute @user` - Unmute a member\n'
              '`!warn @user [reason]` - Warn a member\n'
              '`!warnings @user` - Show warnings for a user\n'
              '`!clear [amount]` - Delete messages (1-100)\n'
              '`!purge` - Delete ALL messages in this channel',
        inline=False
    )
    embed.add_field(
        name='📊 Utility',
        value='`!serverinfo` - Show server info\n'
              '`!userinfo @user` - Show user info\n'
              '`!avatar @user` - Show user avatar\n'
              '`!ping` - Check bot latency',
        inline=False
    )
    embed.add_field(
        name='🎲 Fun',
        value='`!roll` - Roll a dice (1-6)\n'
              '`!coinflip` - Flip a coin\n'
              '`!say [message]` - Make me say something',
        inline=False
    )

    embed.set_footer(text='Made with ❤️ | TurboBot')
    await ctx.send(embed=embed)

# ---------- VERIFICATION SETUP ----------
@bot.command(name='setup_verification')
@commands.has_permissions(manage_roles=True)
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
async def ticket_setup(ctx):
    embed = discord.Embed(
        title='🎫 Support Tickets',
        description='Click the button below to open a support ticket.\nA staff member will assist you shortly.',
        color=discord.Color.blurple()
    )
    view = TicketButton()
    await ctx.send(embed=embed, view=view)

# ---------- MODERATION ----------
@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f'✅ {member.mention} has been kicked. Reason: {reason}')
    except:
        await ctx.send('❌ I cannot kick that member.')

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.ban(reason=reason)
        await ctx.send(f'✅ {member.mention} has been banned. Reason: {reason}')
    except:
        await ctx.send('❌ I cannot ban that member.')

@bot.command(name='mute')
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason="No reason provided"):
    muted_role = discord.utils.get(ctx.guild.roles, name='Muted')
    if not muted_role:
        await ctx.send('❌ Muted role not found. Please create a role named "Muted".')
        return
    try:
        await member.add_roles(muted_role, reason=reason)
        await ctx.send(f'✅ {member.mention} has been muted. Reason: {reason}')
    except:
        await ctx.send('❌ I cannot mute that member.')

@bot.command(name='unmute')
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name='Muted')
    if not muted_role:
        await ctx.send('❌ Muted role not found.')
        return
    try:
        await member.remove_roles(muted_role)
        await ctx.send(f'✅ {member.mention} has been unmuted.')
    except:
        await ctx.send('❌ I cannot unmute that member.')

@bot.command(name='warn')
@commands.has_permissions(manage_roles=True)
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

@bot.command(name='warnings')
@commands.has_permissions(manage_roles=True)
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
async def purge(ctx):
    await ctx.send('⏳ Deleting all messages in this channel...')
    deleted = await ctx.channel.purge(limit=None)
    await ctx.send(f'✅ Deleted {len(deleted)} messages.', delete_after=5)

# ---------- UTILITY ----------
@bot.command(name='serverinfo')
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
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f'{member}\'s Avatar', color=discord.Color.gold())
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send(f'🏓 Pong! Latency: {round(bot.latency * 1000)}ms')

# ---------- FUN ----------
@bot.command(name='roll')
async def roll(ctx):
    await ctx.send(f'🎲 You rolled a **{random.randint(1, 6)}**!')

@bot.command(name='coinflip')
async def coinflip(ctx):
    result = random.choice(['Heads', 'Tails'])
    await ctx.send(f'🪙 **{result}**!')

@bot.command(name='say')
async def say(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

# ---------- ERROR HANDLING ----------
@bot.event
async def on_command_error(ctx, error):
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
