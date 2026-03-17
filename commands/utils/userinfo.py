import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

# ── Badges do Discord ─────────────────────────────────────────────────────────
# Usando atributos como string para evitar o erro de 'flag_value'
BADGES = [
    ("staff",                       "👨‍💼", "Staff do Discord"),
    ("partner",                     "🤝", "Parceiro Discord"),
    ("hypesquad",                   "🏠", "HypeSquad Events"),
    ("bug_hunter",                  "🐛", "Bug Hunter Nível 1"),
    ("hypesquad_bravery",           "🟣", "HypeSquad Bravery"),
    ("hypesquad_brilliance",        "🔴", "HypeSquad Brilliance"),
    ("hypesquad_balance",           "🟡", "HypeSquad Balance"),
    ("early_supporter",             "⭐", "Early Supporter"),
    ("bug_hunter_level_2",          "🥇", "Bug Hunter Nível 2"),
    ("verified_bot_developer",      "🔧", "Desenvolvedor de Bot Verificado"),
    ("discord_certified_moderator", "🛡️", "Moderador Certificado"),
    ("active_developer",            "💻", "Desenvolvedor Ativo"),
]

def get_badges(user: discord.User | discord.Member) -> str:
    flags = user.public_flags
    badges = [f"{emoji} {nome}" for attr, emoji, nome in BADGES if getattr(flags, attr, False)]
    return "\n".join(badges) if badges else "Nenhuma"

# ── Helpers de tempo ──────────────────────────────────────────────────────────

def tempo_relativo(dt: datetime) -> str:
    agora = datetime.now(timezone.utc)
    diff = agora - dt
    dias = diff.days
    horas = diff.seconds // 3600
    minutos = (diff.seconds % 3600) // 60

    partes = []
    if dias > 0:
        anos = dias // 365
        meses = (dias % 365) // 30
        dias_rest = dias % 30
        if anos > 0:
            partes.append(f"{anos} ano{'s' if anos > 1 else ''}")
        if meses > 0:
            partes.append(f"{meses} {'mês' if meses == 1 else 'meses'}")
        if dias_rest > 0:
            partes.append(f"{dias_rest} dia{'s' if dias_rest > 1 else ''}")
    if horas > 0:
        partes.append(f"{horas} hora{'s' if horas > 1 else ''}")
    if minutos > 0 and not partes:
        partes.append(f"{minutos} minuto{'s' if minutos > 1 else ''}")

    return " ".join(partes) if partes else "agora mesmo"

def formatar_dt(dt: datetime) -> str:
    meses = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    return f"{dt.day} de {meses[dt.month - 1]} de {dt.year}, às {dt.hour:02d}:{dt.minute:02d}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cor(alvo) -> discord.Color:
    cor = getattr(alvo, 'color', None)
    if cor and cor.value:
        return cor
    return discord.Color(0x040505)


# ── Embeds ────────────────────────────────────────────────────────────────────

def embed_principal(alvo: discord.Member | discord.User, guild: discord.Guild | None = None) -> discord.Embed:
    embed = discord.Embed(color=_cor(alvo))

    # Cabeçalho: ícone de pessoa + nome (display) + nome de usuário entre parênteses
    embed.set_author(
        name=f"✦ {alvo.display_name} ({alvo.name})",
        icon_url=alvo.display_avatar.url
    )
    embed.set_thumbnail(url=alvo.display_avatar.url)

    # Menção
    embed.add_field(
        name="@ Menção",
        value=alvo.mention,
        inline=False
    )

    # Tag + ID na mesma linha (inline=True para ficarem lado a lado)
    embed.add_field(name="🏷 Tag",  value=f"`{alvo.name}`", inline=True)
    embed.add_field(name="🪪 ID",   value=f"`{alvo.id}`",   inline=True)
    # Campo vazio para forçar quebra de linha após os dois inline
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # Insígnias
    embed.add_field(
        name="✨ Insígnias",
        value=get_badges(alvo),
        inline=False
    )

    # Conta criada
    embed.add_field(
        name="🕰️ Conta criada em",
        value=f"{formatar_dt(alvo.created_at)}\n*({tempo_relativo(alvo.created_at)})*",
        inline=False
    )

    if isinstance(alvo, discord.Member):
        # Entrou no servidor
        if alvo.joined_at:
            embed.add_field(
                name="📆 Entrou no servidor em",
                value=f"{formatar_dt(alvo.joined_at)}\n*({tempo_relativo(alvo.joined_at)})*",
                inline=False
            )

        # Nitro / Boost resumido
        if alvo.premium_since:
            embed.add_field(
                name="🚀 Impulsionando desde",
                value=f"{formatar_dt(alvo.premium_since)}\n*({tempo_relativo(alvo.premium_since)})*",
                inline=False
            )

        # Cargos
        cargos = [r for r in alvo.roles if r.name != "@everyone"]
        cargos.reverse()
        if cargos:
            lista = " ".join(r.mention for r in cargos[:10])
            if len(cargos) > 10:
                lista += f" *+{len(cargos) - 10} mais*"
            embed.add_field(name=f"🎭 Cargos [{len(cargos)}]", value=lista, inline=False)
    else:
        embed.add_field(
            name="ℹ️ Fora do servidor",
            value="Este usuário não está neste servidor.",
            inline=False
        )

    # Footer igual à referência: "Comando executado por X • Hoje às HH:MM"
    bot_name = guild.me.display_name if guild else "Bot"
    agora = datetime.now(timezone.utc)
    embed.set_footer(text=f"Comando executado por {bot_name} • Hoje às {agora.hour:02d}:{agora.minute:02d}")
    embed.timestamp = discord.utils.utcnow()
    return embed


def embed_avatar(alvo: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(title=f"🖼️ Avatar de {alvo.display_name}", color=_cor(alvo))
    guild_avatar = getattr(alvo, 'guild_avatar', None)

    if guild_avatar:
        embed.set_image(url=guild_avatar.url)
        embed.add_field(
            name="Avatar do servidor",
            value=f"[PNG]({guild_avatar.with_format('png').url}) • [JPG]({guild_avatar.with_format('jpg').url}) • [WEBP]({guild_avatar.with_format('webp').url})",
            inline=False
        )
        embed.set_thumbnail(url=alvo.display_avatar.url)
        embed.add_field(
            name="Avatar global",
            value=f"[PNG]({alvo.display_avatar.with_format('png').url}) • [JPG]({alvo.display_avatar.with_format('jpg').url}) • [WEBP]({alvo.display_avatar.with_format('webp').url})",
            inline=False
        )
    else:
        embed.set_image(url=alvo.display_avatar.url)
        embed.add_field(
            name="Links",
            value=f"[PNG]({alvo.display_avatar.with_format('png').url}) • [JPG]({alvo.display_avatar.with_format('jpg').url}) • [WEBP]({alvo.display_avatar.with_format('webp').url})",
            inline=False
        )

    embed.set_footer(text=f"ID: {alvo.id}")
    embed.timestamp = discord.utils.utcnow()
    return embed


def embed_banner(alvo: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(title=f"🎨 Banner de {alvo.display_name}", color=_cor(alvo))
    banner = getattr(alvo, 'banner', None)

    if banner:
        embed.set_image(url=banner.url)
        embed.add_field(
            name="Links",
            value=f"[PNG]({banner.with_format('png').url}) • [JPG]({banner.with_format('jpg').url}) • [WEBP]({banner.with_format('webp').url})",
            inline=False
        )
    else:
        accent = getattr(alvo, 'accent_color', None)
        if accent:
            embed.description = f"Este usuário não tem banner.\n**Cor de perfil:** `#{accent.value:06X}`"
            embed.color = accent
        else:
            embed.description = "Este usuário não possui banner."

    embed.set_footer(text=f"ID: {alvo.id}")
    embed.timestamp = discord.utils.utcnow()
    return embed


def embed_nitro(alvo: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(title=f"💎 Nitro & Boost — {alvo.display_name}", color=_cor(alvo))
    embed.set_thumbnail(url=alvo.display_avatar.url)

    flags = alvo.public_flags
    tem_nitro = (
        alvo.display_avatar.is_animated() or
        bool(getattr(alvo, 'guild_avatar', None)) or
        getattr(flags, 'early_supporter', False)
    )
    embed.add_field(
        name="💠 Nitro",
        value="✅ Provável (avatar animado ou insígnia detectada)" if tem_nitro else "❓ Não detectado",
        inline=False
    )

    if isinstance(alvo, discord.Member) and alvo.premium_since:
        embed.add_field(
            name="🚀 Impulsionando desde",
            value=f"{formatar_dt(alvo.premium_since)}\n*({tempo_relativo(alvo.premium_since)})*",
            inline=False
        )
        embed.add_field(
            name="🏅 Nível do servidor",
            value=f"Nível **{alvo.guild.premium_tier}** com **{alvo.guild.premium_subscription_count or 0}** impulsionamentos",
            inline=False
        )
    elif isinstance(alvo, discord.Member):
        embed.add_field(name="🚀 Boost", value="Este membro não está impulsionando o servidor.", inline=False)
    else:
        embed.add_field(name="🚀 Boost", value="Usuário fora do servidor — dados de boost indisponíveis.", inline=False)

    embed.set_footer(text=f"ID: {alvo.id}")
    embed.timestamp = discord.utils.utcnow()
    return embed


def embed_badges(alvo: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(title=f"✨ Insígnias de {alvo.display_name}", color=_cor(alvo))
    embed.set_thumbnail(url=alvo.display_avatar.url)

    flags = alvo.public_flags
    encontradas = [f"{emoji} **{nome}**" for attr, emoji, nome in BADGES if getattr(flags, attr, False)]
    embed.description = "\n".join(encontradas) if encontradas else "Este usuário não possui insígnias públicas."

    embed.set_footer(text=f"ID: {alvo.id}")
    embed.timestamp = discord.utils.utcnow()
    return embed


# ── View com Select Menu ──────────────────────────────────────────────────────

class UserInfoView(discord.ui.View):
    def __init__(self, alvo: discord.Member | discord.User, guild: discord.Guild | None):
        super().__init__(timeout=120)
        self.guild = guild
        self.add_item(UserInfoSelect(alvo))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class UserInfoSelect(discord.ui.Select):
    def __init__(self, alvo: discord.Member | discord.User):
        self.alvo = alvo
        nome_curto = alvo.display_name[:20]
        opcoes = [
            discord.SelectOption(label="Informações principais", description=f"Dados gerais de {nome_curto}",  emoji="🪪", value="principal"),
            discord.SelectOption(label="Avatar",                 description=f"Avatar de {nome_curto}",        emoji="🖼️", value="avatar"),
            discord.SelectOption(label="Banner",                 description=f"Banner de {nome_curto}",        emoji="🎨", value="banner"),
        ]
        super().__init__(placeholder="Mais informações...", options=opcoes, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        escolha = self.values[0]

        # Re-fetch para banner (precisa de dados completos da API)
        if escolha == "banner":
            try:
                self.alvo = await interaction.client.fetch_user(self.alvo.id)
            except Exception:
                pass

        guild = interaction.guild
        embeds_map = {
            "principal": lambda a: embed_principal(a, guild),
            "avatar":    embed_avatar,
            "banner":    embed_banner,
        }

        novo_embed = embeds_map[escolha](self.alvo)
        await interaction.response.edit_message(embed=novo_embed)


# ── Cog ───────────────────────────────────────────────────────────────────────

class UserInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("✅ UserInfoCog carregado!")

    @app_commands.command(name="userinfo", description="Exibe informações detalhadas de um usuário")
    @app_commands.describe(
        usuario="Mencione um membro do servidor",
        user_id="ID de qualquer usuário Discord (mesmo fora do servidor)"
    )
    async def userinfo(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member | None = None,
        user_id: str | None = None
    ):
        await interaction.response.defer()

        alvo: discord.Member | discord.User | None = None

        if usuario:
            alvo = usuario
        elif user_id:
            try:
                uid = int(user_id)
            except ValueError:
                await interaction.followup.send("❌ ID inválido. Use apenas números.", ephemeral=True)
                return

            # Tenta pegar como membro do servidor primeiro, senão busca globalmente
            alvo = interaction.guild.get_member(uid)
            if not alvo:
                try:
                    alvo = await self.bot.fetch_user(uid)
                except discord.NotFound:
                    await interaction.followup.send("❌ Nenhum usuário encontrado com esse ID.", ephemeral=True)
                    return
                except discord.HTTPException:
                    await interaction.followup.send("❌ Erro ao buscar usuário. Tente novamente.", ephemeral=True)
                    return
        else:
            # Padrão: próprio usuário
            alvo = interaction.guild.get_member(interaction.user.id) or interaction.user

        # Fetch completo para obter banner e accent_color
        try:
            user_completo = await self.bot.fetch_user(alvo.id)
            if isinstance(alvo, discord.Member):
                # Preserva dados de membro mas injeta banner/cor
                alvo.banner = getattr(user_completo, 'banner', None)
                alvo.accent_color = getattr(user_completo, 'accent_color', None)
            else:
                alvo = user_completo
        except Exception:
            pass

        embed = embed_principal(alvo, interaction.guild)
        view = UserInfoView(alvo, interaction.guild)

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(UserInfoCog(bot))