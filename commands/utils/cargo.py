import re
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, Button, View, Modal, TextInput
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


def _strip_custom_emojis(text: str) -> str:
    cleaned = re.sub(r'<a?:\w+:\d+>', '', text).strip()
    return cleaned if cleaned else text


# ── Modais ────────────────────────────────────────────────────────────────────

class AddCargoModal(Modal, title="Adicionar Cargo por ID"):
    def __init__(self, cog, message):
        super().__init__()
        self.cog = cog
        self.message = message

    nome_exibicao = TextInput(
        label="Nome de exibição",
        placeholder="Ex: <a:carpe~15:123456789> Flamengo",
        required=True,
        max_length=100
    )
    cargo_id = TextInput(
        label="ID do Cargo",
        placeholder="Cole o ID do cargo aqui",
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.nome_exibicao.value.strip()

        try:
            role_id = int(self.cargo_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ ID inválido!", ephemeral=True)
            return

        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Cargo não encontrado! Verifique o ID.", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        if guild_id not in self.cog.roles_cargos:
            self.cog.roles_cargos[guild_id] = {}

        if nome in self.cog.roles_cargos[guild_id]:
            await interaction.response.send_message(f"❌ O nome '{nome}' já existe!", ephemeral=True)
            return

        self.cog.roles_cargos[guild_id][nome] = {'role_id': role_id, 'role_name': role.name}

        if self.cog.roles_collection is not None:
            self.cog.roles_collection.update_one(
                {"guild_id": guild_id, "nome_exibicao": nome},
                {"$set": {"guild_id": guild_id, "nome_exibicao": nome, "role_id": role_id, "role_name": role.name}},
                upsert=True
            )

        await interaction.response.defer()
        embed = self.cog.create_preview_embed(guild_id)
        await self.message.edit(embed=embed)
        await interaction.followup.send(f"✅ Cargo **{nome}** adicionado!", ephemeral=True)


class EditEmbedModal(Modal):
    def __init__(self, cog, field, title, label, current_value, guild_id, message):
        super().__init__(title=title)
        self.cog = cog
        self.field = field
        self.guild_id = guild_id
        self.message = message

        is_long = field in ["description", "footer", "title"]
        max_len = 256 if field == "title" else 4000 if field == "description" else 2048

        self.input = TextInput(
            label=label,
            default=str(current_value) if current_value else "",
            required=True,
            max_length=max_len,
            style=discord.TextStyle.paragraph if is_long else discord.TextStyle.short
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.input.value

        if self.field == 'color':
            try:
                value = int(value.replace('#', ''), 16)
            except ValueError:
                await interaction.response.send_message("❌ Cor inválida! Use formato hex (ex: 5865F2).", ephemeral=True)
                return

        config = self.cog.get_guild_config(self.guild_id)
        config[f"embed_{self.field}"] = value
        self.cog.save_guild_config(self.guild_id)

        await interaction.response.defer()
        embed = self.cog.create_preview_embed(self.guild_id)
        await self.message.edit(embed=embed)
        await interaction.followup.send("✅ Configuração salva!", ephemeral=True)


# ── Views ─────────────────────────────────────────────────────────────────────

class RemoveCargoSelect(Select):
    def __init__(self, cog, roles_dict, original_message):
        self.cog = cog
        self.original_message = original_message
        options = []
        for nome, role_data in roles_dict.items():
            label = _strip_custom_emojis(nome)
            options.append(discord.SelectOption(
                label=label[:100],
                description=f"Cargo: {role_data.get('role_name', '?')}"[:100],
                value=nome[:100]
            ))

        if not options:
            options.append(discord.SelectOption(label="Nenhum cargo configurado", value="none", default=True))

        super().__init__(placeholder="Selecione um cargo para remover...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há cargos para remover.", ephemeral=True)
            return

        nome = self.values[0]
        guild_id = str(interaction.guild_id)

        if guild_id not in self.cog.roles_cargos or nome not in self.cog.roles_cargos[guild_id]:
            await interaction.response.send_message(f"❌ Cargo não encontrado!", ephemeral=True)
            return

        del self.cog.roles_cargos[guild_id][nome]

        if self.cog.roles_collection is not None:
            self.cog.roles_collection.delete_one({"guild_id": guild_id, "nome_exibicao": nome})

        await interaction.response.defer()
        embed = self.cog.create_preview_embed(guild_id)
        await self.original_message.edit(embed=embed)
        await interaction.followup.send(f"✅ Cargo **{nome}** removido!", ephemeral=True)


class CargoConfigView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Adicionar Cargo", style=discord.ButtonStyle.success, emoji="➕", row=0)
    async def add_button(self, interaction: discord.Interaction, button: Button):
        modal = AddCargoModal(self.cog, interaction.message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remover Cargo", style=discord.ButtonStyle.danger, emoji="➖", row=0)
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        guild_id = str(interaction.guild_id)
        roles_dict = self.cog.roles_cargos.get(guild_id, {})

        if not roles_dict:
            await interaction.response.send_message("Não há cargos configurados para remover.", ephemeral=True)
            return

        view = View(timeout=60)
        view.add_item(RemoveCargoSelect(self.cog, roles_dict, interaction.message))
        await interaction.response.send_message("Selecione o cargo para remover:", view=view, ephemeral=True)

    @discord.ui.button(label="Atualizar Preview", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        guild_id = str(interaction.guild_id)
        embed = self.cog.create_preview_embed(guild_id)
        await interaction.response.edit_message(embed=embed, view=self)


class EditCargoConfigView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    def _cfg(self, guild_id):
        return self.cog.get_guild_config(str(guild_id))

    @discord.ui.button(label="Título", style=discord.ButtonStyle.primary, row=0)
    async def edit_title(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg(interaction.guild_id)
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "title", "Editar Título", "Novo título:",
            cfg["embed_title"], str(interaction.guild_id), interaction.message))

    @discord.ui.button(label="Descrição", style=discord.ButtonStyle.primary, row=0)
    async def edit_description(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg(interaction.guild_id)
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "description", "Editar Descrição", "Nova descrição (suporta <a:emoji:id>):",
            cfg["embed_description"], str(interaction.guild_id), interaction.message))

    @discord.ui.button(label="Cor", style=discord.ButtonStyle.primary, row=0)
    async def edit_color(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg(interaction.guild_id)
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "color", "Editar Cor", "Cor em hex (ex: 5865F2):",
            f"{cfg['embed_color']:06X}", str(interaction.guild_id), interaction.message))

    @discord.ui.button(label="Footer", style=discord.ButtonStyle.primary, row=0)
    async def edit_footer(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg(interaction.guild_id)
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "footer", "Editar Footer", "Novo footer:",
            cfg["embed_footer"], str(interaction.guild_id), interaction.message))

    @discord.ui.button(label="Thumbnail", style=discord.ButtonStyle.secondary, row=1)
    async def edit_thumbnail(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg(interaction.guild_id)
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "thumbnail", "Editar Thumbnail", "URL da thumbnail:",
            cfg["embed_thumbnail"] or "", str(interaction.guild_id), interaction.message))

    @discord.ui.button(label="Imagem", style=discord.ButtonStyle.secondary, row=1)
    async def edit_image(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg(interaction.guild_id)
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "image", "Editar Imagem", "URL da imagem:",
            cfg["embed_image"] or "", str(interaction.guild_id), interaction.message))


class UserCargoSelect(Select):
    def __init__(self, cog, guild_id):
        self.cog = cog
        self.guild_id = guild_id
        options = []

        for nome, role_data in cog.roles_cargos.get(str(guild_id), {}).items():
            label = _strip_custom_emojis(nome)
            options.append(discord.SelectOption(
                label=label[:100],
                description=f"Cargo: {role_data.get('role_name', 'Cargo')}"[:100],
                value=nome[:100]
            ))

        if not options:
            options.append(discord.SelectOption(label="Nenhum cargo disponível", value="none", default=True))

        super().__init__(
            placeholder="Escolha um cargo...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"cargo:user_select:{guild_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há cargos configurados neste servidor.", ephemeral=True)
            return

        nome = self.values[0]
        role_data = self.cog.roles_cargos.get(str(self.guild_id), {}).get(nome)

        if not role_data:
            await interaction.response.send_message("❌ Cargo não encontrado!", ephemeral=True)
            return

        role = interaction.guild.get_role(role_data['role_id'])
        if not role:
            await interaction.response.send_message("❌ O cargo não existe mais no servidor!", ephemeral=True)
            return

        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Não tenho permissão `Gerenciar Cargos`!", ephemeral=True)
            return

        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                f"❌ Não consigo atribuir **{role.name}** — ele está acima do meu cargo!", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Cargo **{nome}** removido!", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Cargo **{nome}** adicionado!", ephemeral=True)


class PainelCargoView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.add_item(UserCargoSelect(cog, guild_id))


# ── Cog principal ─────────────────────────────────────────────────────────────

class Cargo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = "discord_bot"
        self.client = None
        self.config_collection = None
        self.roles_collection = None
        self.roles_cargos = {}
        self.embed_configs = {}

        self._connect_mongo()
        self._load_all_configs()
        self._load_all_roles()

        for guild_id in self.roles_cargos:
            self.bot.add_view(PainelCargoView(self, int(guild_id)))

    def _connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri)
            self.config_collection = self.client[self.db_name]["cargo_config"]
            self.roles_collection  = self.client[self.db_name]["cargo_roles"]
            self.client.admin.command('ping')
            print("✅ [Cargo] MongoDB conectado.")
        except ConnectionFailure:
            print("❌ [Cargo] Falha ao conectar ao MongoDB.")
            self.client = self.config_collection = self.roles_collection = None

    def _load_all_configs(self):
        self.embed_configs = {}
        if self.config_collection is None:
            return
        for doc in self.config_collection.find({}):
            gid = doc.get("guild_id")
            if gid:
                self.embed_configs[gid] = {
                    "embed_title":       doc.get("embed_title",       "Painel de Cargos"),
                    "embed_description": doc.get("embed_description", "Selecione os cargos que deseja receber:"),
                    "embed_color":       doc.get("embed_color",       0x5865F2),
                    "embed_footer":      doc.get("embed_footer",      "Clique no menu abaixo para pegar/remover um cargo"),
                    "embed_thumbnail":   doc.get("embed_thumbnail",   None),
                    "embed_image":       doc.get("embed_image",       None),
                }
        print(f"📦 [Cargo] {len(self.embed_configs)} configs carregadas.")

    def _load_all_roles(self):
        self.roles_cargos = {}
        if self.roles_collection is None:
            return
        for doc in self.roles_collection.find({}):
            gid  = str(doc.get("guild_id", ""))
            nome = doc.get("nome_exibicao")
            rid  = doc.get("role_id")
            if gid and nome and rid:
                self.roles_cargos.setdefault(gid, {})[nome] = {
                    "role_id":   rid,
                    "role_name": doc.get("role_name", "Cargo desconhecido"),
                }
        total = sum(len(v) for v in self.roles_cargos.values())
        print(f"📦 [Cargo] {total} cargos em {len(self.roles_cargos)} servidores.")

    def get_guild_config(self, guild_id):
        if guild_id not in self.embed_configs:
            self.embed_configs[guild_id] = {
                "embed_title":       "Painel de Cargos",
                "embed_description": "Selecione os cargos que deseja receber:",
                "embed_color":       0x5865F2,
                "embed_footer":      "Clique no menu abaixo para pegar/remover um cargo",
                "embed_thumbnail":   None,
                "embed_image":       None,
            }
        return self.embed_configs[guild_id]

    def save_guild_config(self, guild_id):
        if self.config_collection is None or guild_id not in self.embed_configs:
            return
        cfg = self.embed_configs[guild_id]
        self.config_collection.replace_one(
            {"guild_id": guild_id},
            {"guild_id": guild_id, **cfg},
            upsert=True
        )

    def create_preview_embed(self, guild_id):
        cfg = self.get_guild_config(guild_id)

        descricao = cfg["embed_description"]
        roles = self.roles_cargos.get(guild_id, {})
        if roles:
            linhas = [f"**{nome}** → `@{d['role_name']}`" for nome, d in roles.items()]
            descricao += "\n\n**Cargos Disponíveis**\n" + "\n".join(linhas)
        else:
            descricao += "\n\n*Nenhum cargo configurado neste servidor*"

        embed = discord.Embed(title=cfg["embed_title"], description=descricao, color=cfg["embed_color"])
        if cfg["embed_footer"]:    embed.set_footer(text=cfg["embed_footer"])
        if cfg["embed_thumbnail"]: embed.set_thumbnail(url=cfg["embed_thumbnail"])
        if cfg["embed_image"]:     embed.set_image(url=cfg["embed_image"])
        return embed

    # ── Comandos slash ────────────────────────────────────────────────────────

    @app_commands.command(name="config_cargo", description="Configura os cargos do painel (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def config_cargo(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        embed = self.create_preview_embed(guild_id)
        await interaction.response.send_message("⚙️ **Configuração dos Cargos**", embed=embed,
                                                 view=CargoConfigView(self), ephemeral=True)

    @app_commands.command(name="painel_cargo", description="Envia o painel de cargos no canal atual (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def painel_cargo(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)

        if not self.roles_cargos.get(guild_id):
            await interaction.response.send_message(
                "❌ Não há cargos configurados! Use `/config_cargo` para adicionar.", ephemeral=True)
            return

        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Preciso da permissão `Gerenciar Cargos`!", ephemeral=True)
            return

        embed = self.create_preview_embed(guild_id)
        await interaction.channel.send(embed=embed, view=PainelCargoView(self, interaction.guild_id))
        await interaction.response.send_message("✅ Painel enviado!", ephemeral=True)

    @app_commands.command(name="editar_cargo", description="Edita a aparência do painel de cargos (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def editar_cargo(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        self.get_guild_config(guild_id)
        embed = self.create_preview_embed(guild_id)
        await interaction.response.send_message("🎨 **Editar Aparência do Painel**", embed=embed,
                                                 view=EditCargoConfigView(self), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Cargo(bot))