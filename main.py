import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

class RCEsBot(commands.Bot):
    def __init__(self):

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
        await self.tree.sync()
        print(f"已啟動：{self.user}")

bot = RCEsBot()

@bot.tree.command(name="help", description="顯示CTF Competition的使用教學")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="CTF Competition指令教學", color=discord.Color.blue())
    embed.add_field(name="CTF 功能", value="/ctftime`: 賽事提醒會發佈到頻道", inline=False)
    await interaction.response.send_message(embed=embed)

if __name__ == '__main__':
    bot.run(os.getenv("DISCORD_TOKEN"))