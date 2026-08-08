import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

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

@bot.event
async def on_ready():
    print(f'✅ TurboVerification is online as {bot.user}')
    print(f'✅ In {len(bot.guilds)} guild(s)')

@bot.command(name='setup_verification')
@commands.has_permissions(manage_roles=True)
async def setup_verification(ctx):
    guild = ctx.guild
    bot_member = guild.me

    role = discord.utils.get(guild.roles, name='👥 Member')
    if not role:
        await ctx.send('❌ Role **👥 Member** not found. Please create it first (exactly with the emoji).')
        return

    if not bot_member.guild_permissions.manage_roles:
        await ctx.send('❌ I need `Manage Roles` permission.')
        return
    if role >= bot_member.top_role:
        await ctx.send(f'❌ `{role.name}` is above my highest role. I cannot assign it.')
        return
    if not role.is_assignable():
        await ctx.send(f'❌ `{role.name}` is managed by an integration and cannot be assigned.')
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

@setup_verification.error
async def setup_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('❌ You need `Manage Roles` permission.')

# ---------- SECURE TOKEN HANDLING ----------
token = os.environ.get('MTUzNTQ5ODAwNTQxMzc1Njk3OA.GAzRBe.xxli5O1cvKRycwNeczklPEQhjokpEzGwXeFYxI')
if token is None:
    print('❌ Error: TOKEN environment variable not set!')
else:
    bot.run(token)