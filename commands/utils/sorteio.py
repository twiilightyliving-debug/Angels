import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import time
import motor.motor_asyncio
from typing import Optional
import os
from dotenv import load_dotenv
import asyncio
import re

# Carrega variáveis de ambiente
load_dotenv()

def parse_tempo(tempo_str: str) -> int:
    """
    Converte string de tempo para segundos
    Exemplos: 10s, 5m, 2h, 1d, 30s, 90m, 24h, 7d
    """
    tempo_str = tempo_str.lower().strip()
    
    # Regex para extrair número e unidade
    padrao = re.match(r"^(\d+)([smhd])$", tempo_str)
    if not padrao:
        raise ValueError("Formato inválido. Use: 10s, 5m, 2h, 1d")
    
    valor = int(padrao.group(1))
    unidade = padrao.group(2)
    
    # Converte para segundos
    conversores = {
        's': 1,           # segundos
        'm': 60,          # minutos
        'h': 3600,        # horas
        'd': 86400        # dias
    }
    
    segundos = valor * conversores[unidade]
    
    # Limites de segurança (máx 30 dias)
    if segundos > 2592000:  # 30 dias em segundos
        raise ValueError("Tempo máximo é 30 dias")
    
    return segundos

def formatar_tempo(segundos: int) -> str:
    """Formata segundos para formato legível"""
    if segundos < 60:
        return f"{segundos} segundos"
    elif segundos < 3600:
        minutos = segundos // 60
        return f"{minutos} minuto{'s' if minutos > 1 else ''}"
    elif segundos < 86400:
        horas = segundos // 3600
        minutos_rest = (segundos % 3600) // 60
        if minutos_rest == 0:
            return f"{horas} hora{'s' if horas > 1 else ''}"
        else:
            return f"{horas}h {minutos_rest}min"
    else:
        dias = segundos // 86400
        horas_rest = (segundos % 86400) // 3600
        if horas_rest == 0:
            return f"{dias} dia{'s' if dias > 1 else ''}"
        else:
            return f"{dias}d {horas_rest}h"

class SorteioCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Conexão MongoDB via .env
        mongo_uri = os.getenv('MONGO_URI')
        if not mongo_uri:
            raise ValueError("MONGO_URI não encontrada no arquivo .env")
        
        # Conecta ao MongoDB
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.db = self.mongo_client["miku_bot"]
        self.sorteios_coll = self.db["sorteios"]
        
        print("✅ Conectado ao MongoDB com sucesso!")
        
        # Inicia a task de verificação
        self.check_sorteios.start()

    def cog_unload(self):
        self.check_sorteios.cancel()
        self.mongo_client.close()

    @tasks.loop(seconds=10)
    async def check_sorteios(self):
        """Verifica sorteios expirados"""
        try:
            now = int(time.time())
            
            cursor = self.sorteios_coll.find({
                "status": "running",
                "end_timestamp": {"$lte": now}
            })
            
            async for doc in cursor:
                print(f"🔍 Sorteio expirado: {doc['_id']}")
                try:
                    await self.finalizar_sorteio(doc)
                except Exception as e:
                    print(f"❌ Erro ao finalizar sorteio {doc['_id']}: {e}")
        except Exception as e:
            print(f"❌ Erro na task: {e}")

    async def finalizar_sorteio(self, doc):
        """Finaliza um sorteio específico"""
        try:
            guild = self.bot.get_guild(doc["guild_id"])
            if not guild:
                await self._mark_cancelled(doc, "guild not found")
                return

            channel = guild.get_channel(doc["channel_id"])
            if not channel:
                await self._mark_cancelled(doc, "channel not found")
                return

            try:
                msg = await channel.fetch_message(doc["message_id"])
            except discord.NotFound:
                await self._mark_cancelled(doc, "message deleted")
                return
            except discord.Forbidden:
                await self._mark_cancelled(doc, "no permission")
                return
            except Exception as e:
                await self._mark_cancelled(doc, f"fetch error: {str(e)[:50]}")
                return

            # Coleta participantes
            participantes = []
            if msg.reactions:
                for reaction in msg.reactions:
                    if str(reaction.emoji) == "🎟️":
                        async for user in reaction.users():
                            if not user.bot:
                                member = guild.get_member(user.id)
                                if member:
                                    participantes.append(member)
                        break

            # Prepara embed do resultado
            if not participantes:
                embed_resultado = discord.Embed(
                    title="😢 Sorteio Sem Participantes",
                    description=f"O sorteio **{doc['prize']}** terminou sem participantes.",
                    color=discord.Color.red()
                )
                vencedores = []
            else:
                qtd = min(doc.get("winners_count", 1), len(participantes))
                vencedores = random.sample(participantes, qtd)
                
                mencoes = ", ".join(v.mention for v in vencedores)
                embed_resultado = discord.Embed(
                    title="🎉 SORTEIO FINALIZADO!",
                    description=f"**Prêmio:** {doc['prize']}\n**Vencedor(es):** {mencoes}",
                    color=discord.Color.green()
                )

            if doc.get("requirements"):
                embed_resultado.add_field(
                    name="📋 Requisitos",
                    value=doc["requirements"],
                    inline=False
                )

            embed_resultado.set_footer(text=f"Sorteio ID: {doc['_id'][:8]}")
            embed_resultado.timestamp = discord.utils.utcnow()
            
            await channel.send(embed=embed_resultado)

            # Atualiza status do sorteio
            update_data = {
                "status": "finished",
                "finished_at": int(time.time()),
                "participants_count": len(participantes)
            }
            
            if vencedores:
                update_data["winners"] = [v.id for v in vencedores]
                # Salva lista completa de participantes para uso no re-sortear
                update_data["participants"] = [p.id for p in participantes]
            
            await self.sorteios_coll.update_one(
                {"_id": doc["_id"]},
                {"$set": update_data}
            )
            
            print(f"✅ Sorteio {doc['_id']} finalizado")

        except Exception as e:
            print(f"❌ Erro crítico: {e}")
            await self._mark_cancelled(doc, f"critical error: {str(e)[:50]}")

    async def _mark_cancelled(self, doc, note):
        """Marca um sorteio como cancelado"""
        try:
            await self.sorteios_coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "status": "cancelled", 
                    "cancelled_note": note, 
                    "cancelled_at": int(time.time())
                }}
            )
            print(f"📝 Sorteio {doc['_id']} cancelado: {note}")
        except Exception as e:
            print(f"❌ Erro ao marcar cancelamento: {e}")

    @app_commands.command(name="sorteio", description="Cria um sorteio persistente")
    @app_commands.describe(
        premio="O que será sorteado",
        tempo="Duração (ex: 30s, 5m, 2h, 1d, 30m, 24h, 7d)",
        vencedores="Quantos vencedores (padrão 1, máx 20)",
        requisitos="Descrição dos requisitos para participar"
    )
    async def criar_sorteio(
        self,
        interaction: discord.Interaction,
        premio: str,
        tempo: str,
        vencedores: app_commands.Range[int, 1, 20] = 1,
        requisitos: Optional[str] = None
    ):
        # Verifica permissões
        if not interaction.guild.me.guild_permissions.add_reactions:
            await interaction.response.send_message(
                "❌ Preciso da permissão `Adicionar Reações`!",
                ephemeral=True
            )
            return

        try:
            duracao_segundos = parse_tempo(tempo)
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ {str(e)}\nUse formatos como: `10s`, `5m`, `2h`, `1d`",
                ephemeral=True
            )
            return

        agora = int(time.time())
        end_time = agora + duracao_segundos
        tempo_formatado = formatar_tempo(duracao_segundos)
        
        print(f"📅 Sorteio: {premio} - Duração: {tempo_formatado} ({duracao_segundos}s)")

        embed = discord.Embed(
            title="🎉 SORTEIO ATIVO!",
            description=f"**Prêmio:** {premio}\n**Vencedores:** {vencedores}\n\nReaja com 🎟️ para participar!\n\n**Termina:** <t:{end_time}:R>",
            color=discord.Color.gold()
        )

        if requisitos:
            embed.add_field(
                name="📋 Requisitos",
                value=requisitos,
                inline=False
            )

        embed.set_footer(text=f"Iniciado por {interaction.user.name} • Duração: {tempo_formatado}")
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message("🔄 Criando sorteio...", ephemeral=True)
        
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("🎟️")

        doc = {
            "_id": str(msg.id),
            "guild_id": interaction.guild_id,
            "channel_id": interaction.channel_id,
            "message_id": msg.id,
            "prize": premio,
            "winners_count": vencedores,
            "end_timestamp": end_time,
            "duration_seconds": duracao_segundos,
            "duration_str": tempo,
            "created_by": interaction.user.id,
            "created_at": agora,
            "requirements": requisitos,
            "status": "running"
        }
        
        await self.sorteios_coll.insert_one(doc)
        
        await interaction.edit_original_response(
            content=f"✅ Sorteio criado! Duração: {tempo_formatado}. [Clique aqui]({msg.jump_url})"
        )
        
        print(f"✅ Sorteio salvo: {msg.id}")

    @app_commands.command(name="re_sortear", description="Sorteia um novo vencedor para um sorteio já finalizado")
    @app_commands.describe(
        message_id="ID da mensagem do sorteio (clique com botão direito → Copiar ID)",
        motivo="Motivo do re-sorteio (ex: vencedor não cumpriu requisitos)",
        excluir_anteriores="Excluir os vencedores anteriores da nova seleção? (padrão: Sim)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def re_sortear(
        self,
        interaction: discord.Interaction,
        message_id: str,
        motivo: Optional[str] = None,
        excluir_anteriores: bool = True
    ):
        await interaction.response.defer(ephemeral=True)

        # Busca o sorteio no banco
        doc = await self.sorteios_coll.find_one({
            "_id": message_id,
            "guild_id": interaction.guild_id
        })

        if not doc:
            await interaction.followup.send(
                "❌ Sorteio não encontrado. Verifique o ID da mensagem.\n"
                "💡 Para copiar o ID: clique com botão direito na mensagem do sorteio → **Copiar ID**",
                ephemeral=True
            )
            return

        if doc["status"] == "running":
            await interaction.followup.send(
                "⏳ Este sorteio ainda está em andamento! Aguarde ele terminar para re-sortear.",
                ephemeral=True
            )
            return

        if doc["status"] == "cancelled":
            await interaction.followup.send(
                "❌ Este sorteio foi cancelado e não pode ser re-sorteado.",
                ephemeral=True
            )
            return

        # Busca participantes: tenta da mensagem original primeiro, depois do banco
        guild = interaction.guild
        channel = guild.get_channel(doc["channel_id"])
        participantes_ids = []

        if channel:
            try:
                msg_original = await channel.fetch_message(doc["message_id"])
                for reaction in msg_original.reactions:
                    if str(reaction.emoji) == "🎟️":
                        async for user in reaction.users():
                            if not user.bot:
                                participantes_ids.append(user.id)
                        break
            except (discord.NotFound, discord.Forbidden):
                # Mensagem deletada — usa lista salva no banco
                participantes_ids = doc.get("participants", [])
        else:
            participantes_ids = doc.get("participants", [])

        if not participantes_ids:
            await interaction.followup.send(
                "😢 Não foi possível encontrar participantes para este sorteio.",
                ephemeral=True
            )
            return

        # Filtra vencedores anteriores se solicitado
        vencedores_anteriores_ids = doc.get("winners", [])
        candidatos_ids = participantes_ids

        if excluir_anteriores and vencedores_anteriores_ids:
            candidatos_ids = [uid for uid in participantes_ids if uid not in vencedores_anteriores_ids]

        if not candidatos_ids:
            await interaction.followup.send(
                "😢 Não há candidatos elegíveis após excluir os vencedores anteriores.\n"
                "Use `excluir_anteriores: False` para incluí-los.",
                ephemeral=True
            )
            return

        # Resolve os membros
        candidatos = []
        for uid in candidatos_ids:
            member = guild.get_member(uid)
            if member:
                candidatos.append(member)

        if not candidatos:
            await interaction.followup.send(
                "😢 Nenhum candidato elegível ainda está no servidor.",
                ephemeral=True
            )
            return

        # Sorteia novo(s) vencedor(es)
        qtd = min(doc.get("winners_count", 1), len(candidatos))
        novos_vencedores = random.sample(candidatos, qtd)
        mencoes = ", ".join(v.mention for v in novos_vencedores)

        # Monta embed do resultado
        motivo_texto = f"\n**Motivo:** {motivo}" if motivo else ""
        excluidos_texto = " (anteriores excluídos)" if excluir_anteriores and vencedores_anteriores_ids else ""

        embed_resultado = discord.Embed(
            title="🔄 RE-SORTEIO REALIZADO!",
            description=(
                f"**Prêmio:** {doc['prize']}\n"
                f"**Novo(s) Vencedor(es):** {mencoes}"
                f"{motivo_texto}"
            ),
            color=0x0a0a0a
        )

        if doc.get("requirements"):
            embed_resultado.add_field(
                name="📋 Requisitos",
                value=doc["requirements"],
                inline=False
            )

        embed_resultado.add_field(
            name="📊 Informações",
            value=(
                f"👥 Candidatos elegíveis: {len(candidatos)}{excluidos_texto}\n"
                f"🎟️ Total de participantes: {len(participantes_ids)}\n"
                f"🔁 Re-sorteado por: {interaction.user.mention}"
            ),
            inline=False
        )

        # Link para mensagem original, se ainda existir
        link_original = f"https://discord.com/channels/{doc['guild_id']}/{doc['channel_id']}/{doc['message_id']}"
        embed_resultado.add_field(
            name="🔗 Sorteio Original",
            value=f"[Clique para ver]({link_original})",
            inline=False
        )

        embed_resultado.set_footer(text=f"Sorteio ID: {doc['_id'][:8]}")
        embed_resultado.timestamp = discord.utils.utcnow()

        # Envia resultado no canal do sorteio original (ou canal atual como fallback)
        canal_destino = channel if channel else interaction.channel
        await canal_destino.send(embed=embed_resultado)

        # Atualiza o banco com histórico de re-sorteios
        historico_entry = {
            "novos_vencedores": [v.id for v in novos_vencedores],
            "resorteado_por": interaction.user.id,
            "motivo": motivo,
            "excluiu_anteriores": excluir_anteriores,
            "timestamp": int(time.time())
        }

        await self.sorteios_coll.update_one(
            {"_id": message_id},
            {
                "$set": {"winners": [v.id for v in novos_vencedores]},
                "$push": {"historico_resorteios": historico_entry}
            }
        )

        await interaction.followup.send(
            f"✅ Re-sorteio realizado com sucesso! Novo(s) vencedor(es): {mencoes}",
            ephemeral=True
        )

        print(f"🔄 Re-sorteio do sorteio {message_id} por {interaction.user} — Vencedores: {[v.id for v in novos_vencedores]}")

    @re_sortear.error
    async def re_sortear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa da permissão **Gerenciar Servidor** para usar este comando.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Erro inesperado: {str(error)}",
                ephemeral=True
            )

    @app_commands.command(name="sorteios", description="Lista todos os sorteios ativos")
    async def listar_sorteios(self, interaction: discord.Interaction):
        """Lista todos os sorteios ativos"""
        now = int(time.time())
        
        sorteios = await self.sorteios_coll.find({
            "guild_id": interaction.guild_id,
            "status": "running",
            "end_timestamp": {"$gt": now}
        }).to_list(length=None)

        if not sorteios:
            await interaction.response.send_message(
                "📭 Não há sorteios ativos.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 Sorteios Ativos",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        for sorteio in sorteios:
            segundos_restantes = sorteio["end_timestamp"] - now
            tempo_str = formatar_tempo(segundos_restantes)
            
            embed.add_field(
                name=f"🎁 {sorteio['prize']}",
                value=f"🏆 {sorteio['winners_count']} vencedor(es)\n⏱️ Termina em {tempo_str}\n🔗 [Ver sorteio](https://discord.com/channels/{sorteio['guild_id']}/{sorteio['channel_id']}/{sorteio['message_id']})",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="exemplos_tempo", description="Mostra exemplos de formatos de tempo")
    async def exemplos_tempo(self, interaction: discord.Interaction):
        """Mostra exemplos de como usar o parâmetro tempo"""
        exemplos = discord.Embed(
            title="⏰ Formatos de Tempo",
            description="Use esses formatos no comando `/sorteio`",
            color=discord.Color.blue()
        )
        
        exemplos.add_field(
            name="Segundos",
            value="`10s` - 10 segundos\n`30s` - 30 segundos\n`45s` - 45 segundos",
            inline=True
        )
        
        exemplos.add_field(
            name="Minutos",
            value="`1m` - 1 minuto\n`5m` - 5 minutos\n`30m` - 30 minutos\n`45m` - 45 minutos",
            inline=True
        )
        
        exemplos.add_field(
            name="Horas",
            value="`1h` - 1 hora\n`2h` - 2 horas\n`6h` - 6 horas\n`12h` - 12 horas",
            inline=True
        )
        
        exemplos.add_field(
            name="Dias",
            value="`1d` - 1 dia\n`3d` - 3 dias\n`7d` - 7 dias\n`30d` - 30 dias",
            inline=True
        )
        
        exemplos.add_field(
            name="Exemplos combinados",
            value="`90m` - 90 minutos\n`48h` - 48 horas\n`720h` - 30 dias",
            inline=False
        )
        
        exemplos.set_footer(text="Máximo: 30 dias")
        
        await interaction.response.send_message(embed=exemplos, ephemeral=True)

    @check_sorteios.before_loop
    async def before_check_sorteios(self):
        """Aguarda o bot ficar pronto"""
        await self.bot.wait_until_ready()
        print("🔄 Task de verificação iniciada - verificando a cada 10 segundos")

async def setup(bot: commands.Bot):
    await bot.add_cog(SorteioCog(bot))