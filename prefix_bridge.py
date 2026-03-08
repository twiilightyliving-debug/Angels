"""
prefix_bridge.py
─────────────────────────────────────────────
Sistema que permite usar slash commands via prefix (ex: .warn @user motivo)
Funciona criando uma FakeInteraction que imita o objeto discord.Interaction.
Adicione no seu main.py:
    from prefix_bridge import setup_prefix_bridge
    setup_prefix_bridge(bot)
"""

import discord
from discord.ext import commands
from discord import app_commands
import inspect
import datetime


# ────────────────────────────────────────────────────────────
# FakeResponse — imita interaction.response
# ────────────────────────────────────────────────────────────
class FakeResponse:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author
        self._done = False

    def is_done(self):
        return self._done

    async def send_message(self, content=None, *, embed=None, embeds=None, ephemeral=False, view=None, **kwargs):
        self._done = True
        send_kwargs = {}
        if content:
            send_kwargs["content"] = content
        if embed:
            send_kwargs["embed"] = embed
        if embeds:
            send_kwargs["embeds"] = embeds
        if view:
            send_kwargs["view"] = view
        await self.channel.send(**send_kwargs)

    async def defer(self, ephemeral=False, thinking=False):
        self._done = True  # Simula o defer sem enviar nada


# ────────────────────────────────────────────────────────────
# FakeFollowup — imita interaction.followup
# ────────────────────────────────────────────────────────────
class FakeFollowup:
    def __init__(self, channel):
        self.channel = channel

    async def send(self, content=None, *, embed=None, embeds=None, ephemeral=False, view=None, **kwargs):
        send_kwargs = {}
        if content:
            send_kwargs["content"] = content
        if embed:
            send_kwargs["embed"] = embed
        if embeds:
            send_kwargs["embeds"] = embeds
        if view:
            send_kwargs["view"] = view
        await self.channel.send(**send_kwargs)


# ────────────────────────────────────────────────────────────
# FakeInteraction — imita discord.Interaction
# ────────────────────────────────────────────────────────────
class FakeInteraction:
    def __init__(self, message: discord.Message, command=None):
        self.message    = message
        self.user       = message.author
        self.channel    = message.channel
        self.guild      = message.guild
        self.guild_id   = message.guild.id if message.guild else None
        self.command    = command
        self.response   = FakeResponse(message.channel, message.author)
        self.followup   = FakeFollowup(message.channel)
        self.client     = message.guild._state._get_client() if message.guild else None

        # Permissões simuladas (pega as permissões reais do membro no canal)
        if isinstance(message.author, discord.Member):
            self._permissions = message.channel.permissions_for(message.author)
        else:
            self._permissions = discord.Permissions.none()

    @property
    def permissions(self):
        return self._permissions


# ────────────────────────────────────────────────────────────
# Conversor de argumentos — transforma strings nos tipos certos
# ────────────────────────────────────────────────────────────
async def convert_argument(bot: commands.Bot, guild: discord.Guild, channel, param_annotation, raw_value: str):
    """Converte um argumento string para o tipo esperado pelo slash command."""

    if param_annotation in (str, inspect.Parameter.empty):
        return raw_value

    if param_annotation == int:
        try:
            return int(raw_value)
        except ValueError:
            raise ValueError(f"❌ `{raw_value}` não é um número válido.")

    if param_annotation == float:
        try:
            return float(raw_value)
        except ValueError:
            raise ValueError(f"❌ `{raw_value}` não é um número decimal válido.")

    if param_annotation == bool:
        return raw_value.lower() in ("sim", "s", "yes", "y", "true", "1")

    if param_annotation == discord.Member:
        # Suporta @menção ou ID
        raw_id = raw_value.strip("<@!>")
        try:
            member = guild.get_member(int(raw_id))
            if not member:
                member = await guild.fetch_member(int(raw_id))
            return member
        except (ValueError, discord.NotFound):
            raise ValueError(f"❌ Membro `{raw_value}` não encontrado.")

    if param_annotation == discord.User:
        raw_id = raw_value.strip("<@!>")
        try:
            return await bot.fetch_user(int(raw_id))
        except (ValueError, discord.NotFound):
            raise ValueError(f"❌ Usuário `{raw_value}` não encontrado.")

    if param_annotation == discord.Role:
        raw_id = raw_value.strip("<@&>")
        try:
            role = guild.get_role(int(raw_id))
            if role:
                return role
        except ValueError:
            pass
        # Tenta por nome
        role = discord.utils.get(guild.roles, name=raw_value)
        if role:
            return role
        raise ValueError(f"❌ Cargo `{raw_value}` não encontrado.")

    if param_annotation == discord.TextChannel:
        raw_id = raw_value.strip("<#>")
        try:
            ch = guild.get_channel(int(raw_id))
            if ch:
                return ch
        except ValueError:
            pass
        ch = discord.utils.get(guild.text_channels, name=raw_value)
        if ch:
            return ch
        raise ValueError(f"❌ Canal `{raw_value}` não encontrado.")

    # Tipo desconhecido → retorna string
    return raw_value


# ────────────────────────────────────────────────────────────
# Setup principal — registra o on_message no bot
# ────────────────────────────────────────────────────────────
def setup_prefix_bridge(bot: commands.Bot):
    """
    Registra o listener on_message no bot para capturar comandos com prefix
    e executar os slash commands correspondentes.
    """

    @bot.listen("on_message")
    async def prefix_bridge_listener(message: discord.Message):
        # Ignora bots e DMs
        if message.author.bot:
            return
        if not message.guild:
            return

        prefix = bot.command_prefix
        if callable(prefix):
            prefix = await prefix(bot, message)
        if isinstance(prefix, (list, tuple)):
            matched_prefix = next((p for p in prefix if message.content.startswith(p)), None)
            if not matched_prefix:
                return
            prefix = matched_prefix
        elif not message.content.startswith(prefix):
            return

        # Remove o prefix e divide em partes
        content = message.content[len(prefix):].strip()
        if not content:
            return

        parts = content.split()
        command_name = parts[0].lower()
        raw_args = parts[1:]

        # Procura o slash command pelo nome
        slash_command = bot.tree.get_command(command_name)
        if not slash_command:
            return  # Comando não existe, ignora silenciosamente

        # Cria a FakeInteraction
        fake_interaction = FakeInteraction(message, command=slash_command)

        # Pega os parâmetros do comando (ignora 'self' e 'interaction')
        callback = slash_command.callback
        sig = inspect.signature(callback)
        params = [
            (name, param)
            for name, param in sig.parameters.items()
            if name not in ("self", "interaction")
        ]

        # Converte os argumentos
        kwargs = {}
        for i, (name, param) in enumerate(params):
            annotation = param.annotation

            # Parâmetro com default (opcional)
            has_default = param.default is not inspect.Parameter.empty

            if i >= len(raw_args):
                if has_default:
                    kwargs[name] = param.default
                    continue
                else:
                    await message.channel.send(f"❌ Argumento obrigatório faltando: `{name}`\n💡 Uso: `{prefix}{command_name} {' '.join(f'<{n}>' for n, _ in params)}`")
                    return

            # O último parâmetro string captura o resto da mensagem
            if annotation in (str, inspect.Parameter.empty) and i == len(params) - 1:
                raw_value = " ".join(raw_args[i:])
            else:
                raw_value = raw_args[i]

            try:
                kwargs[name] = await convert_argument(bot, message.guild, message.channel, annotation, raw_value)
            except ValueError as e:
                await message.channel.send(str(e))
                return

        # Verifica permissões (default_permissions do slash command)
        if slash_command.default_permissions:
            member_perms = message.channel.permissions_for(message.author)
            missing = [
                perm for perm, value in slash_command.default_permissions
                if value and not getattr(member_perms, perm, False)
            ]
            if missing and not message.author.guild_permissions.administrator:
                perms_fmt = ", ".join(p.replace("_", " ").title() for p in missing)
                await message.channel.send(f"❌ Você não tem permissão: **{perms_fmt}**")
                return

        # Executa o comando
        try:
            cog = slash_command.binding  # o Cog ao qual pertence
            if cog:
                await callback(cog, fake_interaction, **kwargs)
            else:
                await callback(fake_interaction, **kwargs)
        except Exception as e:
            await message.channel.send(f"❌ Erro ao executar o comando: `{e}`")
            raise