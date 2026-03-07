import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, Button, View, Modal, TextInput
import datetime
import math

# ==================== MODAIS PARA CONFIGURAÇÃO ====================

class ConfigTitleModal(Modal, title="Editar Título do Level Up"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: str, original_interaction: discord.Interaction):
        # Inicializa o Modal primeiro
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        # Depois adiciona o TextInput
        self.titulo = TextInput(
            label="Título da mensagem",
            placeholder="Ex: 🎉 Level Up!",
            default=current_value,
            required=True,
            max_length=100
        )
        self.add_item(self.titulo)

    async def on_submit(self, interaction: discord.Interaction):
        config = await self.cog.get_guild_config(self.guild_id)
        config["levelup_title"] = self.titulo.value
        await self.cog.save_guild_config(self.guild_id, config)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelEmbedView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigDescModal(Modal, title="Editar Descrição do Level Up"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: str, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        self.descricao = TextInput(
            label="Descrição",
            placeholder="Use {user} para mencionar e {level} para o nível",
            default=current_value,
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.descricao)

    async def on_submit(self, interaction: discord.Interaction):
        config = await self.cog.get_guild_config(self.guild_id)
        config["levelup_description"] = self.descricao.value
        await self.cog.save_guild_config(self.guild_id, config)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelEmbedView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigColorModal(Modal, title="Editar Cor do Level Up"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: str, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        self.cor = TextInput(
            label="Cor em hexadecimal",
            placeholder="Ex: #FF0000 para vermelho",
            default=current_value,
            required=True,
            max_length=7
        )
        self.add_item(self.cor)

    async def on_submit(self, interaction: discord.Interaction):
        cor = self.cor.value
        if not cor.startswith("#") or len(cor) not in [4, 7]:
            await interaction.response.send_message("❌ Cor inválida! Use formato #RRGGBB", ephemeral=True)
            return
        
        try:
            discord.Color.from_str(cor)
        except:
            await interaction.response.send_message("❌ Cor inválida!", ephemeral=True)
            return
        
        config = await self.cog.get_guild_config(self.guild_id)
        config["levelup_color"] = cor
        await self.cog.save_guild_config(self.guild_id, config)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelEmbedView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigImageModal(Modal, title="Editar Imagem do Level Up"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: str, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        self.imagem = TextInput(
            label="URL da imagem (deixe vazio para remover)",
            placeholder="https://exemplo.com/imagem.png",
            default=current_value,
            required=False,
            max_length=200
        )
        self.add_item(self.imagem)

    async def on_submit(self, interaction: discord.Interaction):
        config = await self.cog.get_guild_config(self.guild_id)
        config["levelup_image"] = self.imagem.value if self.imagem.value else None
        await self.cog.save_guild_config(self.guild_id, config)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelEmbedView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigChannelModal(Modal, title="Configurar Canal de Level Up"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: int = None, original_interaction: discord.Interaction = None):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        canal_atual = str(current_value) if current_value else "0"
        
        self.canal = TextInput(
            label="ID do Canal (0 para remover)",
            placeholder="Digite o ID do canal",
            default=canal_atual,
            required=True,
            max_length=20
        )
        self.add_item(self.canal)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            canal_id = int(self.canal.value)
        except ValueError:
            await interaction.response.send_message("❌ ID inválido!", ephemeral=True)
            return
        
        config = await self.cog.get_guild_config(self.guild_id)
        
        if canal_id == 0:
            config["levelup_channel"] = None
            await self.cog.save_guild_config(self.guild_id, config)
            await interaction.response.send_message("✅ Canal removido!", ephemeral=True)
            embed = self.cog.create_config_embed(config, interaction.guild)
            view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
            await interaction.edit_original_response(embed=embed, view=view)
            return
        
        channel = interaction.guild.get_channel(canal_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("❌ Canal não encontrado ou não é de texto!", ephemeral=True)
            return
        
        config["levelup_channel"] = canal_id
        await self.cog.save_guild_config(self.guild_id, config)
        
        await interaction.response.send_message(f"✅ Canal configurado: {channel.mention}", ephemeral=True)
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
        await interaction.edit_original_response(embed=embed, view=view)


class ConfigXPPerMsgModal(Modal, title="Configurar XP por Mensagem"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: int, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        self.xp = TextInput(
            label="XP por mensagem",
            placeholder="Digite um número",
            default=str(current_value),
            required=True,
            max_length=5
        )
        self.add_item(self.xp)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp = int(self.xp.value)
            if xp < 1 or xp > 1000:
                await interaction.response.send_message("❌ XP deve estar entre 1 e 1000!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Valor inválido!", ephemeral=True)
            return
        
        config = await self.cog.get_guild_config(self.guild_id)
        config["xp_per_msg"] = xp
        await self.cog.save_guild_config(self.guild_id, config)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigCooldownModal(Modal, title="Configurar Cooldown"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: int, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        self.cooldown = TextInput(
            label="Cooldown em segundos",
            placeholder="Digite um número",
            default=str(current_value),
            required=True,
            max_length=5
        )
        self.add_item(self.cooldown)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cooldown = int(self.cooldown.value)
            if cooldown < 1 or cooldown > 3600:
                await interaction.response.send_message("❌ Cooldown deve estar entre 1 e 3600 segundos!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Valor inválido!", ephemeral=True)
            return
        
        config = await self.cog.get_guild_config(self.guild_id)
        config["xp_cooldown"] = cooldown
        await self.cog.save_guild_config(self.guild_id, config)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigMultiplierModal(Modal, title="Configurar Multiplicador"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: float, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        self.mult = TextInput(
            label="Multiplicador de XP",
            placeholder="Ex: 1.5, 2.0, 0.5",
            default=str(current_value),
            required=True,
            max_length=5
        )
        self.add_item(self.mult)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            mult = float(self.mult.value)
            if mult < 0.1 or mult > 10.0:
                await interaction.response.send_message("❌ Multiplicador deve estar entre 0.1 e 10.0!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Valor inválido!", ephemeral=True)
            return
        
        config = await self.cog.get_guild_config(self.guild_id)
        config["xp_multiplier"] = mult
        await self.cog.save_guild_config(self.guild_id, config)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigCurveModal(Modal, title="Configurar Curva de Níveis"):
    def __init__(self, cog: 'Levels', guild_id: int, current_value: float, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        self.curve = TextInput(
            label="Curva de crescimento",
            placeholder="Ex: 1.5 (padrão), 2.0 (mais difícil)",
            default=str(current_value),
            required=True,
            max_length=5
        )
        self.add_item(self.curve)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            curve = float(self.curve.value)
            if curve < 1.0 or curve > 3.0:
                await interaction.response.send_message("❌ Curva deve estar entre 1.0 e 3.0!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Valor inválido!", ephemeral=True)
            return
        
        config = await self.cog.get_guild_config(self.guild_id)
        config["xp_curve"] = curve
        await self.cog.save_guild_config(self.guild_id, config)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== MODAIS PARA RECOMPENSAS ====================

class AddRewardModal(Modal, title="Adicionar Recompensa"):
    def __init__(self, cog: 'Levels', guild_id: int, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction

        self.nivel = TextInput(
            label="Nível",
            placeholder="Digite o número do nível",
            required=True,
            max_length=5
        )
        self.add_item(self.nivel)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            nivel = int(self.nivel.value)
            if nivel < 1:
                await interaction.response.send_message("❌ Nível deve ser maior que 0.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Digite um número válido.", ephemeral=True)
            return

        # Criar view para selecionar cargo
        view = View(timeout=60)
        
        class RoleSelect(discord.ui.RoleSelect):
            def __init__(self, cog, guild_id, nivel, original_interaction):
                super().__init__(placeholder="Selecione o cargo")
                self.cog = cog
                self.guild_id = guild_id
                self.nivel = nivel
                self.original_interaction = original_interaction

            async def callback(self, inter: discord.Interaction):
                role = self.values[0]
                
                config = await self.cog.get_guild_config(self.guild_id)
                rewards = config.get("level_rewards", [])
                rewards = [r for r in rewards if r["level"] != self.nivel]
                rewards.append({"level": self.nivel, "role_id": str(role.id)})
                config["level_rewards"] = rewards
                await self.cog.save_guild_config(self.guild_id, config)
                
                await inter.response.send_message(f"✅ Recompensa: Nível **{self.nivel}** → {role.mention}", ephemeral=True)
                
                # Atualizar mensagem principal
                config = await self.cog.get_guild_config(self.guild_id)
                embed = self.cog.create_config_embed(config, inter.guild)
                view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
                await self.original_interaction.edit_original_response(embed=embed, view=view)
        
        select = RoleSelect(self.cog, self.guild_id, nivel, self.original_interaction)
        view.add_item(select)
        
        await interaction.response.send_message(
            f"Nível **{nivel}** selecionado. Escolha o cargo:",
            view=view,
            ephemeral=True
        )


class RemoveRewardSelect(Select):
    def __init__(self, cog: 'Levels', guild_id: int, rewards: list, original_interaction: discord.Interaction):
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction
        
        options = []
        for r in sorted(rewards, key=lambda x: x["level"]):
            options.append(discord.SelectOption(
                label=f"Nível {r['level']}",
                value=str(r["level"]),
                description="Clique para remover esta recompensa"
            ))
        
        super().__init__(
            placeholder="Selecione a recompensa para remover",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        level = int(self.values[0])
        config = await self.cog.get_guild_config(self.guild_id)
        config["level_rewards"] = [r for r in config.get("level_rewards", []) if r["level"] != level]
        await self.cog.save_guild_config(self.guild_id, config)
        
        await interaction.response.send_message(f"✅ Recompensa do nível {level} removida.", ephemeral=True)
        
        # Atualizar mensagem principal
        config = await self.cog.get_guild_config(self.guild_id)
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
        await self.original_interaction.edit_original_response(embed=embed, view=view)


# ==================== MODAIS PARA XP ====================

class AddXPModal(Modal, title="Adicionar XP"):
    def __init__(self, cog: 'Levels', guild_id: int, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction

        self.usuario = TextInput(
            label="ID do Usuário",
            placeholder="Digite o ID do usuário",
            required=True,
            max_length=20
        )
        self.add_item(self.usuario)
        
        self.quantidade = TextInput(
            label="Quantidade de XP",
            placeholder="Digite a quantidade",
            required=True,
            max_length=10
        )
        self.add_item(self.quantidade)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.usuario.value)
            xp = int(self.quantidade.value)
            if xp <= 0:
                await interaction.response.send_message("❌ XP deve ser maior que 0!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Valores inválidos!", ephemeral=True)
            return
        
        result = await self.cog.add_xp(self.guild_id, user_id, xp)
        await interaction.response.send_message(result, ephemeral=True)


class RemoveXPModal(Modal, title="Remover XP"):
    def __init__(self, cog: 'Levels', guild_id: int, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction

        self.usuario = TextInput(
            label="ID do Usuário",
            placeholder="Digite o ID do usuário",
            required=True,
            max_length=20
        )
        self.add_item(self.usuario)
        
        self.quantidade = TextInput(
            label="Quantidade de XP",
            placeholder="Digite a quantidade",
            required=True,
            max_length=10
        )
        self.add_item(self.quantidade)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.usuario.value)
            xp = int(self.quantidade.value)
            if xp <= 0:
                await interaction.response.send_message("❌ XP deve ser maior que 0!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Valores inválidos!", ephemeral=True)
            return
        
        result = await self.cog.remove_xp(self.guild_id, user_id, xp)
        await interaction.response.send_message(result, ephemeral=True)


class ResetUserXPModal(Modal, title="Resetar XP de Usuário"):
    def __init__(self, cog: 'Levels', guild_id: int, original_interaction: discord.Interaction):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction

        self.usuario = TextInput(
            label="ID do Usuário",
            placeholder="Digite o ID do usuário",
            required=True,
            max_length=20
        )
        self.add_item(self.usuario)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.usuario.value)
        except ValueError:
            await interaction.response.send_message("❌ ID inválido!", ephemeral=True)
            return
        
        result = await self.cog.reset_user_xp(self.guild_id, user_id)
        await interaction.response.send_message(result, ephemeral=True)


# ==================== VIEW PARA CONFIGURAÇÃO DO EMBED ====================

class LevelEmbedView(View):
    def __init__(self, cog: 'Levels', guild_id: int, original_interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    # LINHA 0 - Configurações Visuais (4 botões)
    @discord.ui.button(label="📝 Título", style=discord.ButtonStyle.primary, row=0)
    async def edit_title(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigTitleModal(self.cog, self.guild_id, config.get("levelup_title", "↑ Level Up!"), self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📄 Descrição", style=discord.ButtonStyle.primary, row=0)
    async def edit_desc(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigDescModal(self.cog, self.guild_id, config.get("levelup_description", ""), self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎨 Cor", style=discord.ButtonStyle.primary, row=0)
    async def edit_color(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigColorModal(self.cog, self.guild_id, config.get("levelup_color", "#1A1A1A"), self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🖼️ Imagem", style=discord.ButtonStyle.primary, row=0)
    async def edit_image(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigImageModal(self.cog, self.guild_id, config.get("levelup_image", ""), self.original_interaction)
        await interaction.response.send_modal(modal)

    # LINHA 1 - Utilitários (3 botões)
    @discord.ui.button(label="👀 Preview", style=discord.ButtonStyle.secondary, row=1)
    async def preview(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        embed = self.cog.create_preview_embed(config, interaction.guild)
        await interaction.response.send_message("**Preview da mensagem de level up:**", embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 Atualizar", style=discord.ButtonStyle.secondary, row=1)
    async def refresh(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        embed = self.cog.create_config_embed(config, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚙️ Voltar ao Principal", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelConfigView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== VIEW PRINCIPAL ====================

class LevelConfigView(View):
    def __init__(self, cog: 'Levels', guild_id: int, original_interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.original_interaction = original_interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    # LINHA 0 - Configurações Gerais (4 botões)
    @discord.ui.button(label="📢 Canal", style=discord.ButtonStyle.secondary, row=0)
    async def edit_channel(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigChannelModal(self.cog, self.guild_id, config.get("levelup_channel"), self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⚙️ XP/msg", style=discord.ButtonStyle.secondary, row=0)
    async def edit_xp_per_msg(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigXPPerMsgModal(self.cog, self.guild_id, config.get("xp_per_msg", 10), self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⏱️ Cooldown", style=discord.ButtonStyle.secondary, row=0)
    async def edit_cooldown(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigCooldownModal(self.cog, self.guild_id, config.get("xp_cooldown", 45), self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📊 Multiplicador", style=discord.ButtonStyle.secondary, row=0)
    async def edit_multiplier(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigMultiplierModal(self.cog, self.guild_id, config.get("xp_multiplier", 1.0), self.original_interaction)
        await interaction.response.send_modal(modal)

    # LINHA 1 - Configurações Avançadas (4 botões)
    @discord.ui.button(label="📈 Curva", style=discord.ButtonStyle.secondary, row=1)
    async def edit_curve(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        modal = ConfigCurveModal(self.cog, self.guild_id, config.get("xp_curve", 1.5), self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔌 Ativar/Desativar", style=discord.ButtonStyle.danger, row=1)
    async def toggle_system(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        config["xp_enabled"] = not config.get("xp_enabled", True)
        await self.cog.save_guild_config(self.guild_id, config)
        
        status = "✅ **ATIVADO**" if config["xp_enabled"] else "❌ **DESATIVADO**"
        await interaction.response.send_message(f"Sistema {status}!", ephemeral=True)
        
        embed = self.cog.create_config_embed(config, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="➕ Add Recompensa", style=discord.ButtonStyle.success, row=1)
    async def add_reward(self, interaction: discord.Interaction, button: Button):
        modal = AddRewardModal(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="➖ Remover Recompensa", style=discord.ButtonStyle.danger, row=1)
    async def remove_reward(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        rewards = config.get("level_rewards", [])
        
        if not rewards:
            await interaction.response.send_message("❌ Nenhuma recompensa configurada.", ephemeral=True)
            return
        
        view = View(timeout=60)
        view.add_item(RemoveRewardSelect(self.cog, self.guild_id, rewards, self.original_interaction))
        await interaction.response.send_message("Selecione a recompensa para remover:", view=view, ephemeral=True)

    # LINHA 2 - Gerenciamento de XP (4 botões)
    @discord.ui.button(label="⬆️ Add XP", style=discord.ButtonStyle.success, row=2)
    async def add_xp(self, interaction: discord.Interaction, button: Button):
        modal = AddXPModal(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⬇️ Remover XP", style=discord.ButtonStyle.danger, row=2)
    async def remove_xp(self, interaction: discord.Interaction, button: Button):
        modal = RemoveXPModal(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔄 Reset Usuário", style=discord.ButtonStyle.secondary, row=2)
    async def reset_user(self, interaction: discord.Interaction, button: Button):
        modal = ResetUserXPModal(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🌍 Reset Global", style=discord.ButtonStyle.danger, row=2)
    async def reset_global(self, interaction: discord.Interaction, button: Button):
        view = View(timeout=60)
        
        async def confirm(inter: discord.Interaction):
            result = self.cog.bot.db.levels.delete_many({"guild_id": self.guild_id})
            await inter.response.send_message(f"✅ **{result.deleted_count}** usuários resetados!", ephemeral=True)
            
            # Atualizar a mensagem original
            config = await self.cog.get_guild_config(self.guild_id)
            embed = self.cog.create_config_embed(config, interaction.guild)
            await self.original_interaction.edit_original_response(embed=embed, view=self)
        
        async def cancel(inter: discord.Interaction):
            await inter.response.edit_message(content="❌ Operação cancelada.", view=None)
        
        confirm_btn = Button(label="✅ Confirmar", style=discord.ButtonStyle.danger)
        confirm_btn.callback = confirm
        cancel_btn = Button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
        cancel_btn.callback = cancel
        
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        
        await interaction.response.send_message(
            "⚠️ **ATENÇÃO!** Isso resetará o XP de **TODOS** os usuários!\nTem certeza?",
            view=view,
            ephemeral=True
        )

    # LINHA 3 - Utilitários (3 botões)
    @discord.ui.button(label="🎨 Configurar Embed", style=discord.ButtonStyle.primary, row=3)
    async def config_embed(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        embed = self.cog.create_config_embed(config, interaction.guild)
        view = LevelEmbedView(self.cog, self.guild_id, self.original_interaction)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="👀 Preview", style=discord.ButtonStyle.secondary, row=3)
    async def preview(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        embed = self.cog.create_preview_embed(config, interaction.guild)
        await interaction.response.send_message("**Preview da mensagem de level up:**", embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 Atualizar", style=discord.ButtonStyle.secondary, row=3)
    async def refresh(self, interaction: discord.Interaction, button: Button):
        config = await self.cog.get_guild_config(self.guild_id)
        embed = self.cog.create_config_embed(config, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)


# ==================== COG PRINCIPAL ====================

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_guild_config(self, guild_id: int):
        if not hasattr(self.bot, 'db') or self.bot.db is None:
            # Configuração padrão se não houver banco de dados
            return {
                "guild_id": guild_id,
                "xp_per_msg": 10,
                "xp_cooldown": 45,
                "xp_multiplier": 1.0,
                "xp_curve": 1.5,
                "level_rewards": [],
                "xp_enabled": True,
                "levelup_channel": None,
                "levelup_title": "↑ Level Up!",
                "levelup_description": "Parabéns {user}! Você alcançou o **nível {level}**!",
                "levelup_color": "#1A1A1A",
                "levelup_image": None
            }
        
        config = self.bot.db.guild_configs.find_one({"guild_id": guild_id})
        if not config:
            config = {
                "guild_id": guild_id,
                "xp_per_msg": 10,
                "xp_cooldown": 45,
                "xp_multiplier": 1.0,
                "xp_curve": 1.5,
                "level_rewards": [],
                "xp_enabled": True,
                "levelup_channel": None,
                "levelup_title": "↑ Level Up!",
                "levelup_description": "Parabéns {user}! Você alcançou o **nível {level}**!",
                "levelup_color": "#1A1A1A",
                "levelup_image": None
            }
            self.bot.db.guild_configs.insert_one(config)
        return config

    async def save_guild_config(self, guild_id: int, config: dict):
        if hasattr(self.bot, 'db') and self.bot.db is not None:
            self.bot.db.guild_configs.replace_one({"guild_id": guild_id}, config, upsert=True)

    def calculate_level(self, xp: int, curve: float = 1.5):
        level = 0
        required = 0
        while True:
            next_required = required + int(100 * ((level + 1) ** curve))
            if next_required > xp:
                break
            level += 1
            required = next_required
        return level, required, next_required

    async def add_xp(self, guild_id: int, user_id: int, amount: int):
        if not hasattr(self.bot, 'db') or self.bot.db is None:
            return f"⚠️ Banco de dados não disponível."
        
        filter_ = {"guild_id": guild_id, "user_id": user_id}
        data = self.bot.db.levels.find_one(filter_)
        
        if not data:
            data = {"guild_id": guild_id, "user_id": user_id, "xp": 0, "level": 0, "messages": 0}
        
        data["xp"] += amount
        
        config = await self.get_guild_config(guild_id)
        curve = config.get("xp_curve", 1.5)
        
        new_level, _, _ = self.calculate_level(data["xp"], curve)
        data["level"] = new_level
        
        self.bot.db.levels.replace_one(filter_, data, upsert=True)
        return f"✅ +{amount} XP para <@{user_id}> (Total: {data['xp']} | Nível {data['level']})"

    async def remove_xp(self, guild_id: int, user_id: int, amount: int):
        if not hasattr(self.bot, 'db') or self.bot.db is None:
            return f"⚠️ Banco de dados não disponível."
        
        filter_ = {"guild_id": guild_id, "user_id": user_id}
        data = self.bot.db.levels.find_one(filter_)
        
        if not data:
            return "❌ Usuário sem dados."
        
        data["xp"] = max(0, data["xp"] - amount)
        
        config = await self.get_guild_config(guild_id)
        curve = config.get("xp_curve", 1.5)
        
        new_level, _, _ = self.calculate_level(data["xp"], curve)
        data["level"] = new_level
        
        self.bot.db.levels.replace_one(filter_, data, upsert=True)
        return f"✅ -{amount} XP de <@{user_id}> (Total: {data['xp']} | Nível {data['level']})"

    async def reset_user_xp(self, guild_id: int, user_id: int):
        if not hasattr(self.bot, 'db') or self.bot.db is None:
            return f"⚠️ Banco de dados não disponível."
        
        filter_ = {"guild_id": guild_id, "user_id": user_id}
        result = self.bot.db.levels.delete_one(filter_)
        
        if result.deleted_count > 0:
            return f"✅ XP de <@{user_id}> resetado!"
        return f"❌ Usuário sem dados."

    def create_config_embed(self, config: dict, guild: discord.Guild):
        """Cria embed de configuração com todas as opções atuais"""
        
        # Status do sistema
        status = "✅ ATIVADO" if config.get("xp_enabled", True) else "❌ DESATIVADO"
        canal = f"<#{config.get('levelup_channel')}>" if config.get('levelup_channel') else "`Não configurado`"
        
        # Configurações básicas
        texto = f"**Status do Sistema**\n"
        texto += f"• Sistema: {status}\n"
        texto += f"• Canal: {canal}\n"
        texto += f"• XP por mensagem: `{config.get('xp_per_msg', 10)}`\n"
        texto += f"• Cooldown: `{config.get('xp_cooldown', 45)}s`\n"
        texto += f"• Multiplicador: `{config.get('xp_multiplier', 1.0)}x`\n"
        texto += f"• Curva: `{config.get('xp_curve', 1.5)}`\n\n"
        
        # Configurações visuais
        texto += f"**Aparência da Mensagem**\n"
        texto += f"• Título: `{config.get('levelup_title', '↑ Level Up!')}`\n"
        texto += f"• Cor: `{config.get('levelup_color', '#1A1A1A')}`\n"
        texto += f"• Imagem: {'✅ Configurada' if config.get('levelup_image') else '❌ Não configurada'}\n\n"
        
        # Recompensas
        texto += f"**Recompensas por Nível**\n"
        rewards = config.get("level_rewards", [])
        if rewards:
            for r in sorted(rewards, key=lambda x: x["level"]):
                role = guild.get_role(int(r["role_id"]))
                role_name = role.mention if role else f"`ID: {r['role_id']}`"
                texto += f"• Nível **{r['level']}** → {role_name}\n"
        else:
            texto += "• Nenhuma recompensa configurada.\n"
        
        embed = discord.Embed(
            title="⚙️ Configuração do Sistema de Níveis",
            description=texto,
            color=discord.Color.from_str(config.get("levelup_color", "#1A1A1A"))
        )
        
        # Preview thumbnail
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text="Use /levelembed para configurar a aparência • /levelconfig para configurações")
        return embed

    def create_preview_embed(self, config: dict, guild: discord.Guild):
        """Cria embed de preview da mensagem de level up"""
        desc = config.get("levelup_description", "").replace("{user}", "@Usuário").replace("{level}", "10")
        
        embed = discord.Embed(
            title=config.get("levelup_title", "↑ Level Up!"),
            description=desc,
            color=discord.Color.from_str(config.get("levelup_color", "#1A1A1A"))
        )
        
        if config.get("levelup_image"):
            embed.set_image(url=config["levelup_image"])
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text="Preview da mensagem de level up")
        return embed

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        if not hasattr(self.bot, 'db') or self.bot.db is None:
            return

        config = await self.get_guild_config(message.guild.id)
        if not config.get("xp_enabled", True):
            return

        now = datetime.datetime.utcnow()
        filter_ = {"guild_id": message.guild.id, "user_id": message.author.id}
        data = self.bot.db.levels.find_one(filter_)

        if not data:
            data = {
                "guild_id": message.guild.id,
                "user_id": message.author.id,
                "xp": 0,
                "level": 0,
                "last_xp": now - datetime.timedelta(seconds=config["xp_cooldown"] + 1),
                "messages": 0
            }

        time_since = (now - data.get("last_xp", now - datetime.timedelta(days=1))).total_seconds()
        if time_since < config["xp_cooldown"]:
            return

        xp_gain = int(config["xp_per_msg"] * config["xp_multiplier"])
        data["xp"] += xp_gain
        data["last_xp"] = now
        data["messages"] = data.get("messages", 0) + 1

        old_level = data["level"]
        new_level, _, _ = self.calculate_level(data["xp"], config["xp_curve"])
        data["level"] = new_level

        self.bot.db.levels.replace_one(filter_, data, upsert=True)

        if new_level > old_level:
            desc = config.get("levelup_description", "").replace("{user}", message.author.mention).replace("{level}", str(new_level))
            
            embed = discord.Embed(
                title=config.get("levelup_title", "↑ Level Up!"),
                description=desc,
                color=discord.Color.from_str(config.get("levelup_color", "#1A1A1A"))
            )
            
            if config.get("levelup_image"):
                embed.set_image(url=config["levelup_image"])
            
            embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else None)
            
            channel_id = config.get("levelup_channel")
            if channel_id:
                channel = message.guild.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)
                else:
                    await message.channel.send(embed=embed)
            else:
                await message.channel.send(embed=embed)

            for r in config.get("level_rewards", []):
                if r["level"] == new_level:
                    role = message.guild.get_role(int(r["role_id"]))
                    if role and role not in message.author.roles:
                        try:
                            await message.author.add_roles(role)
                            reward_embed = discord.Embed(
                                title="🎁 Recompensa!",
                                description=f"{message.author.mention} ganhou {role.mention}",
                                color=0x00FF00
                            )
                            if channel_id and 'channel' in locals():
                                await channel.send(embed=reward_embed)
                            else:
                                await message.channel.send(embed=reward_embed)
                        except:
                            pass

    # ==================== COMANDOS ====================

    @app_commands.command(name="levelconfig", description="⚙️ Configurar sistema de níveis (XP, recompensas, etc)")
    @app_commands.default_permissions(administrator=True)
    async def levelconfig(self, interaction: discord.Interaction):
        """Configurações principais do sistema de níveis"""
        config = await self.get_guild_config(interaction.guild_id)
        embed = self.create_config_embed(config, interaction.guild)
        view = LevelConfigView(self, interaction.guild_id, interaction)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="levelembed", description="🎨 Configurar aparência da mensagem de level up")
    @app_commands.default_permissions(administrator=True)
    async def levelembed(self, interaction: discord.Interaction):
        """Configurações visuais da mensagem de level up"""
        config = await self.get_guild_config(interaction.guild_id)
        embed = self.create_config_embed(config, interaction.guild)
        view = LevelEmbedView(self, interaction.guild_id, interaction)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="level", description="📊 Ver seu nível e XP ou de outro usuário")
    async def level(self, interaction: discord.Interaction, usuario: discord.User = None):
        """Mostra o nível, XP e progresso de um usuário"""
        if usuario is None:
            usuario = interaction.user
        
        if not hasattr(self.bot, 'db') or self.bot.db is None:
            await interaction.response.send_message("⚠️ Banco de dados não disponível.", ephemeral=True)
            return
        
        config = await self.get_guild_config(interaction.guild_id)
        
        # Buscar dados do usuário
        data = self.bot.db.levels.find_one({
            "guild_id": interaction.guild_id,
            "user_id": usuario.id
        })
        
        if not data:
            # Se não tiver dados, mostrar nível 0
            embed = discord.Embed(
                title=f"XP de {usuario.display_name}",
                color=discord.Color.from_str(config.get("levelup_color", "#1A1A1A"))
            )
            
            embed.add_field(name="Nível", value="0", inline=True)
            embed.add_field(name="XP Total", value="0", inline=True)
            embed.add_field(name="Mensagens", value="0", inline=True)
            
            embed.add_field(
                name="Progresso",
                value="⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0 / 100 XP (0.0%)",
                inline=False
            )
            
            embed.set_footer(text=f"ID: {usuario.id}")
            embed.set_thumbnail(url=usuario.avatar.url if usuario.avatar else usuario.default_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            return
        
        # Calcular níveis e XP necessário
        xp_atual = data["xp"]
        nivel_atual = data["level"]
        messages = data.get("messages", 0)
        curve = config.get("xp_curve", 1.5)
        
        # Calcular XP necessário para o próximo nível
        xp_para_proximo = 0
        xp_necessario_total = 0
        
        for i in range(nivel_atual + 1):
            if i == 0:
                xp_necessario_nivel = 100
            else:
                xp_necessario_nivel = int(100 * ((i + 1) ** curve) - 100 * (i ** curve))
            
            if i < nivel_atual:
                xp_necessario_total += xp_necessario_nivel
            else:
                xp_para_proximo = xp_necessario_nivel
        
        # XP no nível atual
        xp_no_nivel = xp_atual - xp_necessario_total
        
        # Calcular porcentagem
        if xp_para_proximo > 0:
            porcentagem = (xp_no_nivel / xp_para_proximo) * 100
        else:
            porcentagem = 0
        
        porcentagem = min(100, max(0, porcentagem))
        
        # Criar barra de progresso com quadrados (alternativa mais compatível)
        tamanho_barra = 10
        preenchido = int(porcentagem / 10)
        barra = "⬛" * preenchido + "⬜" * (tamanho_barra - preenchido)
        
        # Criar embed
        embed = discord.Embed(
            title=f"XP de {usuario.display_name}",
            color=discord.Color.from_str(config.get("levelup_color", "#1A1A1A"))
        )
        
        embed.add_field(name="Nível", value=str(nivel_atual), inline=True)
        embed.add_field(name="XP Total", value=str(xp_atual), inline=True)
        embed.add_field(name="Mensagens", value=str(messages), inline=True)
        
        embed.add_field(
            name="Progresso",
            value=f"{barra} {xp_no_nivel} / {xp_para_proximo} XP ({porcentagem:.1f}%)",
            inline=False
        )
        
        embed.set_footer(text=f"ID: {usuario.id}")
        embed.set_thumbnail(url=usuario.avatar.url if usuario.avatar else usuario.default_avatar.url)
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Levels(bot))