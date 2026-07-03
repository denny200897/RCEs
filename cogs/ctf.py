import discord
from discord.ext import commands, tasks
import aiohttp
import datetime
import json
import os
import re

DATA_FILE = "ctf_data.json"

class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_data()
        self.ctftime_daily_check.start()
        self.ctf_hourly_reminder.start()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                self.data = {"sent_ctfs": [], "upcoming": {}}
        else:
            self.data = {"sent_ctfs": [], "upcoming": {}}

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    async def fetch_upcoming_ctfs(self, days=3):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        now = datetime.datetime.now(datetime.timezone.utc)
        start_timestamp = int(now.timestamp())
        finish_timestamp = int((now + datetime.timedelta(days=days)).timestamp())
        
        url = f"https://ctftime.org/api/v1/events/?limit=10&start={start_timestamp}&finish={finish_timestamp}"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None

    def format_ctf_time(self, start_str, end_str):
        tw_tz = datetime.timezone(datetime.timedelta(hours=8))
        start = datetime.datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S%z").astimezone(tw_tz)
        end = datetime.datetime.strptime(end_str, "%Y-%m-%dT%H:%M:%S%z").astimezone(tw_tz)
        
        zh_weekdays = ['一', '二', '三', '四', '五', '六', '日']
        zh_start_week = zh_weekdays[start.weekday()]
        zh_end_week = zh_weekdays[end.weekday()]
        en_start_week = start.strftime("%a")
        en_end_week = end.strftime("%a")
        en_start_month = start.strftime("%b")
        en_end_month = end.strftime("%b")
        
        zh_start = f"{start.month:02d}.{start.day:02d}.{start.strftime('%H:%M')}.星期{zh_start_week}"
        zh_end = f"{end.month:02d}.{end.day:02d}.{end.strftime('%H:%M')}.星期{zh_end_week}"
        
        en_start = f"{en_start_week}.{en_start_month} {start.day:02d}.{start.strftime('%H:%M')}"
        en_end = f"{en_end_week}.{en_end_month} {end.day:02d}.{end.strftime('%H:%M')}"
        
        delta = end - start
        days = delta.days
        hours = delta.seconds // 3600
        zh_total = f"{days}天{hours}小時" if hours > 0 else f"{days}天"
        en_total = f"{days} Days {hours} Hours" if hours > 0 else f"{days} Days"
        
        return zh_start, zh_end, zh_total, en_start, en_end, en_total, start.timestamp()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            
            if custom_id.startswith("join_ctf:"):
                await interaction.response.defer(ephemeral=True)
                ctf_name = custom_id.split(":", 1)[1]
                guild = interaction.guild
                
                # 1. 獨立檢查並處理身分組
                role = discord.utils.get(guild.roles, name=ctf_name)
                if not role:
                    try:
                        role = await guild.create_role(name=ctf_name, color=discord.Color(0x1f8b4c), mentionable=True)
                        special_role = discord.utils.get(guild.roles, name="============SPECIAL============")
                        if special_role:
                            await role.edit(position=special_role.position - 1)
                    except Exception as e:
                        await interaction.followup.send(f"⚠️ 建立身分組失敗: `{e}`", ephemeral=True)
                        return

                # 把身份組給點擊按鈕的玩家
                if role not in interaction.user.roles:
                    await interaction.user.add_roles(role)
                
                # 2. 獨立檢查並處理頻道
                raw_channel_name = ctf_name.lower().replace(" ", "-")
                channel_name = re.sub(r'[^a-z0-9\-]', '', raw_channel_name)
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                
                if not channel:
                    try:
                        category = discord.utils.get(guild.categories, name="CTF Competition")
                        if not category:
                            category = await guild.create_category("CTF Competition")
                        
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(read_messages=False),
                            role: discord.PermissionOverwrite(read_messages=True)
                        }
                        
                        channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)
                        await interaction.followup.send(f"成功為您建立頻道：<#{channel.id}>", ephemeral=True)
                    except Exception as e:
                        await interaction.followup.send(f"建立頻道發生錯誤：`{e}`", ephemeral=True)
                else:
                    await interaction.followup.send(f"已為您加上 `{ctf_name}` 身分組，頻道已經在 <#{channel.id}> 準備好了！", ephemeral=True)

    @tasks.loop(hours=24) 
    async def ctftime_daily_check(self):
        await self.bot.wait_until_ready()

        events = await self.fetch_upcoming_ctfs(days=3)
        if not events:
            return

        for event in events:
            ctf_id = str(event.get('id'))
            
            if ctf_id in self.data["sent_ctfs"]:
                continue
                
            ctf_name = event.get('title', 'Unknown CTF')
            ctf_url = event.get('ctftime_url', '')
            logo_url = event.get('logo', '')
            
            zh_start, zh_end, zh_total, en_start, en_end, en_total, start_ts = self.format_ctf_time(event['start'], event['finish'])
            
            embed = discord.Embed(
                title=ctf_name,
                url=ctf_url if ctf_url else None,
                color=discord.Color(0x1f8b4c)
            )
            
            if logo_url:
                embed.set_thumbnail(url=logo_url)

            embed.add_field(
                name="台灣時間 (UTC+8)",
                value=f"**開始**: {zh_start}\n**結束**: {zh_end}\n**總共**: {zh_total}",
                inline=False
            )
            embed.add_field(
                name="Global Time",
                value=f"**Start**: {en_start}\n**End**: {en_end}\n**Total**: {en_total}",
                inline=False
            )
            
            for guild in self.bot.guilds:
                channel = discord.utils.get(guild.text_channels, name="ctf-competition")
                if channel:
                    view = discord.ui.View(timeout=None)
                    button = discord.ui.Button(label="參加 Join", style=discord.ButtonStyle.success, custom_id=f"join_ctf:{ctf_name}")
                    view.add_item(button)
                    
                    try:
                        await channel.send(embed=embed, view=view)
                    except discord.Forbidden:
                        pass
            
            self.data["sent_ctfs"].append(ctf_id)
            self.data["upcoming"][ctf_id] = {
                "name": ctf_name,
                "start_time": start_ts,
                "notified": False
            }
            self.save_data()

    @tasks.loop(minutes=1)
    async def ctf_hourly_reminder(self):
        await self.bot.wait_until_ready()
        now_ts = datetime.datetime.now().timestamp()
        
        for ctf_id, info in self.data["upcoming"].items():
            if info["notified"]:
                continue
                
            if now_ts >= (info["start_time"] - 3600):
                ctf_name = info["name"]
                
                for guild in self.bot.guilds:
                    raw_channel_name = ctf_name.lower().replace(" ", "-")
                    channel_name = re.sub(r'[^a-z0-9\-]', '', raw_channel_name)
                    channel = discord.utils.get(guild.text_channels, name=channel_name)
                    role = discord.utils.get(guild.roles, name=ctf_name)
                    
                    if channel and role:
                        ping_msg = (
                            f"{role.mention}\n"
                            f"**\"{ctf_name}\"** 開始於1小時後\n"
                            f"**\"{ctf_name}\"** Start in 1hr"
                        )
                        try:
                            await channel.send(ping_msg)
                        except discord.Forbidden:
                            pass
                
                self.data["upcoming"][ctf_id]["notified"] = True
                self.save_data()

async def setup(bot):
    await bot.add_cog(CTF(bot))