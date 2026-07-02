import discord
from discord.ext import commands, tasks
import aiohttp
import datetime

class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctftime_alert.start() 

    async def fetch_upcoming_ctfs(self, limit=3):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        now = datetime.datetime.now(datetime.timezone.utc)
        start_timestamp = int(now.timestamp())
        finish_timestamp = int((now + datetime.timedelta(days=14)).timestamp())
        
        url = f"https://ctftime.org/api/v1/events/?limit={limit}&start={start_timestamp}&finish={finish_timestamp}"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Failed to fetch CTFtime API. Status code: {response.status}")
                    return None

    @tasks.loop(hours=24) 
    async def ctftime_alert(self):
        await self.bot.wait_until_ready()
        
        channel = discord.utils.get(self.bot.get_all_channels(), name="ctf-competition")
        if not channel:
            print("Cannot find channel named 'ctf-competition', skipping alert.")
            return

        events = await self.fetch_upcoming_ctfs(limit=3)
        if not events:
            return

        embed = discord.Embed(
            title="📅 Upcoming CTF Events",
            description="Here are the top upcoming events within the next 14 days:",
            color=discord.Color.purple()
        )

        for event in events:
            title = event.get('title', 'Unknown Event')
            url = event.get('ctftime_url', 'No Link')
            weight = event.get('weight', 0)
            start_time = event.get('start', '').replace('T', ' ')[:16]
            format_text = event.get('format', 'Unknown')
            
            embed.add_field(
                name=f"🚩 {title}",
                value=f"**Time**: {start_time} (UTC)\n**Format**: {format_text}\n**Weight**: {weight}\n[🔗 View on CTFtime]({url})",
                inline=False
            )

        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CTF(bot))