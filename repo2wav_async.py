import re
import httpx
import asyncio
import subprocess
import os

from bilibili_api.channel_series import ChannelSeries, ChannelSeriesType
from bilibili_api.video import Video, VideoDownloadURLDataDetecter
from bilibili_api import Credential, HEADERS
from browser_cookie3 import firefox


async def download_url(url: str, out: str, info: str):
    # 下载函数
    async with httpx.AsyncClient(headers=HEADERS) as sess:
        resp = await sess.get(url)
        length = resp.headers.get('content-length')
        with open(out, 'wb') as f:
            process = 0
            for chunk in resp.iter_bytes(1024):
                if not chunk:
                    break
                process += len(chunk)
                print(f'downloading {info} {process} / {length}')
                f.write(chunk)


credential = {}
cj = firefox(domain_name="bilibili.com")
for cookie in cj:
    name = cookie.name
    if name == 'DedeUserID':
        credential["dedeuserid"] = cookie.value
    elif name == 'bili_jct':
        credential["bili_jct"] = cookie.value
    elif name == 'buvid3':
        credential["buvid3"] = cookie.value
    elif name == 'SESSDATA':
        credential["sessdata"] = cookie.value
my_credential = Credential(**credential)

repo = "https://space.bilibili.com/1733415840/channel/collectiondetail?sid=1084109&ctype=0"
split_repo = repo.split("/")
target_uid = eval(split_repo[-3])
channel_series_type = ChannelSeriesType.SERIES if "series" in split_repo[-1] else ChannelSeriesType.SEASON
series_id = eval(re.search(r"sid=\d*", split_repo[-1]).group()[4:])
channel = ChannelSeries(uid=target_uid, type_=channel_series_type, id_=series_id,
                        credential=my_credential)

# Define a semaphore to limit concurrency
semaphore = asyncio.Semaphore(16)


async def process_video(archive, credential):
    async with semaphore:  # Ensure the semaphore limits execution
        bvid = archive['bvid']
        v = Video(bvid=bvid, credential=credential)

        # Get download URL data
        # Retry logic for timeout errors
        for attempt in range(3):  # Retry up to 3 times
            try:
                download_url_data = await asyncio.wait_for(v.get_download_url(0), timeout=120)
                break
            except asyncio.TimeoutError:
                if attempt < 2:
                    print(f"Timeout for {bvid}, retrying {attempt + 1}/3...")
                else:
                    print(f"Failed to process {bvid} after 3 retries.")
                    return

        detecter = VideoDownloadURLDataDetecter(data=download_url_data)
        best_streams = detecter.detect_best_streams()

        print(f'Starting to download {bvid}')

        # Download video
        m4s_file = f"{bvid}.m4s"
        if os.path.exists(m4s_file):
            print(f"Skipping download for {m4s_file}, file already exists.")
        else:
            await download_url(best_streams[1].url, m4s_file, f"{bvid}")

        # Convert to WAV using FFmpeg
        wav_file = f"{bvid}.wav"
        ffmpeg_command = ["ffmpeg", "-n", "-i", m4s_file, wav_file]
        subprocess.run(ffmpeg_command)
        print(f'Finished processing {bvid}')


async def main():
    videos = await channel.get_videos()

    # Create tasks, but ensure semaphore controls concurrency
    tasks = [process_video(archive, my_credential) for archive in videos['archives']]

    # Run tasks with limited concurrency
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
