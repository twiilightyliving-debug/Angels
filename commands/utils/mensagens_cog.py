import discord
from discord import app_commands
from discord.ext import commands
import motor.motor_asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

load_dotenv()

def get_periodos() -> dict:
    """Retorna os timestamps de início de cada período"""
    agora = datetime.now(timezone.utc)

    inicio_hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)

    # Início da semana (segunda-feira)
    inicio_semana = inicio_hoje - timedelta(days=agora.weekday())

    # Início do mês
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return {
        "hoje": int(inicio_hoje.timestamp()),
        "semana": int(inicio_semana.timestamp()),
        "mes": int(inicio_mes.timestamp()),
    }


class MensagensCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        mongo_uri = os.getenv('MONGO_URI')
        if not mongo_uri:
            raise ValueError("MONGO_URI não encontrada no arquivo .env")

        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.db = self.mongo_client["miku_bot"]
        self.msgs_coll = self.db["mensagens"]

        print("✅ MensagensCog conectado ao MongoDB!")

    def cog_unload(self):
        self.mongo_client.close()

    # ── Listener: registra cada mensagem ──────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Registra mensagem no banco ao ser enviada"""
        # Ignora bots e DMs
        if message.author.bot or not message.guild:
            return

        agora = int(message.created_at.timestamp())

        await self.msgs_coll.insert_one({
            "user_id":    message.author.id,
            "guild_id":   message.guild.id,
            "channel_id": message.channel.id,
            "timestamp":  agora
        })

    # ── Helpers de contagem ───────────────────────────────────────────────────

    async def _contar(self, user_id: int, guild_id: int, desde: int | None = None) -> int:
        filtro = {"user_id": user_id, "guild_id": guild_id}
        if desde is not None:
            filtro["timestamp"] = {"$gte": desde}
        return await self.msgs_coll.count_documents(filtro)

    # ── Comando /mensagens ────────────────────────────────────────────────────

    @app_commands.command(name="mensagens", description="Mostra a contagem de mensagens de um usuário")
    @app_commands.describe(usuario="Usuário que deseja consultar (padrão: você mesmo)")
    async def mensagens(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member | None = None
    ):
        await interaction.response.defer()

        alvo = usuario or interaction.user
        periodos = get_periodos()

        hoje  = await self._contar(alvo.id, interaction.guild_id, periodos["hoje"])
        semana = await self._contar(alvo.id, interaction.guild_id, periodos["semana"])
        mes   = await self._contar(alvo.id, interaction.guild_id, periodos["mes"])
        total = await self._contar(alvo.id, interaction.guild_id)

        embed = discord.Embed(
            title=f"✉️ Contagem de mensagens de {alvo.display_name}",
            color=0x040505
        )

        embed.add_field(
            name="• Mensagens enviadas no servidor:",
            value=(
                "\u00a0\u00a0∘ Hoje: **" + f"{hoje:,}" + "**\n"
                "\u00a0\u00a0∘ Essa Semana: **" + f"{semana:,}" + "**\n"
                "\u00a0\u00a0∘ Esse mês: **" + f"{mes:,}" + "**\n"
                "\u00a0\u00a0∘ Total: **" + f"{total:,}" + "**"
            ),
            inline=False
        )

        embed.set_thumbnail(url=alvo.display_avatar.url)
        embed.set_footer(text="🎖️ Utilize /rank_msgs para ver o top 10 deste servidor.")
        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed)

    # ── Comando /rank ─────────────────────────────────────────────────────────

    @app_commands.command(name="rank_msgs", description="Mostra o top 10 de mensagens do servidor")
    @app_commands.describe(periodo="Período para o ranking (padrão: total)")
    @app_commands.choices(periodo=[
        app_commands.Choice(name="Hoje",       value="hoje"),
        app_commands.Choice(name="Essa semana", value="semana"),
        app_commands.Choice(name="Esse mês",   value="mes"),
        app_commands.Choice(name="Total",      value="total"),
    ])
    async def rank_msgs(
        self,
        interaction: discord.Interaction,
        periodo: app_commands.Choice[str] | None = None
    ):
        await interaction.response.defer()

        periodo_valor = periodo.value if periodo else "total"
        periodos = get_periodos()

        # Monta o filtro de tempo
        match_stage: dict = {"guild_id": interaction.guild_id}
        if periodo_valor != "total":
            match_stage["timestamp"] = {"$gte": periodos[periodo_valor]}

        # Agrega top 10
        pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]

        cursor = self.msgs_coll.aggregate(pipeline)
        resultados = await cursor.to_list(length=10)

        if not resultados:
            await interaction.followup.send("📭 Nenhuma mensagem registrada ainda.", ephemeral=True)
            return

        # Nomes dos períodos para o título
        nomes_periodo = {
            "hoje": "Hoje",
            "semana": "Essa Semana",
            "mes": "Esse Mês",
            "total": "Total"
        }

        medalhas = ["🥇", "🥈", "🥉"]
        linhas = []

        for i, entry in enumerate(resultados):
            member = interaction.guild.get_member(entry["_id"])
            nome = member.display_name if member else f"Usuário {entry['_id']}"
            icone = medalhas[i] if i < 3 else f"`#{i+1}`"
            linhas.append(f"{icone} **{nome}** — {entry['count']:,} mensagens")

        embed = discord.Embed(
            title=f"🏆 Top 10 — {nomes_periodo[periodo_valor]}",
            description="\n".join(linhas),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{interaction.guild.name}")
        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MensagensCog(bot))