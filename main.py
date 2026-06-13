import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
import asyncio
import re
import datetime
import typing
import aiohttp

SETTINGS_FILE = "settings.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('guard_bot')

def load_dotenv_file(path: str = ".env"):
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        logger.warning(f"Failed to load .env file: {e}")

load_dotenv_file()

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        default_settings = {
            "token": "token",
            "log_channel_id": None,
            "protections": {
                "anti_spam": True,
                "anti_swear": True,
                "anti_ad": True,
                "anti_link": True,
                "anti_caps": True,
                "anti_bot": True,
                "channel_protect": True,
                "category_protect": True,
                "role_protect": True,
                "ban_protect": True,
                "webhook_protect": True,
                "anti_raid": False,
                "anti_alt": False
            },
            "whitelist": {
                "users": [],
                "roles": []
            },
            "warnings": {},
            "log_channels": {}
        }
        save_settings(default_settings)
        return default_settings

def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_guild_log_channels(guild: typing.Optional[discord.Guild]) -> dict:
    if not guild:
        return {}
    log_channels = bot.settings.get("log_channels", {}) or {}
    return log_channels.get(str(guild.id), {})


def get_log_channel_id(guild: typing.Optional[discord.Guild], protection_key: typing.Optional[str] = None) -> typing.Optional[int]:
    guild_channels = get_guild_log_channels(guild)
    if protection_key and protection_key in guild_channels:
        return guild_channels.get(protection_key)
    return bot.settings.get("log_channel_id")


async def log_action(embed: discord.Embed, guild: typing.Optional[discord.Guild] = None, protection_key: typing.Optional[str] = None):
    channel_id = get_log_channel_id(guild, protection_key)
    if channel_id:
        channel = bot.get_channel(channel_id)
        if isinstance(channel, discord.abc.Messageable):
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Missing permissions to send logs to channel {channel_id}")
    else:
        logger.warning("No log channel configured for this protection action.")

LOG_CHANNEL_NAMES = {
    "anti_swear": "küfür-log",
    "anti_ad": "reklam-log",
    "anti_link": "link-log",
    "anti_caps": "caps-log",
    "anti_spam": "spam-log",
    "anti_raid": "raid-log",
    "anti_alt": "alt-hesap-log",
    "anti_bot": "bot-log",
    "channel_protect": "kanal-log",
    "category_protect": "kategori-log",
    "role_protect": "rol-log",
    "ban_protect": "ban-log",
    "webhook_protect": "webhook-log",
    "general": "guard-genel-log"
}

class GuardBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.settings: dict = load_settings() or {}
        self.user_message_times: dict = {} 
        self.banned_words: list = []
        self.stats: dict = {"deleted": 0, "timeout": 0, "kicked": 0, "banned": 0, "reverted": 0}
        self.recent_joins: list = [] 
        self.webhook_create_times: dict = {}

    async def fetch_swear_words(self):
        url = "https://raw.githubusercontent.com/ooguz/turkce-kufur-karaliste/master/karaliste.json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        self.banned_words = await response.json(content_type=None)
                        logger.info(f"Loaded {len(self.banned_words)} swear words from API.")
                    else:
                        raise Exception(f"HTTP Return Code {response.status}")
        except Exception as e:
            logger.error(f"Failed to fetch swear words API: {e}. Falling back to default list.")
            self.banned_words = [
                "amk", "aq", "amq", "amqq", "sg", "orospu", "pic", "piç", "siktir", "yavsak", "yavşak", "ibne", "oc", "oç",
                "amcık", "amcik", "yarrak", "yarak", "sik", "sikik", "sikim", "göt", "got", "gavat", "kahpe", "pezevenk", 
                "pust", "puşt", "amına koyayım", "amina koyayim", "veled", "amk çocuğu", "orospu çocuğu", "ananı", "anani",
                "sikeyim", "sokam", "sokuyum", "yarrağı", "yarrag"
            ]

    async def setup_hook(self):
        await self.fetch_swear_words()

    async def on_ready(self):
        if self.user is None:
            logger.info("GuardBot is ready but bot user is not available.")
            return
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("------")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s) globally.")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

bot = GuardBot()

def is_whitelisted(member: discord.Member) -> bool:
    whitelist = bot.settings.get("whitelist", {})
    if not isinstance(whitelist, dict): whitelist = {}
    
    users = whitelist.get("users", [])
    roles = whitelist.get("roles", [])
    
    if member.id in users:
        return True
    for role in member.roles:
        if role.id in roles:
            return True
    return False


def add_warning(user_id: int):
    pass 


def get_panel_embed():
    embed = discord.Embed(
        title="🛡️ Guard Bot - Güvenlik Paneli", 
        description=(
            "Sunucunuzu korumak için aşağıdaki menülerden sistemleri yönetebilirsiniz.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        ),
        color=0x2b2d31
    )
    if bot.user is not None and getattr(bot.user, "display_avatar", None):
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    prots = bot.settings.get("protections", {})
    def status(key): return "🟢 `Açık`" if prots.get(key, False) else "🔴 `Kapalı`"

    stats_val = (
        f"> 🗑️ **Silinen Mesaj:** `{bot.stats['deleted']}`  |  "
        f"🤐 **Susturulan:** `{bot.stats['timeout']}`  |  "
        f"👢 **Atılan:** `{bot.stats['kicked']}`\n"
        f"> 🔨 **Yasaklanan:** `{bot.stats['banned']}`  |  "
        f"🔄 **Geri Alınan İşlem:** `{bot.stats['reverted']}`"
    )
    embed.add_field(name="📊 Canlı İstatistikler", value=stats_val, inline=False)
    embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", inline=False)

    text_prots = (
        f"🛡️ **Spam:** {status('anti_spam')}\n"
        f"🤬 **Küfür:** {status('anti_swear')}\n"
        f"📢 **Reklam:** {status('anti_ad')}\n"
        f"🔗 **Link:** {status('anti_link')}\n"
        f"🔠 **Caps:** {status('anti_caps')}"
    )
    
    server_prots = (
        f"🛡️ **Raid:** {status('anti_raid')}\n"
        f"🎭 **Alt Hesap:** {status('anti_alt')}\n"
        f"🤖 **Bot:** {status('anti_bot')}\n"
        f"📁 **Kanal:** {status('channel_protect')}\n"
        f"📑 **Kategori:** {status('category_protect')}\n"
        f"🎭 **Rol:** {status('role_protect')}\n"
        f"🔨 **Ban:** {status('ban_protect')}\n"
        f"🔌 **Webhook:** {status('webhook_protect')}"
    )
    
    embed.add_field(name="💬 Metin Filtreleri", value=text_prots, inline=True)
    embed.add_field(name="⚙️ Sunucu Korumaları", value=server_prots, inline=True)
    embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", inline=False)
    
    log_ch = bot.settings.get("log_channel_id")
    embed.add_field(name="📝 Log Kanalı", value=f"👉 <#{log_ch}>" if log_ch else "👉 `Ayarlanmadı`", inline=False)
    
    return embed

def get_action_embed(selected_module=None):
    embed = discord.Embed(
        title="⚖️ Guard Bot - Ceza Paneli",
        description=(
            "Filtre ihlallerinde uygulanacak otomatik cezaları ayarlayın.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        ),
        color=0x2b2d31
    )
    actions = bot.settings.get("actions", {})
    
    def get_act_str(key):
        act = actions.get(key, "delete")
        is_text = key in ["anti_spam", "anti_swear", "anti_ad", "anti_link", "anti_caps"]
        if act == "delete":
            return "Sil" if is_text else "Geri Al"
        texts = {"timeout": "Sustur", "kick": "Kick", "ban": "Ban"}
        return texts.get(act, "?")

    def format_act(key, emoji, title):
        prefix = "👉" if key == selected_module else "▪️"
        val = get_act_str(key)
        return f"{prefix} {emoji} **{title}:** `{val}`\n"

    text_acts = (
        format_act("anti_spam", "🛡️", "Spam") +
        format_act("anti_swear", "🤬", "Küfür") +
        format_act("anti_ad", "📢", "Reklam") +
        format_act("anti_link", "🔗", "Link") +
        format_act("anti_caps", "🔠", "Caps")
    )
    
    server_acts = (
        format_act("anti_raid", "🛡️", "Raid") +
        format_act("anti_alt", "🎭", "Alt Hesap") +
        format_act("anti_bot", "🤖", "Bot") +
        format_act("channel_protect", "📁", "Kanal") +
        format_act("category_protect", "📑", "Kategori") +
        format_act("role_protect", "🎭", "Rol") +
        format_act("ban_protect", "🔨", "Ban") +
        format_act("webhook_protect", "🔌", "Webhook")
    )
    
    embed.add_field(name="💬 Metin Cezaları", value=text_acts, inline=True)
    embed.add_field(name="⚙️ Sunucu Cezaları", value=server_acts, inline=True)
    embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", inline=False)
            
    return embed

class ProtectionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Anti-Spam", value="anti_spam"),
            discord.SelectOption(label="Küfür Koruması", value="anti_swear"),
            discord.SelectOption(label="Reklam Koruması", value="anti_ad"),
            discord.SelectOption(label="Link Koruması", value="anti_link"),
            discord.SelectOption(label="Caps Lock Koruması", value="anti_caps"),
            discord.SelectOption(label="Anti-Raid (Baskın Koruması)", value="anti_raid"),
            discord.SelectOption(label="Anti-Alt (Şüpheli Hesap Koruması)", value="anti_alt"),
            discord.SelectOption(label="Anti-Bot", value="anti_bot"),
            discord.SelectOption(label="Kanal Koruması", value="channel_protect"),
            discord.SelectOption(label="Kategori Koruması", value="category_protect"),
            discord.SelectOption(label="Rol Koruması", value="role_protect"),
            discord.SelectOption(label="Ban/Kick Koruması", value="ban_protect"),
            discord.SelectOption(label="Webhook Koruması", value="webhook_protect"),
        ]
        super().__init__(placeholder="Açıp/Kapatmak istediğiniz korumayı seçin...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Bu işlemi yapmak için yönetici izniniz yok.", ephemeral=True)
        selected = self.values[0]
        bot.settings["protections"][selected] = not bot.settings["protections"].get(selected, False)
        save_settings(bot.settings)
        await interaction.response.edit_message(embed=get_panel_embed(), view=self.view)

class ActionModuleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Anti-Spam", value="anti_spam"),
            discord.SelectOption(label="Küfür Koruması", value="anti_swear"),
            discord.SelectOption(label="Reklam Koruması", value="anti_ad"),
            discord.SelectOption(label="Link Koruması", value="anti_link"),
            discord.SelectOption(label="Caps Lock Koruması", value="anti_caps"),
            discord.SelectOption(label="Anti-Raid Koruması", value="anti_raid"),
            discord.SelectOption(label="Anti-Alt Koruması", value="anti_alt"),
            discord.SelectOption(label="Anti-Bot (İzinsiz Bot)", value="anti_bot"),
            discord.SelectOption(label="Kanal Koruması", value="channel_protect"),
            discord.SelectOption(label="Kategori Koruması", value="category_protect"),
            discord.SelectOption(label="Rol Koruması", value="role_protect"),
            discord.SelectOption(label="Ban/Kick Koruması", value="ban_protect"),
            discord.SelectOption(label="Webhook Koruması", value="webhook_protect"),
        ]
        super().__init__(placeholder="Hangi korumanın cezasını ayarlayacaksınız?", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Bu işlemi yapmak için yönetici izniniz yok.", ephemeral=True)
        view = self.view
        if view is None:
            return
        view.selected_module = self.values[0]
        
        for p in self.options:
            p.default = (p.value == self.values[0])
        
        for item in view.children:
            if isinstance(item, ActionTypeSelect):
                is_text = view.selected_module in ["anti_spam", "anti_swear", "anti_ad", "anti_link", "anti_caps"]
                item.options[0].label = "Sadece Mesajı Sil" if is_text else "Sadece İşlemi Geri Al"
                item.options[0].emoji = "🗑️" if is_text else "🔄"
                break
                
        await interaction.response.edit_message(embed=get_action_embed(view.selected_module), view=view)

class ActionTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Mesajı Sil / İşlemi Geri Al", value="delete", emoji="🗑️"),
            discord.SelectOption(label="10 Dakika Sustur", value="timeout", emoji="🤐"),
            discord.SelectOption(label="Sunucudan At (Kick)", value="kick", emoji="👢"),
            discord.SelectOption(label="Yasakla (Ban)", value="ban", emoji="🔨")
        ]
        super().__init__(placeholder="Uygulanacak cezayı seçin...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Bu işlemi yapmak için yönetici izniniz yok.", ephemeral=True)
        view = self.view
        if view is None or not getattr(view, "selected_module", None):
            return await interaction.response.send_message("Önce üstteki menüden koruma seçmelisiniz!", ephemeral=True)
        bot.settings.setdefault("actions", {})[view.selected_module] = self.values[0]
        save_settings(bot.settings)
        await interaction.response.edit_message(embed=get_action_embed(view.selected_module), view=view)

class LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Log Kanalını Ayarla...", channel_types=[discord.ChannelType.text])
    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Bu işlemi yapmak için yönetici izniniz yok.", ephemeral=True)
        bot.settings["log_channel_id"] = self.values[0].id
        save_settings(bot.settings)
        await interaction.response.edit_message(embed=get_panel_embed(), view=self.view)

class GoBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Geri Dön", style=discord.ButtonStyle.secondary, emoji="◀️", row=4)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=get_panel_embed(), view=MainPanelView())

class ToggleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ProtectionSelect())
        self.add_item(GoBackButton())

class ActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.selected_module = None
        self.add_item(ActionModuleSelect())
        self.add_item(ActionTypeSelect())
        self.add_item(GoBackButton())

class LogView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(LogChannelSelect())
        self.add_item(GoBackButton())

class MainPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Korumaları Değiştir", style=discord.ButtonStyle.secondary, emoji="🛡️")
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_panel_embed(), view=ToggleView())

    @discord.ui.button(label="Cezaları Yapılandır", style=discord.ButtonStyle.secondary, emoji="⚖️")
    async def btn_actions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_action_embed(), view=ActionView())

    @discord.ui.button(label="Log Kanalı Seç", style=discord.ButtonStyle.secondary, emoji="📝")
    async def btn_log(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_panel_embed(), view=LogView())

async def get_display_name_for_log_key(key: str) -> str:
    return {
        "anti_swear": "Küfür Logu",
        "anti_ad": "Reklam Logu",
        "anti_link": "Link Logu",
        "anti_caps": "Caps Logu",
        "anti_spam": "Spam Logu",
        "anti_raid": "Raid Logu",
        "anti_alt": "Alt Hesap Logu",
        "anti_bot": "Bot Logu",
        "channel_protect": "Kanal Koruma Logu",
        "category_protect": "Kategori Koruma Logu",
        "role_protect": "Rol Koruma Logu",
        "ban_protect": "Ban Koruma Logu",
        "webhook_protect": "Webhook Logu",
        "general": "Genel Guard Logu"
    }.get(key, key)


async def get_or_create_category(guild: discord.Guild, name: str):
    category = discord.utils.get(guild.categories, name=name)
    if category:
        return category
    try:
        return await guild.create_category(name, reason="Guard Bot: Log kanalları için kategori oluşturuldu")
    except discord.Forbidden:
        return None


async def setup_log_channels_for_guild(guild: discord.Guild, category: typing.Optional[discord.CategoryChannel] = None) -> dict:
    if category is None:
        category = await get_or_create_category(guild, "guard-logları")
    if category is None:
        return {}

    channel_ids = {}
    for key, name in LOG_CHANNEL_NAMES.items():
        existing_channel = discord.utils.get(guild.text_channels, name=name)
        if existing_channel is None:
            try:
                existing_channel = await guild.create_text_channel(
                    name,
                    category=category,
                    reason="Guard Bot: Otomatik log kanalı oluşturma"
                )
            except discord.Forbidden:
                continue
        else:
            try:
                await existing_channel.edit(category=category)
            except Exception:
                pass
        channel_ids[key] = existing_channel.id

    return channel_ids


class LogSetupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Log Kanalı Kur", style=discord.ButtonStyle.primary, emoji="📝", row=1)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Bu işlemi yapmak için yönetici izniniz yok.", ephemeral=True)

        embed = discord.Embed(
            title="📂 Log Kategori Seçimi",
            description=(
                "Aşağıdaki menüden log kanallarını oluşturmak istediğiniz kategoriyi seçin. "
                "Seçtiğiniz kategoriye tüm guard log kanalları kurulacaktır."
            ),
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=embed, view=CategorySelectView())


class LogCategorySelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Log kanallarını kurmak için kategori seçin...", channel_types=[discord.ChannelType.category])

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Bu işlemi yapmak için yönetici izniniz yok.", ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("Bu komut sunucuda kullanılabilir.", ephemeral=True)

        category = self.values[0] if self.values else None
        if category is None or not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message(
                "Lütfen bir kategori seçin.",
                ephemeral=True
            )

        created_channels = await setup_log_channels_for_guild(guild, category=category)
        if not created_channels:
            return await interaction.response.edit_message(
                content="Log kanalları oluşturulamadı. Botun kanal oluşturma izinlerini kontrol edin.",
                embed=None,
                view=None
            )

        bot.settings.setdefault("log_channels", {})[str(guild.id)] = created_channels
        bot.settings["log_channel_id"] = created_channels.get("general")
        save_settings(bot.settings)

        embed = discord.Embed(
            title="✅ Log Kanalları Hazır",
            description=f"Guard log kanalları **{category.name}** kategorisine kuruldu.",
            color=discord.Color.green()
        )
        for key, channel_id in created_channels.items():
            name = await get_display_name_for_log_key(key)
            embed.add_field(name=name, value=f"<#{channel_id}>", inline=True)

        await interaction.response.edit_message(embed=embed, view=None)


class CategorySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(LogCategorySelect())
        self.add_item(GoBackButton())


class LogSetupButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(LogSetupButton())


@bot.tree.command(name="yardım", description="Bot komutlarını listeler.")
@app_commands.default_permissions(administrator=True)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Bot komutları", description="Sunucunuz için kullanılabilir yönetim komutları:", color=discord.Color.blurple())
    embed.add_field(name="/guard", value="Guard panelini açar — sunucu korumalarını ve cezaları yönetir. (Sadece Yöneticiler)", inline=False)
    embed.add_field(name="/logkur", value="Guard log kanallarını otomatik oluşturur ve koruma loglarını ayrı kanallara ayarlar.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="logkur", description="Guard log kanallarını otomatik oluşturur ve koruma türlerine göre ayarlar.")
@app_commands.default_permissions(administrator=True)
async def setup_logs(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message("Bu komut sadece sunucularda çalışır.", ephemeral=True)

    embed = discord.Embed(
        title="🔧 Log Kanal Kurulumu",
        description=(
            "Bu komutla log kanalları oluşturabilir ve mevcut bir kategori seçerek "
            "tüm logları oraya yerleştirebilirsiniz."
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(name="1.", value="Kategori seçmek için alttaki butona basın.", inline=False)
    embed.add_field(name="2.", value="Bot, seçilen kategoriye tüm guard log kanallarını kuracaktır.", inline=False)
    embed.add_field(name="Not", value="Eğer kategori seçilmezse, varsayılan olarak `guard-logları` kategorisi kullanılacaktır.", inline=False)

    await interaction.response.send_message(embed=embed, view=LogSetupButtonView(), ephemeral=True)


@bot.tree.command(name="guard", description="Guard panelini açar (Sadece Yöneticiler).")
@app_commands.default_permissions(administrator=True)
async def guard_command(interaction: discord.Interaction):
    await interaction.response.send_message(embed=get_panel_embed(), view=MainPanelView(), ephemeral=True)

@bot.tree.command(name="whitelist", description="Beyaz listeye (whitelist) kullanıcı veya rol ekle/çıkar (Sadece Yöneticiler)")
@app_commands.describe(action="Ekle (add) veya Çıkar (remove)", target="Kişi veya Rol")
@app_commands.choices(action=[
    app_commands.Choice(name="Ekle", value="add"),
    app_commands.Choice(name="Çıkar", value="remove")
])
@app_commands.default_permissions(administrator=True)
async def manage_whitelist(interaction: discord.Interaction, action: app_commands.Choice[str], target: typing.Union[discord.Member, discord.Role]):
    target_id = target.id
    target_type = "users" if isinstance(target, discord.Member) else "roles"
    target_name = getattr(target, "name", str(target_id))
    
    if action.value == "add":
        if target_id not in bot.settings["whitelist"][target_type]:
            bot.settings["whitelist"][target_type].append(target_id)
            save_settings(bot.settings)
            msg = f"{target_name} ({target_type}) beyaz listeye **eklendi**."
        else:
            msg = f"{target_name} zaten beyaz listede."
    else:
        if target_id in bot.settings["whitelist"][target_type]:
            bot.settings["whitelist"][target_type].remove(target_id)
            save_settings(bot.settings)
            msg = f"{target_name} ({target_type}) beyaz listeden **çıkarıldı**."
        else:
            msg = f"{target_name} beyaz listede bulunamadı."
            
    embed = discord.Embed(title="🛡️ Whitelist Güncellemesi", description=msg, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def process_text_protections(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    if not isinstance(message.author, discord.Member):
        return
    author = message.author
    if is_whitelisted(author):
        return

    content = message.content.lower()
    protections = bot.settings.get("protections", {})

    deleted = False
    reason = ""

    reason_key = ""

    if protections.get("anti_swear", True):
        clean_content = content.replace("1", "i").replace("0", "o").replace("3", "e").replace("4", "a").replace("@", "a")
        clean_content = re.sub(r'[^\w\s]', '', clean_content)
        words_in_message = clean_content.split()
        
        for word in bot.banned_words:
            if word in words_in_message:
                deleted = True
                reason = "Küfür Kullanımı"
                reason_key = "anti_swear"
                break
            if len(word) > 3 and word in clean_content:
                deleted = True
                reason = "Küfür Kullanımı"
                reason_key = "anti_swear"
                break

    if not deleted and protections.get("anti_ad", True):
        if "discord.gg/" in content or "discord.com/invite/" in content:
            deleted = True
            reason = "Sunucu Daveti (Reklam)"
            reason_key = "anti_ad"

    if not deleted and protections.get("anti_link", True):
        if re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content):
            deleted = True
            reason = "Bağlantı (Link) Paylaşımı"
            reason_key = "anti_link"

    if not deleted and protections.get("anti_caps", True):
        alpha_chars = [c for c in message.content if c.isalpha()]
        if len(alpha_chars) > 5:
            upper_count = sum(1 for c in alpha_chars if c.isupper())
            if (upper_count / len(alpha_chars)) > 0.7:
                deleted = True
                reason_key = "anti_caps"
                reason = "Aşırı Büyük Harf (Caps Lock) Kullanımı"

    if not deleted and protections.get("anti_spam", True):
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        uid = message.author.id
        
        if uid not in bot.user_message_times:
            bot.user_message_times[uid] = []
            
        timestamps = bot.user_message_times[uid]
        timestamps.append(now)
        
        bot.user_message_times[uid] = [t for t in timestamps if now - t <= 5.0]
        
        if len(bot.user_message_times[uid]) > 5:
            deleted = True
            reason = "Spam (Hızlı Mesaj Gönderme)"
            reason_key = "anti_spam"
            bot.user_message_times[uid] = []

    if deleted:
        bot.stats["deleted"] += 1
        try:
            await message.delete()
        except:
            pass
            
        action = bot.settings.get("actions", {}).get(reason_key, "delete")
        
        punishment_desc = ""
        try:
            if action == "timeout":
                await author.timeout(datetime.timedelta(minutes=10), reason=f"Guard Bot: {reason}")
                bot.stats["timeout"] += 1
                punishment_desc = "\n🛑 **Ceza İşlemi:** 10 Dakika Susturulma (Timeout)"
            elif action == "kick":
                await author.kick(reason=f"Guard Bot: {reason}")
                bot.stats["kicked"] += 1
                punishment_desc = "\n🛑 **Ceza İşlemi:** Sunucudan Atılma (Kick)"
            elif action == "ban":
                await author.ban(reason=f"Guard Bot: {reason}")
                bot.stats["banned"] += 1
                punishment_desc = "\n🛑 **Ceza İşlemi:** Sunucudan Yasaklanma (Ban)"
        except discord.Forbidden:
            punishment_desc = "\n⚠️ *(Botun yetkisi yetersiz olduğu için ek ceza uygulanmadı)*"

        warn_embed = discord.Embed(
            title=f"⚠️ {message.author.name}, Mesajınız Silindi!",
            description=f"**Kural İhlali:** {reason}{punishment_desc}",
            color=discord.Color.orange()
        )
        try:
            await message.author.send(embed=warn_embed)
        except discord.Forbidden:
            warn_msg = await message.channel.send(content=f"{message.author.mention}", embed=warn_embed)
            await asyncio.sleep(5)
            try:
                await warn_msg.delete()
            except:
                pass

        embed = discord.Embed(title="🛡️ Metin Koruması Tetiklendi", color=discord.Color.red())
        embed.add_field(name="Kullanıcı", value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
        embed.add_field(name="Kanal", value=getattr(message.channel, "mention", "Bilinmeyen Kanal"), inline=False)
        embed.add_field(name="Neden", value=reason, inline=False)
        embed.add_field(name="Uygulanan Ceza", value=action, inline=False)
        embed.add_field(name="Mesaj İçeriği", value=message.content[:1000] if message.content else "İçerik Bulunamadı", inline=False)
        await log_action(embed, message.guild, reason_key)

@bot.event
async def on_message(message: discord.Message):
    await process_text_protections(message)
    await bot.process_commands(message)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.content != after.content:
        await process_text_protections(after)

async def apply_server_punishment(guild: discord.Guild, user: typing.Optional[discord.Member], reason_key: str, reason_text: str):
    if user is None:
        return "Bilinmeyen Kullanıcı"
    
    action = bot.settings.get("actions", {}).get(reason_key, "delete")
    punishment_str = action
    
    try:
        if action == "timeout":
            await user.timeout(datetime.timedelta(minutes=10), reason=f"Guard Bot Server Protection: {reason_text}")
            bot.stats["timeout"] += 1
            punishment_str = "10 Dakika Susturuldu"
        elif action == "kick":
            await user.kick(reason=f"Guard Bot Server Protection: {reason_text}")
            bot.stats["kicked"] += 1
            punishment_str = "Sunucudan Atıldı (Kick)"
        elif action == "ban":
            await user.ban(reason=f"Guard Bot Server Protection: {reason_text}")
            bot.stats["banned"] += 1
            punishment_str = "Sunucudan Yasaklandı (Ban)"
        else:
            bot.stats["reverted"] += 1
            punishment_str = "Sadece İşlem Geri Alındı"
    except discord.Forbidden:
        punishment_str += " (Yetki Yetmedi)"
    except Exception as e:
        logger.error(f"Punishment error '{action}' for {user}: {e}")
        punishment_str += " (Hata Oluştu)"
        
    return punishment_str

async def get_audit_entry(guild: discord.Guild, action_type: discord.AuditLogAction, target_id: typing.Optional[int] = None) -> typing.Optional[discord.AuditLogEntry]:
    await asyncio.sleep(2)
    try:
        async for entry in guild.audit_logs(action=action_type, limit=10):
            if target_id is None:
                return entry
            target = getattr(entry, "target", None)
            if target is not None and getattr(target, "id", None) == target_id:
                return entry
    except discord.Forbidden:
        logger.warning(f"Missing view audit log permissions in {guild.name}")
    return None

def check_server_protection(guild: discord.Guild, entry: typing.Optional[discord.AuditLogEntry], protection_key: str):
    if not entry or not entry.user:
        return False
    user = entry.user
    if user is None or bot.user is None:
        return False
    if user.id == bot.user.id:
        return False  
    
    protections = bot.settings.get("protections", {})
    if not protections.get(protection_key, True): return False

    member = guild.get_member(entry.user.id)
    if not member: return True 
    
    if is_whitelisted(member): return False
    return True

@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    entry = await get_audit_entry(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
    if check_server_protection(channel.guild, entry, "channel_protect"):
        try:
            clone = await channel.clone(reason="Guard Bot: Kanal silinmesi koruması")
            if hasattr(clone, "edit"):
                getattr(clone, "edit" )(position=channel.position)
            
            embed = discord.Embed(title="🚨 Kanal Silindi & Kurtarıldı!", color=discord.Color.dark_red())
            if entry and entry.user:
                embed.add_field(name="Silen Kişi", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
                member = channel.guild.get_member(entry.user.id)
                punishment = await apply_server_punishment(channel.guild, member, "channel_protect", "İzinsiz kanal silme")
                embed.add_field(name="Uygulanan Ceza", value=punishment, inline=False)
            embed.add_field(name="Kanal Adı", value=channel.name, inline=False)
            await log_action(embed, channel.guild, "channel_protect")
        except Exception as e:
            logger.error(f"Failed to recreate channel: {e}")

@bot.event
async def on_guild_role_delete(role: discord.Role):
    entry = await get_audit_entry(role.guild, discord.AuditLogAction.role_delete, role.id)
    if check_server_protection(role.guild, entry, "role_protect"):
        try:
            await role.guild.create_role(
                name=role.name, permissions=role.permissions, color=role.color, 
                hoist=role.hoist, mentionable=role.mentionable, reason="Guard Bot: Rol silinmesi koruması"
            )
            embed = discord.Embed(title="🚨 Rol Silindi & Kurtarıldı!", color=discord.Color.dark_red())
            if entry and entry.user:
                embed.add_field(name="Silen Kişi", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
                member = role.guild.get_member(entry.user.id)
                punishment = await apply_server_punishment(role.guild, member, "role_protect", "İzinsiz rol silme")
                embed.add_field(name="Uygulanan Ceza", value=punishment, inline=False)
            embed.add_field(name="Rol Adı", value=role.name, inline=False)
            await log_action(embed, role.guild, "role_protect")
        except Exception as e:
            logger.error(f"Failed to recreate role: {e}")

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    entry = await get_audit_entry(guild, discord.AuditLogAction.ban, user.id)
    if check_server_protection(guild, entry, "ban_protect"):
        try:
            await guild.unban(user, reason="Guard Bot: İzinsiz Ban Koruması")
            embed = discord.Embed(title="🚨 İzinsiz Ban Atıldı & Kaldırıldı!", color=discord.Color.dark_red())
            if entry and entry.user:
                embed.add_field(name="Banlayan Kişi", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
                member = guild.get_member(entry.user.id)
                punishment = await apply_server_punishment(guild, member, "ban_protect", "İzinsiz üye yasaklama")
                embed.add_field(name="Uygulanan Ceza", value=punishment, inline=False)
            embed.add_field(name="Banlanan Kullanıcı", value=f"{user.mention} (`{user.id}`)", inline=False)
            await log_action(embed, guild, "ban_protect")
        except Exception as e:
            logger.error(f"Failed to unban user: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    protections = bot.settings.get("protections", {})
    
    if member.bot:
        if protections.get("anti_bot", True):
            entry = await get_audit_entry(member.guild, discord.AuditLogAction.bot_add, member.id)
            if check_server_protection(member.guild, entry, "anti_bot"):
                try:
                    await member.kick(reason="Guard Bot: İzinsiz Bot Girişi")
                    bot.stats["kicked"] += 1
                    embed = discord.Embed(title="🚨 İzinsiz Bot Eklendi & Atıldı!", color=discord.Color.dark_red())
                    if entry and entry.user:
                        embed.add_field(name="Ekleyen Kişi", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
                        actor_member = member.guild.get_member(entry.user.id)
                        punishment = await apply_server_punishment(member.guild, actor_member, "anti_bot", "İzinsiz bot daveti")
                        embed.add_field(name="Uygulanan Ceza", value=punishment, inline=False)
                    embed.add_field(name="Bot", value=f"{member.mention} (`{member.id}`)", inline=False)
                    await log_action(embed, member.guild, "anti_bot")
                except Exception as e:
                    logger.error(f"Failed to kick unauthorized bot: {e}")
        return

    if protections.get("anti_alt", False):
        now = discord.utils.utcnow()
        if (now - member.created_at).days < 7: 
            try:
                punishment = await apply_server_punishment(member.guild, member, "anti_alt", "Anti-Alt (Şüpheli Yeni Hesap)")
                embed = discord.Embed(title="🎭 Şüpheli Yeni Hesap Engellendi!", color=discord.Color.dark_red())
                embed.add_field(name="Kullanıcı", value=f"{member.mention} (`{member.id}`)", inline=False)
                embed.add_field(name="Hesap Kuruluşu", value=discord.utils.format_dt(member.created_at, "R"), inline=False)
                embed.add_field(name="Uygulanan Ceza", value=punishment, inline=False)
                await log_action(embed, member.guild, "anti_alt")
                return 
            except Exception as e:
                logger.error(f"Failed to punish alt account: {e}")

    if protections.get("anti_raid", False):
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        bot.recent_joins.append(now_ts)
        bot.recent_joins = [t for t in bot.recent_joins if now_ts - t <= 10.0]
        
        if len(bot.recent_joins) > 5: 
            try:
                punishment = await apply_server_punishment(member.guild, member, "anti_raid", "Anti-Raid (Baskın Koruması)")
                embed = discord.Embed(title="🛡️ Olası Sunucu Baskını Engellendi!", color=discord.Color.dark_red())
                embed.add_field(name="Kullanıcı", value=f"{member.mention} (`{member.id}`)", inline=False)
                embed.add_field(name="Uygulanan Ceza", value=punishment, inline=False)
                await log_action(embed, member.guild, "anti_raid")
            except Exception as e:
                logger.error(f"Failed to punish raider: {e}")

@bot.event
async def on_webhooks_update(channel: discord.abc.GuildChannel):
    entry = await get_audit_entry(channel.guild, discord.AuditLogAction.webhook_create)
    if entry and check_server_protection(channel.guild, entry, "webhook_protect"):
        try:
            # Try to delete the webhook immediately
            try:
                webhook = None
                if hasattr(channel.guild, "fetch_webhook"):
                    entry_target = getattr(entry, "target", None)
                    target_id = getattr(entry_target, "id", None)
                    if target_id is not None:
                        webhook = await getattr(channel.guild, "fetch_webhook")(target_id)
                if webhook is not None:
                    await webhook.delete(reason="Guard Bot: İzinsiz Webhook Koruması")
            except Exception:
                webhook = None

            embed = discord.Embed(title="🚨 İzinsiz Webhook Oluşturuldu & Silindi!", color=discord.Color.dark_red())

            # Rate-limit / flood detection per guild+user (3 creations per 60s -> escalate)
            if entry and entry.user:
                actor_id = entry.user.id
                guild_id = channel.guild.id
                now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
                guild_map = bot.webhook_create_times.setdefault(guild_id, {})
                times = guild_map.setdefault(actor_id, [])
                times.append(now_ts)
                # keep only last 60 seconds
                times = [t for t in times if now_ts - t <= 60]
                guild_map[actor_id] = times

                embed.add_field(name="Oluşturan Kişi", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)

                # If user created too many webhooks recently, escalate punishment
                if len(times) > 3:
                    member = channel.guild.get_member(actor_id)
                    try:
                        # try direct guild ban as escalation
                        await channel.guild.ban(member or entry.user, reason="Guard Bot: Çoklu izinsiz webhook oluşturma (Otomatik)")
                        punishment_str = "Sunucudan Yasaklandı (Otomatik Ban)"
                        bot.stats["banned"] += 1
                    except Exception:
                        punishment_str = await apply_server_punishment(channel.guild, member, "webhook_protect", "İzinsiz webhook oluşturma (Flood)")
                    embed.add_field(name="Uygulanan Ceza", value=punishment_str, inline=False)
                else:
                    member = channel.guild.get_member(actor_id)
                    punishment = await apply_server_punishment(channel.guild, member, "webhook_protect", "İzinsiz webhook oluşturma")
                    embed.add_field(name="Uygulanan Ceza", value=punishment, inline=False)

            embed.add_field(name="Kanal", value=channel.mention, inline=False)
            await log_action(embed, channel.guild, "webhook_protect")
        except Exception as e:
            logger.error(f"Failed to handle unauthorized webhook: {e}")


if __name__ == '__main__':
    env_token = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    settings_token = bot.settings.get("token")
    token = env_token or settings_token
    if token and isinstance(token, str) and token.strip():
        try:
            bot.run(token.strip())
        except Exception as e:
            logger.error(f"Bot başlatılamadı: {e}")
    else:
        logger.error("Lütfen env dosyasına veya settings.json dosyasına geçerli bir bot token'ı ekleyin ve botu tekrar başlatın.")
