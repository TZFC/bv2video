import os
from asyncio import get_event_loop
from os import remove
from re import sub
from time import sleep

import requests
from bilibili_api import Credential, HEADERS
from bilibili_api.user import User
from bilibili_api.video import Video, VideoDownloadURLDataDetecter
from browser_cookie3 import chrome, safari
from httpx import AsyncClient


async def get_max_range(url: str) -> int:
    __HEADERS = HEADERS.copy()
    __HEADERS["range"] = 'bytes=0-100'
    async with AsyncClient(headers=__HEADERS) as sess:
        resp = await sess.get(url)
        return int(resp.headers.get('content-range').split("/")[-1])


async def download_url(url: str, out: str, info: str, byte_range: str | None, append_to_head=False):
    __HEADERS = HEADERS.copy()
    if byte_range:
        __HEADERS["range"] = byte_range
    # 下载函数
    async with AsyncClient(headers=__HEADERS) as sess:
        resp = await sess.get(url)
        length = resp.headers.get('content-length')
        with open(out, 'ab' if append_to_head else 'wb') as f:
            process = 0
            for chunk in resp.iter_bytes(1024):
                if not chunk:
                    break
                process += len(chunk)
                print(f'下载 {info} {process} / {length}')
                f.write(chunk)


async def main():
    cj = None
    try:
        cj = chrome(domain_name="bilibili.com")
    except:
        pass
    if not cj:
        try:
            cj = safari(domain_name="bilibili.com")
        except:
            pass
    if not cj:
        print("请先在浏览器登录b站")
        sleep(3)
        return
    credential = {}
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
    if not credential:
        print("请在浏览器登录b站")
        sleep(3)
        return
    my_credential = Credential(**credential)
    user = User(uid=my_credential.dedeuserid)
    user_info = await user.get_user_info()
    uid = user_info['mid']
    username = user_info['name']
    vip = user_info['vip']
    is_vip = False if vip['status'] == 0 else True
    print(f"正在以 用户 {username}, uid = {uid} 账号登录")
    if is_vip:
        print("本账户有大会员")
    else:
        print("本账户无大会员")

    bvid_or_url = input("BV号 或 含BV号的url: ")
    bvid = None
    for seg in bvid_or_url.split('/'):
        if seg.startswith('BV'):
            bvid = seg
    if not bvid:
        print("BV号应以BV开头，若为url，请确认url内含BV号")
        sleep(3)
        return

    start_time = input("第几秒开始？(从头开始请输入0) : ")
    try:
        start_time_int = int(start_time)
    except:
        print("开始时间应为 整数 秒数！")
        sleep(3)
        return

    end_time = input("第几秒结束？(下到结尾请输入0) : ")
    try:
        end_time_int = int(end_time)
    except:
        print("结束时间应为 整数 秒数！")
        sleep(3)
        return

    # FFMPEG 路径，查看：http://ffmpeg.org/
    FFMPEG_PATH = r"ffmpeg.exe"

    # 实例化 Credential 类
    credential = my_credential
    # 实例化 Video 类
    v = Video(bvid=bvid, credential=credential)
    v_info = await v.get_info()
    duration = v_info['duration']
    start_percentage = max((start_time_int - 15) / duration, 0)
    end_percentage = min((end_time_int + 15) / duration, 1)
    title = v_info['title']
    cover_url = v_info['pic']
    owner_name = v_info['owner']['name']
    if start_time_int == 0 and end_time_int == 0:
        print("即将下载完整视频")
        file_name = sub(r'[^\w]', '', f"{owner_name}_{title}_全")
    elif start_time_int == 0:
        print(f"即将从开头下载至 {int(end_percentage * 100)}%")
        file_name = sub(r'[^\w]', '', f"{owner_name}_{title}_start_to_{int(end_percentage * 100)}%")
    elif end_time_int == 0:
        print(f"即将从 {int(start_percentage * 100)}% 下载至结尾")
        file_name = sub(r'[^\w]', '', f"{owner_name}_{title}_{int(start_percentage * 100)}%_to_end")
    else:
        print(f"即将从 {int(start_percentage * 100)}% 下载至 {int(end_percentage * 100)}%")
        file_name = sub(r'[^\w]', '',
                        f"{owner_name}_{title}_{int(start_percentage * 100)}%_to_{int(end_percentage * 100)}%")

    # 保存封面
    cover = requests.get(cover_url).content
    with open(f"{file_name}.jpg", 'wb') as file:
        file.write(cover)
    # 获取视频下载链接
    download_url_data = await v.get_download_url(0, html5=False)
    # 解析视频下载信息
    detector = VideoDownloadURLDataDetecter(data=download_url_data)
    best_streams = detector.detect_best_streams()

    # 有 MP4 流 / FLV 流两种可能
    if detector.check_flv_stream() == True:
        # FLV 流下载
        await download_url(best_streams[0].url, "flv_temp.flv", "FLV 音视频流")
        # 转换文件格式
        os.system(f'{FFMPEG_PATH} -i flv_temp.flv video.mp4')
        # 删除临时文件
        remove("flv_temp.flv")
    else:
        # MP4 流下载
        max_video_range = await get_max_range(best_streams[0].url)
        max_audio_range = await get_max_range(best_streams[1].url)
        if (start_time_int == 0 or start_percentage == 0) and (end_time_int == 0 or end_percentage == 0):
            await download_url(best_streams[0].url, "video_temp.m4s", "视频流", byte_range=None, append_to_head=False)
            await download_url(best_streams[1].url, "audio_temp.m4s", "音频流", byte_range=None, append_to_head=False)
        elif (end_time_int == 0 or end_percentage == 0):
            await download_url(best_streams[0].url, "video_temp.m4s", "视频流",
                               byte_range=f'bytes={int(max_video_range * start_percentage)}-{max_video_range}',
                               append_to_head=True)
            await download_url(best_streams[1].url, "audio_temp.m4s", "音频流",
                               byte_range=f'bytes={int(max_audio_range * start_percentage)}-{max_audio_range}',
                               append_to_head=True)
        elif (start_time_int == 0 or start_percentage == 0):
            await download_url(best_streams[0].url, "video_temp.m4s", "视频流",
                               byte_range=f'bytes=0-{int(max_video_range * end_percentage)}', append_to_head=False)
            await download_url(best_streams[1].url, "audio_temp.m4s", "音频流",
                               byte_range=f'bytes=0-{int(max_audio_range * end_percentage)}', append_to_head=False)
        else:
            await download_url(best_streams[0].url, "video_temp.m4s", "视频流",
                               byte_range=f'bytes={int(max_video_range * start_percentage)}-{int(max_video_range * end_percentage)}',
                               append_to_head=True)
            await download_url(best_streams[1].url, "audio_temp.m4s", "音频流",
                               byte_range=f'bytes={int(max_audio_range * start_percentage)}-{int(max_audio_range * end_percentage)}',
                               append_to_head=True)
        # 混流
        os.system(
            f'{FFMPEG_PATH} -err_detect ignore_err -i video_temp.m4s -i audio_temp.m4s -ignore_unknown -vcodec copy -acodec copy {file_name}.mp4')

        # 删除临时文件
        remove("video_temp.m4s")
        remove("audio_temp.m4s")


if __name__ == '__main__':
    # 主入口
    get_event_loop().run_until_complete(main())
