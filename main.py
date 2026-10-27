import discord
from discord import app_commands
from discord.ext import commands
import re
import datetime

# 1. 봇 인텐트 설정 (음성 및 멤버 관리 권한 필수)
intents = discord.Intents.default()
intents.message_content = True  
intents.members = True
intents.voice_states = True     

class BaekByeolBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 슬래시 명령어 동기화
        await self.tree.sync()
        print("슬래시 명령어가 동기화되었습니다.")

bot = BaekByeolBot()

@bot.event
async def on_ready():
    print(f"백별봇 로그인 완료: {bot.user} (ID: {bot.user.id})")

# -------------------------------------------------------------
# 1. 슬래시 명령어: /음챗이사 (음성 채널 선택 이동 + 헤드셋 음소거 자동 켜짐)
# -------------------------------------------------------------
@bot.tree.command(name="음챗이사", description="선택한 음성 채널로 봇을 이동시킵니다.")
@app_commands.describe(channel="이동할 음성 채널을 선택하세요.")
async def move_voice(interaction: discord.Interaction, channel: discord.VoiceChannel):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.move_to(channel)
        await interaction.guild.change_voice_state(channel=channel, self_deaf=True)
        await interaction.response.send_message(f"🔇 🔊 {channel.name} 채널로 이동했습니다 (헤드셋 음소거 적용)!", ephemeral=True)
    else:
        await channel.connect(self_deaf=True)
        await interaction.response.send_message(f"🔇 🔊 {channel.name} 채널에 입장했습니다 (헤드셋 음소거 적용)!", ephemeral=True)

# -------------------------------------------------------------
# 2. 슬래시 명령어: /재생 (스포티파이 곡 검색 및 아티스트 선택)
# -------------------------------------------------------------
class ArtistSelectView(discord.ui.View):
    def __init__(self, tracks):
        super().__init__()
        options = [
            discord.SelectOption(label=track['name'], description=f"아티스트: {track['artist']}", value=str(i))
            for i, track in enumerate(tracks[:5])
        ]
        
        self.select_menu = discord.ui.Select(placeholder="어떤 아티스트의 곡으로 할까요?", options=options)
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)
        self.selected_track = None

    async def select_callback(self, interaction: discord.Interaction):
        selected_index = int(self.select_menu.values[0])
        self.selected_track = selected_index
        await interaction.response.edit_message(content=f"🎵 선택하신 곡을 재생 준비 중입니다...", view=None)
        self.stop()

@bot.tree.command(name="재생", description="스포티파이 곡을 검색하여 재생합니다.")
@app_commands.describe(query="재생할 곡 이름을 입력하세요.")
async def play_song(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)

    # 동일한 이름의 곡이 여러 개 검색된 상황을 가정하는 더미 데이터
    dummy_search_results = [
        {"name": query, "artist": "아티스트 A"},
        {"name": query, "artist": "아티스트 B"},
        {"name": query, "artist": "아티스트 C"}
    ]

    if len(dummy_search_results) > 1:
        view = ArtistSelectView(dummy_search_results)
        await interaction.followup.send(f"🔍 '{query}'에 대한 검색 결과가 여러 개 있습니다. 아티스트를 선택해주세요:", view=view)
        
        timed_out = await view.wait()
        if timed_out or view.selected_track is None:
            return

        chosen = dummy_search_results[view.selected_track]
        await interaction.followup.send(f"▶️ **{chosen['artist']}**의 **{chosen['name']}** 재생을 시작합니다!")
    else:
        await interaction.followup.send(f"▶️ **{query}** 재생을 시작합니다!")

# -------------------------------------------------------------
# 3. 텍스트 명령어 ("백별아 들어와", "백별아 [대상] 탐아 [시간]")
# -------------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    raw_content = message.content
    clean_content = raw_content.replace(" ", "")

    # 기능 A: "백별아 들어와" (헤드셋 음소거 상태로 음성 채널 입장)
    if clean_content == "백별아들어와":
        if message.author.voice and message.author.voice.channel:
            channel = message.author.voice.channel
            if message.guild.voice_client is not None:
                await message.guild.voice_client.move_to(channel)
                await message.guild.change_voice_state(channel=channel, self_deaf=True)
            else:
                await channel.connect(self_deaf=True)
            await message.channel.send(f"🔇 🔊 {channel.name} 채널에 입장했습니다 (헤드셋 음소거 켜짐)!")
        else:
            await message.channel.send("❌ 먼저 음성 채널에 들어가서 말씀해 주세요!")
        return

    # 기능 B: "백별아 [대상] 탐아 [시간]" (타임아웃)
    if clean_content.startswith("백별아") and "탐아" in clean_content:
        if not message.author.guild_permissions.moderate_members:
            await message.channel.send("❌ 이 명령어를 사용할 권한(멤버 관리)이 없습니다!")
            return

        target_member = None
        if message.mentions:
            target_member = message.mentions[0]
        else:
            try:
                pattern = r"백별아\s*(.+?)\s*탐아"
                match = re.search(pattern, raw_content)
                if match:
                    target_name = match.group(1).strip()
                    for member in message.guild.members:
                        if target_name in (member.name, member.display_name):
                            target_member = member
                            break
            except Exception as e:
                print(f"이름 파싱 오류: {e}")

        if not target_member:
            await message.channel.send("❌ 타임아웃을 적용할 상대를 찾지 못했어요! 정확한 닉네임을 적거나 멘션해 주세요.")
            return

        time_match = re.search(r"탐아\s*(\d+)([분시간일년]*)", clean_content)
        if not time_match:
            await message.channel.send("❌ 타임아웃 시간을 올바르게 입력해 주세요! (예: 백별아 쿠키 탐아 10분)")
            return

        time_val = int(time_match.group(1))
        time_unit = time_match.group(2) if time_match.group(2) else "분" 

        if "분" in time_unit:
            delta = datetime.timedelta(minutes=time_val)
        elif "시간" in time_unit:
            delta = datetime.timedelta(hours=time_val)
        elif "일" in time_unit:
            delta = datetime.timedelta(days=time_val)
        elif "년" in time_unit:
            delta = datetime.timedelta(days=365 * time_val)
        else:
            delta = datetime.timedelta(minutes=time_val)

        max_delta = datetime.timedelta(days=28)
        if delta > max_delta:
            delta = max_delta
            await message.channel.send("⚠️ 디스코드 정책상 타임아웃은 최대 28일까지만 가능하여 **최대 기간(28일)**으로 적용됩니다!")

        try:
            await target_member.timeout(delta, reason="백별봇 타임아웃 명령어 실행")
            await message.channel.send(f"✅ {target_member.mention}님을 성공적으로 타임아웃 처리했습니다!")
        except discord.Forbidden:
            await message.channel.send("❌ 봇의 권한이 부족하여 해당 유저를 타임아웃시킬 수 없습니다.")
        except Exception as e:
            await message.channel.send(f"❌ 오류가 발생했습니다: {e}")

    await bot.process_commands(message)

# 봇 실행
bot.run("MTU1MzA0NDI4MzMwMzUzMDUyNg.Gfs_3h.j8MwmDujmKq_gBQv1pd4jWJIzzdS6Ai-bcTZfg")
