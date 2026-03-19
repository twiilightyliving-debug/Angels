import re
import uuid
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, Button, View, Modal, TextInput
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_custom_emojis(text: str) -> str:
    cleaned = re.sub(r'<a?:\w+:\d+>', '', text).strip()
    return cleaned if cleaned else text


def _extract_emoji(text: str):
    """Retorna (PartialEmoji, label_sem_emoji) ou (None, texto_original)."""
    match = re.search(r'<(a?):(\w+):(\d+)>', text)
    if match:
        animated  = match.group(1) == 'a'
        name      = match.group(2)
        emoji_id  = int(match.group(3))
        emoji_obj = discord.PartialEmoji(name=name, id=emoji_id, animated=animated)
        label     = re.sub(r'<a?:\w+:\d+>', '', text).strip()
        return emoji_obj, (label if label else name)
    return None, text


# ── Modais ────────────────────────────────────────────────────────────────────

class CreatePainelModal(Modal, title="Criar Novo Painel"):
    def __init__(self, cog, message):
        super().__init__()
        self.cog     = cog
        self.message = message

    nome = TextInput(label="Nome do painel", placeholder="Ex: Times, Cargos VIP, Regiões...",
                     required=True, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id   = str(interaction.guild_id)
        panel_name = self.nome.value.strip()

        # Verifica duplicata
        paineis = self.cog.paineis.get(guild_id, {})
        if any(p['name'] == panel_name for p in paineis.values()):
            await interaction.response.send_message(f"❌ Já existe um painel chamado **{panel_name}**!", ephemeral=True)
            return

        panel_id = str(uuid.uuid4())[:8]
        self.cog._create_painel(guild_id, panel_id, panel_name)

        await interaction.response.defer()
        embed = self.cog.create_list_embed(guild_id)
        view  = PainelListView(self.cog, guild_id)
        await interaction.edit_original_response(embed=embed, view=view)
        await interaction.followup.send(f"✅ Painel **{panel_name}** criado! Selecione-o no menu para configurar.", ephemeral=True)


class AddCargoModal(Modal, title="Adicionar Cargo por ID"):
    def __init__(self, cog, guild_id, panel_id, message):
        super().__init__()
        self.cog      = cog
        self.guild_id = guild_id
        self.panel_id = panel_id
        self.message  = message

    nome_exibicao = TextInput(label="Nome de exibição",
                              placeholder="Ex: <a:carpe~15:123456789> Flamengo",
                              required=True, max_length=100)
    cargo_id = TextInput(label="ID do Cargo", placeholder="Cole o ID do cargo aqui",
                         required=True, max_length=20)

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

        roles = self.cog.paineis[self.guild_id][self.panel_id]['roles']
        if nome in roles:
            await interaction.response.send_message(f"❌ O nome **{nome}** já existe neste painel!", ephemeral=True)
            return

        roles[nome] = {'role_id': role_id, 'role_name': role.name}
        self.cog._save_painel(self.guild_id, self.panel_id)

        await interaction.response.defer()
        embed = self.cog.create_config_embed(self.guild_id, self.panel_id)
        await interaction.edit_original_response(embed=embed)
        await interaction.followup.send(f"✅ Cargo **{nome}** adicionado!", ephemeral=True)


class EditEmbedModal(Modal):
    def __init__(self, cog, field, title, label, current_value, guild_id, panel_id, message):
        super().__init__(title=title)
        self.cog      = cog
        self.field    = field
        self.guild_id = guild_id
        self.panel_id = panel_id
        self.message  = message

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

        painel = self.cog.paineis[self.guild_id][self.panel_id]
        painel['config'][f"embed_{self.field}"] = value
        self.cog._save_painel(self.guild_id, self.panel_id)

        await interaction.response.defer()
        embed = self.cog.create_config_embed(self.guild_id, self.panel_id)
        await interaction.edit_original_response(embed=embed)
        await interaction.followup.send("✅ Configuração salva!", ephemeral=True)


class RenamePainelModal(Modal, title="Renomear Painel"):
    def __init__(self, cog, guild_id, panel_id, message):
        super().__init__()
        self.cog      = cog
        self.guild_id = guild_id
        self.panel_id = panel_id
        self.message  = message

    novo_nome = TextInput(label="Novo nome", required=True, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.novo_nome.value.strip()
        self.cog.paineis[self.guild_id][self.panel_id]['name'] = nome
        self.cog._save_painel(self.guild_id, self.panel_id)

        await interaction.response.defer()
        embed = self.cog.create_config_embed(self.guild_id, self.panel_id)
        await interaction.edit_original_response(embed=embed)
        await interaction.followup.send(f"✅ Painel renomeado para **{nome}**!", ephemeral=True)


# ── Views ─────────────────────────────────────────────────────────────────────

class PainelListView(View):
    """Tela inicial — lista os painéis e permite criar novo."""

    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog      = cog
        self.guild_id = guild_id
        self._build()

    def _build(self):
        self.clear_items()
        paineis = self.cog.paineis.get(self.guild_id, {})

        if paineis:
            options = []
            for pid, data in paineis.items():
                options.append(discord.SelectOption(
                    label=data['name'][:100],
                    description=f"{len(data['roles'])} cargo(s)",
                    value=pid
                ))
            select = Select(placeholder="Selecione um painel para editar...",
                            options=options, min_values=1, max_values=1)
            select.callback = self._select_callback
            self.add_item(select)

        btn_new = Button(label="Novo Painel", style=discord.ButtonStyle.success, emoji="➕", row=1)
        btn_new.callback = self._new_callback
        self.add_item(btn_new)

    async def _select_callback(self, interaction: discord.Interaction):
        panel_id = interaction.data['values'][0]
        embed    = self.cog.create_config_embed(self.guild_id, panel_id)
        view     = PainelConfigView(self.cog, self.guild_id, panel_id)
        await interaction.response.edit_message(embed=embed, view=view)

    async def _new_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreatePainelModal(self.cog, interaction.message))


class RemoveCargoSelect(Select):
    def __init__(self, cog, guild_id, panel_id, roles_dict, original_message):
        self.cog      = cog
        self.guild_id = guild_id
        self.panel_id = panel_id
        self.original_message = original_message

        options = []
        for nome, role_data in roles_dict.items():
            emoji_obj, label = _extract_emoji(nome)
            opt = discord.SelectOption(
                label=label[:100],
                description=f"Cargo: {role_data.get('role_name', '?')}"[:100],
                value=nome[:100]
            )
            if emoji_obj:
                opt.emoji = emoji_obj
            options.append(opt)

        if not options:
            options.append(discord.SelectOption(label="Nenhum cargo configurado", value="none", default=True))

        super().__init__(placeholder="Selecione um cargo para remover...",
                         options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há cargos para remover.", ephemeral=True)
            return

        nome   = self.values[0]
        roles  = self.cog.paineis[self.guild_id][self.panel_id]['roles']

        if nome not in roles:
            await interaction.response.send_message("❌ Cargo não encontrado!", ephemeral=True)
            return

        del roles[nome]
        self.cog._save_painel(self.guild_id, self.panel_id)

        await interaction.response.defer()
        embed = self.cog.create_config_embed(self.guild_id, self.panel_id)
        await interaction.edit_original_response(embed=embed)
        await interaction.followup.send(f"✅ Cargo **{nome}** removido!", ephemeral=True)


class PainelConfigView(View):
    """Tela de configuração de um painel específico."""

    def __init__(self, cog, guild_id, panel_id):
        super().__init__(timeout=None)
        self.cog      = cog
        self.guild_id = guild_id
        self.panel_id = panel_id

    def _cfg(self):
        return self.cog.paineis[self.guild_id][self.panel_id]['config']

    # Row 0: cargos (3 botões)
    @discord.ui.button(label="➕ Adicionar Cargo", style=discord.ButtonStyle.success, row=0)
    async def add_cargo(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(
            AddCargoModal(self.cog, self.guild_id, self.panel_id, interaction.message))

    @discord.ui.button(label="➖ Remover Cargo", style=discord.ButtonStyle.danger, row=0)
    async def remove_cargo(self, interaction: discord.Interaction, button: Button):
        roles = self.cog.paineis[self.guild_id][self.panel_id]['roles']
        if not roles:
            await interaction.response.send_message("Não há cargos para remover.", ephemeral=True)
            return
        view = View(timeout=60)
        view.add_item(RemoveCargoSelect(self.cog, self.guild_id, self.panel_id, roles, interaction.message))
        await interaction.response.send_message("Selecione o cargo para remover:", view=view, ephemeral=True)

    @discord.ui.button(label="🔄 Atualizar", style=discord.ButtonStyle.secondary, row=0)
    async def refresh(self, interaction: discord.Interaction, button: Button):
        embed = self.cog.create_config_embed(self.guild_id, self.panel_id)
        await interaction.response.edit_message(embed=embed, view=self)

    # Row 1: aparência (5 botões)
    @discord.ui.button(label="Título", style=discord.ButtonStyle.primary, row=1)
    async def edit_title(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg()
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "title", "Editar Título", "Novo título:",
            cfg["embed_title"], self.guild_id, self.panel_id, interaction.message))

    @discord.ui.button(label="Descrição", style=discord.ButtonStyle.primary, row=1)
    async def edit_desc(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg()
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "description", "Editar Descrição", "Nova descrição:",
            cfg["embed_description"], self.guild_id, self.panel_id, interaction.message))

    @discord.ui.button(label="Cor", style=discord.ButtonStyle.primary, row=1)
    async def edit_color(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg()
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "color", "Editar Cor", "Cor em hex (ex: 5865F2):",
            f"{cfg['embed_color']:06X}", self.guild_id, self.panel_id, interaction.message))

    @discord.ui.button(label="Footer", style=discord.ButtonStyle.primary, row=1)
    async def edit_footer(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg()
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "footer", "Editar Footer", "Novo footer:",
            cfg["embed_footer"], self.guild_id, self.panel_id, interaction.message))

    @discord.ui.button(label="Thumbnail", style=discord.ButtonStyle.primary, row=1)
    async def edit_thumb(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg()
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "thumbnail", "Editar Thumbnail", "URL da thumbnail:",
            cfg["embed_thumbnail"] or "", self.guild_id, self.panel_id, interaction.message))

    # Row 2: imagem + painel (4 botões)
    @discord.ui.button(label="Imagem", style=discord.ButtonStyle.secondary, row=2)
    async def edit_image(self, interaction: discord.Interaction, button: Button):
        cfg = self._cfg()
        await interaction.response.send_modal(EditEmbedModal(
            self.cog, "image", "Editar Imagem", "URL da imagem:",
            cfg["embed_image"] or "", self.guild_id, self.panel_id, interaction.message))

    @discord.ui.button(label="✏️ Renomear", style=discord.ButtonStyle.secondary, row=2)
    async def rename(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(
            RenamePainelModal(self.cog, self.guild_id, self.panel_id, interaction.message))

    @discord.ui.button(label="🗑️ Deletar Painel", style=discord.ButtonStyle.danger, row=2)
    async def delete_painel(self, interaction: discord.Interaction, button: Button):
        nome = self.cog.paineis[self.guild_id][self.panel_id]['name']
        self.cog._delete_painel(self.guild_id, self.panel_id)
        embed = self.cog.create_list_embed(self.guild_id)
        view  = PainelListView(self.cog, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)
        await interaction.followup.send(f"🗑️ Painel **{nome}** deletado.", ephemeral=True)

    # Row 3: navegação (2 botões)
    @discord.ui.button(label="◀ Voltar", style=discord.ButtonStyle.secondary, row=3)
    async def voltar(self, interaction: discord.Interaction, button: Button):
        embed = self.cog.create_list_embed(self.guild_id)
        view  = PainelListView(self.cog, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="📤 Enviar Painel no Canal", style=discord.ButtonStyle.success, row=3)
    async def enviar(self, interaction: discord.Interaction, button: Button):
        roles = self.cog.paineis[self.guild_id][self.panel_id]['roles']
        if not roles:
            await interaction.response.send_message("❌ Adicione pelo menos um cargo antes de enviar!", ephemeral=True)
            return
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Preciso da permissão `Gerenciar Cargos`!", ephemeral=True)
            return
        embed = self.cog.create_public_embed(self.guild_id, self.panel_id)
        view  = UserCargoView(self.cog, self.guild_id, self.panel_id)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Painel enviado!", ephemeral=True)


class UserCargoSelect(Select):
    """Select público — PERSISTENTE."""

    def __init__(self, cog, guild_id, panel_id):
        self.cog      = cog
        self.guild_id = guild_id
        self.panel_id = panel_id

        roles   = cog.paineis.get(guild_id, {}).get(panel_id, {}).get('roles', {})
        options = []

        for nome, role_data in roles.items():
            emoji_obj, label = _extract_emoji(nome)
            opt = discord.SelectOption(
                label=label[:100],
                description=f"Cargo: {role_data.get('role_name', 'Cargo')}"[:100],
                value=nome[:100]
            )
            if emoji_obj:
                opt.emoji = emoji_obj
            options.append(opt)

        if not options:
            options.append(discord.SelectOption(label="Nenhum cargo disponível", value="none", default=True))

        super().__init__(
            placeholder="Escolha um cargo...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"cargo:select:{guild_id}:{panel_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há cargos configurados.", ephemeral=True)
            return

        nome      = self.values[0]
        painel    = self.cog.paineis.get(str(self.guild_id), {}).get(self.panel_id, {})
        role_data = painel.get('roles', {}).get(nome)

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


class UserCargoView(View):
    def __init__(self, cog, guild_id, panel_id):
        super().__init__(timeout=None)
        self.add_item(UserCargoSelect(cog, guild_id, panel_id))


# ── Cog principal ─────────────────────────────────────────────────────────────

class Cargo(commands.Cog):
    def __init__(self, bot):
        self.bot     = bot
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.client  = None
        self.col     = None   # coleção única: cargo_paineis
        self.paineis = {}     # guild_id -> {panel_id -> {name, config, roles}}

        self._connect_mongo()
        self._load_all()

        # Registra views persistentes
        for guild_id, paineis in self.paineis.items():
            for panel_id in paineis:
                self.bot.add_view(UserCargoView(self, guild_id, panel_id))

    # ── MongoDB ───────────────────────────────────────────────────────────────

    def _connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri)
            self.col    = self.client["discord_bot"]["cargo_paineis"]
            self.client.admin.command('ping')
            print("✅ [Cargo] MongoDB conectado.")
        except ConnectionFailure:
            print("❌ [Cargo] Falha ao conectar ao MongoDB.")
            self.client = self.col = None

    def _load_all(self):
        self.paineis = {}
        if self.col is None:
            return
        for doc in self.col.find({}):
            gid      = str(doc['guild_id'])
            pid      = doc['panel_id']
            self.paineis.setdefault(gid, {})[pid] = {
                'name':   doc.get('name', 'Painel'),
                'config': doc.get('config', self._default_config()),
                'roles':  doc.get('roles', {}),
            }
        total = sum(len(v) for v in self.paineis.values())
        print(f"📦 [Cargo] {total} painéis carregados.")

    def _default_config(self):
        return {
            "embed_title":       "Painel de Cargos",
            "embed_description": "Selecione os cargos que deseja receber:",
            "embed_color":       0x5865F2,
            "embed_footer":      "Clique no menu abaixo para pegar/remover um cargo",
            "embed_thumbnail":   None,
            "embed_image":       None,
        }

    def _create_painel(self, guild_id, panel_id, name):
        self.paineis.setdefault(guild_id, {})[panel_id] = {
            'name':   name,
            'config': self._default_config(),
            'roles':  {},
        }
        self._save_painel(guild_id, panel_id)

    def _save_painel(self, guild_id, panel_id):
        if self.col is None:
            return
        data = self.paineis[guild_id][panel_id]
        self.col.replace_one(
            {"guild_id": guild_id, "panel_id": panel_id},
            {"guild_id": guild_id, "panel_id": panel_id, **data},
            upsert=True
        )

    def _delete_painel(self, guild_id, panel_id):
        if guild_id in self.paineis and panel_id in self.paineis[guild_id]:
            del self.paineis[guild_id][panel_id]
        if self.col is not None:
            self.col.delete_one({"guild_id": guild_id, "panel_id": panel_id})

    # ── Embeds ────────────────────────────────────────────────────────────────

    def create_list_embed(self, guild_id):
        """Embed da tela inicial com a lista de painéis."""
        paineis = self.paineis.get(guild_id, {})
        embed   = discord.Embed(title="⚙️ Gerenciar Painéis de Cargo", color=0x5865F2)

        if paineis:
            linhas = [f"**{d['name']}** — {len(d['roles'])} cargo(s)" for d in paineis.values()]
            embed.description = "\n".join(linhas)
        else:
            embed.description = "*Nenhum painel criado ainda. Clique em **Novo Painel** para começar!*"

        return embed

    def create_config_embed(self, guild_id, panel_id):
        """Embed de configuração de um painel específico."""
        painel = self.paineis[guild_id][panel_id]
        cfg    = painel['config']
        roles  = painel['roles']

        embed = discord.Embed(
            title=cfg["embed_title"],
            description=cfg["embed_description"],
            color=cfg["embed_color"]
        )
        embed.set_author(name=f"Editando: {painel['name']}")

        if cfg["embed_footer"]:    embed.set_footer(text=cfg["embed_footer"])
        if cfg["embed_thumbnail"]: embed.set_thumbnail(url=cfg["embed_thumbnail"])
        if cfg["embed_image"]:     embed.set_image(url=cfg["embed_image"])
        return embed

    def create_public_embed(self, guild_id, panel_id):
        """Embed público sem o author de edição."""
        painel = self.paineis[guild_id][panel_id]
        cfg    = painel['config']

        embed = discord.Embed(
            title=cfg["embed_title"],
            description=cfg["embed_description"],
            color=cfg["embed_color"]
        )
        if cfg["embed_footer"]:    embed.set_footer(text=cfg["embed_footer"])
        if cfg["embed_thumbnail"]: embed.set_thumbnail(url=cfg["embed_thumbnail"])
        if cfg["embed_image"]:     embed.set_image(url=cfg["embed_image"])
        return embed

    # ── Comando slash ─────────────────────────────────────────────────────────

    @app_commands.command(name="cargo", description="Gerencia os painéis de cargo (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def cargo(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        embed    = self.create_list_embed(guild_id)
        view     = PainelListView(self, guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Cargo(bot))